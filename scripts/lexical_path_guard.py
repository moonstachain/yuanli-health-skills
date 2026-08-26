"""POSIX descriptor-anchored no-follow operations for caller-selected package roots."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path, PurePosixPath


_MAX_TREE_DEPTH = 64
_MAX_TREE_ENTRIES = 4096
_MAX_TREE_BYTES = 64 * 1024 * 1024
_POSIX_CAPABILITY_ERROR = "POSIX descriptor capabilities required for package integrity"
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


def require_posix_capabilities() -> None:
    """Fail closed instead of emulating no-follow descriptor semantics elsewhere."""
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    if os.name != "posix" or any(not hasattr(os, name) for name in required):
        raise ValueError(_POSIX_CAPABILITY_ERROR)


def absolute_lexical_path(path: Path) -> Path:
    """Make a path absolute without resolving any symbolic link."""
    require_posix_capabilities()
    return Path(os.path.abspath(os.fspath(path)))


def _identity(metadata: os.stat_result) -> tuple[int, int, int]:
    return metadata.st_dev, metadata.st_ino, stat.S_IFMT(metadata.st_mode)


def _stability(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    """Fields that must not change while a package member is being read."""
    return (
        *_identity(metadata),
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _safe_relative_parts(relative: str) -> tuple[str, ...]:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("unsafe generated package path")
    return pure.parts


class _EntryBudget:
    def __init__(self) -> None:
        self.count = 0

    def consume(self) -> None:
        self.count += 1
        if self.count > _MAX_TREE_ENTRIES:
            raise ValueError("package inventory exceeds safety budget")


def _bounded_names(directory_descriptor: int, budget: _EntryBudget, context: str) -> list[str]:
    """Materialize only a count-capped directory listing before lexical sorting."""
    names: list[str] = []
    try:
        with os.scandir(directory_descriptor) as entries:
            for entry in entries:
                budget.consume()
                names.append(entry.name)
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(context) from exc
    return sorted(names)


def _read_regular_file(
    directory_descriptor: int,
    name: str,
    metadata: os.stat_result,
    *,
    byte_budget: list[int] | None = None,
) -> bytes:
    """Read one no-follow regular file and reject any name or inode instability."""
    initial = _stability(metadata)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError("package tree changed during anchored inspection")
    try:
        descriptor = os.open(name, _READ_FLAGS, dir_fd=directory_descriptor)
    except OSError as exc:
        raise ValueError("package tree changed during anchored inspection") from exc
    try:
        if _stability(os.fstat(descriptor)) != initial:
            raise ValueError("package tree changed during anchored inspection")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if byte_budget is not None:
                byte_budget[0] += len(chunk)
                if byte_budget[0] > _MAX_TREE_BYTES:
                    raise ValueError("package inventory exceeds safety budget")
        final = os.fstat(descriptor)
        try:
            rebound = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        except OSError as exc:
            raise ValueError("package tree changed during anchored inspection") from exc
        if _stability(final) != initial or _stability(rebound) != initial or size != metadata.st_size:
            raise ValueError("package tree changed during anchored inspection")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


class LexicalPathIdentity:
    """Own the descriptors that define one lexical directory identity."""

    def __init__(
        self,
        path: Path,
        descriptors: list[int],
        bindings: list[tuple[int, str, tuple[int, int, int]]],
        missing: tuple[str, ...],
        error_message: str,
    ) -> None:
        self.path = path
        self._descriptors = descriptors
        self._bindings = bindings
        self._missing = missing
        self.error_message = error_message
        self._closed = False

    def __enter__(self) -> "LexicalPathIdentity":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    @property
    def exists(self) -> bool:
        return not self._missing

    @property
    def descriptor(self) -> int:
        if self._closed:
            raise ValueError(self.error_message)
        return self._descriptors[-1]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for descriptor in reversed(self._descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
        self._descriptors.clear()

    def revalidate_binding(self) -> None:
        """Check names only relative to their already-open lexical parents."""
        if self._closed:
            raise ValueError(self.error_message)
        try:
            for parent_index, name, expected in self._bindings:
                metadata = os.stat(
                    name,
                    dir_fd=self._descriptors[parent_index],
                    follow_symlinks=False,
                )
                if _identity(metadata) != expected or not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(self.error_message)
            if self._missing:
                try:
                    os.stat(
                        self._missing[0],
                        dir_fd=self.descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError(self.error_message)
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(self.error_message) from exc

    def _descriptor_for_lexical_path(self, path: Path) -> int | None:
        """Return a held descriptor only when it represents this exact lexical prefix."""
        for index, descriptor in enumerate(self._descriptors):
            if self.path.parts[: index + 1] == path.parts:
                return descriptor
        return None

    def _create_root(self, shared_identity: "LexicalPathIdentity | None" = None) -> None:
        if not self._missing:
            return
        for name in self._missing:
            parent_index = len(self._descriptors) - 1
            parent_descriptor = self.descriptor
            child_descriptor: int | None = None
            source_descriptor: int | None = None
            created_path = Path(*self.path.parts[: len(self._descriptors) + 1])
            try:
                try:
                    os.mkdir(name, mode=0o755, dir_fd=parent_descriptor)
                except FileExistsError as exc:
                    source_descriptor = (
                        shared_identity._descriptor_for_lexical_path(created_path) if shared_identity is not None else None
                    )
                    if source_descriptor is None:
                        raise ValueError(self.error_message) from exc
                    child_descriptor = os.dup(source_descriptor)
                else:
                    child_descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_descriptor)
                metadata = os.fstat(child_descriptor)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(self.error_message)
            except (OSError, ValueError) as exc:
                if child_descriptor is not None:
                    os.close(child_descriptor)
                if isinstance(exc, OSError) and exc.errno == errno.EEXIST:
                    raise ValueError(self.error_message) from exc
                raise ValueError(self.error_message) from exc
            assert child_descriptor is not None
            self._descriptors.append(child_descriptor)
            self._bindings.append((parent_index, name, _identity(metadata)))
        self._missing = ()

    def create_missing_root_from(self, shared_identity: "LexicalPathIdentity") -> None:
        """Create missing components while accepting only a package-held shared prefix."""
        self._create_root(shared_identity)

    def read_regular_file(self, relative: str) -> bytes:
        """Read one anchored metadata file without reopening its lexical parent."""
        parts = _safe_relative_parts(relative)
        if len(parts) != 1 or not self.exists:
            raise ValueError(self.error_message)
        try:
            metadata = os.stat(parts[0], dir_fd=self.descriptor, follow_symlinks=False)
        except OSError as exc:
            raise ValueError(self.error_message) from exc
        try:
            return _read_regular_file(self.descriptor, parts[0], metadata)
        except ValueError as exc:
            raise ValueError(self.error_message) from exc

    def write_regular_file(self, relative: str, content: bytes) -> None:
        """Atomically replace one metadata file below the anchored parent."""
        parts = _safe_relative_parts(relative)
        if len(parts) != 1:
            raise ValueError(self.error_message)
        self._create_root()
        name = parts[0]
        temporary_name = f".{name}.tmp"
        descriptor: int | None = None
        renamed = False
        try:
            descriptor = os.open(temporary_name, _WRITE_FLAGS, 0o644, dir_fd=self.descriptor)
            view = memoryview(content)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise ValueError(self.error_message)
                view = view[written:]
            final = os.fstat(descriptor)
            if (
                not stat.S_ISREG(final.st_mode)
                or final.st_nlink != 1
                or final.st_size != len(content)
            ):
                raise ValueError(self.error_message)
            os.rename(
                temporary_name,
                name,
                src_dir_fd=self.descriptor,
                dst_dir_fd=self.descriptor,
            )
            renamed = True
            rebound = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
            if _identity(final) != _identity(rebound) or rebound.st_nlink != 1 or rebound.st_size != len(content):
                raise ValueError(self.error_message)
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(self.error_message) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if not renamed:
                try:
                    os.unlink(temporary_name, dir_fd=self.descriptor)
                except OSError:
                    pass

    def snapshot(
        self,
        *,
        reject_executable: bool = False,
        missing_issue: bool = False,
    ) -> tuple[dict[str, bytes], list[str]]:
        """Read a bounded byte snapshot exclusively through anchored descriptors."""
        if not self.exists:
            return ({}, [self.error_message] if missing_issue else [])
        files: dict[str, bytes] = {}
        issues: list[str] = []
        entry_budget = _EntryBudget()
        total_bytes = [0]

        def visit(directory_descriptor: int, prefix: str, depth: int) -> None:
            if depth > _MAX_TREE_DEPTH:
                raise ValueError("package inventory exceeds safety budget")
            before_directory = _stability(os.fstat(directory_descriptor))
            names = _bounded_names(directory_descriptor, entry_budget, "package tree changed during anchored inspection")
            for name in names:
                relative = f"{prefix}/{name}" if prefix else name
                try:
                    metadata = os.stat(
                        name,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise ValueError("package tree changed during anchored inspection") from exc
                mode = metadata.st_mode
                if stat.S_ISLNK(mode):
                    issues.append(f"symlink forbidden: {relative}")
                    continue
                if stat.S_ISDIR(mode):
                    try:
                        child_descriptor = os.open(
                            name,
                            _DIRECTORY_FLAGS,
                            dir_fd=directory_descriptor,
                        )
                    except OSError as exc:
                        raise ValueError("package tree changed during anchored inspection") from exc
                    try:
                        if _identity(os.fstat(child_descriptor)) != _identity(metadata):
                            raise ValueError("package tree changed during anchored inspection")
                        visit(child_descriptor, relative, depth + 1)
                    finally:
                        os.close(child_descriptor)
                    continue
                if not stat.S_ISREG(mode):
                    issues.append(f"special file forbidden: {relative}")
                    continue
                if metadata.st_nlink != 1:
                    issues.append(f"hardlink forbidden: {relative}")
                if reject_executable and mode & 0o111:
                    issues.append(f"executable forbidden: {relative}")
                files[relative] = _read_regular_file(
                    directory_descriptor,
                    name,
                    metadata,
                    byte_budget=total_bytes,
                )
            if _stability(os.fstat(directory_descriptor)) != before_directory:
                raise ValueError("package tree changed during anchored inspection")

        visit(self.descriptor, "", 0)
        self.revalidate_binding()
        return files, issues

    def clear_contents(self) -> None:
        """Delete only entries below the anchored directory identity."""
        if not self.exists:
            return

        entry_budget = _EntryBudget()

        def clear(directory_descriptor: int, depth: int) -> None:
            if depth > _MAX_TREE_DEPTH:
                raise ValueError("package inventory exceeds safety budget")
            names = _bounded_names(directory_descriptor, entry_budget, "package tree changed during anchored clear")
            for name in names:
                try:
                    metadata = os.stat(
                        name,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                    if stat.S_ISDIR(metadata.st_mode):
                        child_descriptor = os.open(
                            name,
                            _DIRECTORY_FLAGS,
                            dir_fd=directory_descriptor,
                        )
                        try:
                            if _identity(os.fstat(child_descriptor)) != _identity(metadata):
                                raise ValueError("package tree changed during anchored clear")
                            clear(child_descriptor, depth + 1)
                        finally:
                            os.close(child_descriptor)
                        os.rmdir(name, dir_fd=directory_descriptor)
                    elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                        os.unlink(name, dir_fd=directory_descriptor)
                    else:
                        raise ValueError("unsafe generated output inventory")
                except ValueError:
                    raise
                except OSError as exc:
                    raise ValueError("package tree changed during anchored clear") from exc

        clear(self.descriptor, 0)

    def write_files(self, files: dict[str, bytes]) -> None:
        """Create package files only below the anchored directory identity."""
        self._create_root()
        for relative, content in sorted(files.items()):
            parts = _safe_relative_parts(relative)
            directory_descriptor = os.dup(self.descriptor)
            try:
                for name in parts[:-1]:
                    try:
                        child_descriptor = os.open(
                            name,
                            _DIRECTORY_FLAGS,
                            dir_fd=directory_descriptor,
                        )
                    except FileNotFoundError:
                        try:
                            os.mkdir(name, mode=0o755, dir_fd=directory_descriptor)
                            child_descriptor = os.open(
                                name,
                                _DIRECTORY_FLAGS,
                                dir_fd=directory_descriptor,
                            )
                        except OSError as exc:
                            raise ValueError("package write failed closed") from exc
                    except OSError as exc:
                        raise ValueError("package write failed closed") from exc
                    os.close(directory_descriptor)
                    directory_descriptor = child_descriptor
                try:
                    file_descriptor = os.open(
                        parts[-1],
                        _WRITE_FLAGS,
                        0o644,
                        dir_fd=directory_descriptor,
                    )
                except OSError as exc:
                    raise ValueError("package write failed closed") from exc
                try:
                    view = memoryview(content)
                    while view:
                        written = os.write(file_descriptor, view)
                        if written <= 0:
                            raise ValueError("package write failed closed")
                        view = view[written:]
                finally:
                    os.close(file_descriptor)
            finally:
                os.close(directory_descriptor)


def inspect_lexical_path(
    path: Path,
    error_message: str = "package root must be a real directory",
) -> LexicalPathIdentity:
    """Open every existing lexical component with no-follow semantics."""
    require_posix_capabilities()
    absolute = absolute_lexical_path(path)
    descriptors: list[int] = []
    bindings: list[tuple[int, str, tuple[int, int, int]]] = []
    try:
        root_descriptor = os.open(absolute.anchor, _DIRECTORY_FLAGS)
        descriptors.append(root_descriptor)
        parts = absolute.parts[1:]
        for index, name in enumerate(parts):
            parent_index = len(descriptors) - 1
            try:
                child_descriptor = os.open(
                    name,
                    _DIRECTORY_FLAGS,
                    dir_fd=descriptors[parent_index],
                )
            except FileNotFoundError:
                return LexicalPathIdentity(
                    absolute,
                    descriptors,
                    bindings,
                    tuple(parts[index:]),
                    error_message,
                )
            except OSError as exc:
                raise ValueError(error_message) from exc
            try:
                metadata = os.fstat(child_descriptor)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(error_message)
            except Exception:
                os.close(child_descriptor)
                raise
            descriptors.append(child_descriptor)
            bindings.append((parent_index, name, _identity(metadata)))
        return LexicalPathIdentity(absolute, descriptors, bindings, (), error_message)
    except Exception:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def revalidate_lexical_path(identity: LexicalPathIdentity) -> None:
    """Compatibility wrapper for descriptor-relative lexical binding checks."""
    identity.revalidate_binding()
