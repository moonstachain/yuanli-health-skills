"""Descriptor-anchored no-follow operations for caller-selected package roots."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path, PurePosixPath


_MAX_TREE_DEPTH = 64
_MAX_TREE_ENTRIES = 4096
_MAX_TREE_BYTES = 64 * 1024 * 1024
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC


def absolute_lexical_path(path: Path) -> Path:
    """Make a path absolute without resolving any symbolic link."""
    return Path(os.path.abspath(os.fspath(path)))


def _identity(metadata: os.stat_result) -> tuple[int, int, int]:
    return metadata.st_dev, metadata.st_ino, stat.S_IFMT(metadata.st_mode)


def _safe_relative_parts(relative: str) -> tuple[str, ...]:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("unsafe generated package path")
    return pure.parts


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

    def _create_root(self) -> None:
        if not self._missing:
            return
        for name in self._missing:
            parent_index = len(self._descriptors) - 1
            parent_descriptor = self.descriptor
            try:
                os.mkdir(name, mode=0o755, dir_fd=parent_descriptor)
                child_descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_descriptor)
                metadata = os.fstat(child_descriptor)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(self.error_message)
            except (OSError, ValueError) as exc:
                if isinstance(exc, OSError) and exc.errno == errno.EEXIST:
                    raise ValueError(self.error_message) from exc
                raise ValueError(self.error_message) from exc
            self._descriptors.append(child_descriptor)
            self._bindings.append((parent_index, name, _identity(metadata)))
        self._missing = ()

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
        entries = 0
        total_bytes = 0

        def visit(directory_descriptor: int, prefix: str, depth: int) -> None:
            nonlocal entries, total_bytes
            if depth > _MAX_TREE_DEPTH:
                raise ValueError("package inventory exceeds safety budget")
            try:
                names = sorted(os.listdir(directory_descriptor))
            except OSError as exc:
                raise ValueError("package tree changed during anchored inspection") from exc
            for name in names:
                entries += 1
                if entries > _MAX_TREE_ENTRIES:
                    raise ValueError("package inventory exceeds safety budget")
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
                try:
                    file_descriptor = os.open(
                        name,
                        _READ_FLAGS,
                        dir_fd=directory_descriptor,
                    )
                except OSError as exc:
                    raise ValueError("package tree changed during anchored inspection") from exc
                try:
                    opened_metadata = os.fstat(file_descriptor)
                    if (
                        _identity(opened_metadata) != _identity(metadata)
                        or not stat.S_ISREG(opened_metadata.st_mode)
                        or opened_metadata.st_nlink != metadata.st_nlink
                    ):
                        raise ValueError("package tree changed during anchored inspection")
                    chunks: list[bytes] = []
                    file_bytes = 0
                    while True:
                        chunk = os.read(file_descriptor, 64 * 1024)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        file_bytes += len(chunk)
                        total_bytes += len(chunk)
                        if total_bytes > _MAX_TREE_BYTES:
                            raise ValueError("package inventory exceeds safety budget")
                    if os.fstat(file_descriptor).st_size != file_bytes:
                        raise ValueError("package tree changed during anchored inspection")
                    files[relative] = b"".join(chunks)
                finally:
                    os.close(file_descriptor)

        visit(self.descriptor, "", 0)
        return files, issues

    def clear_contents(self) -> None:
        """Delete only entries below the anchored directory identity."""
        if not self.exists:
            return

        def clear(directory_descriptor: int, depth: int) -> None:
            if depth > _MAX_TREE_DEPTH:
                raise ValueError("package inventory exceeds safety budget")
            try:
                names = sorted(os.listdir(directory_descriptor))
            except OSError as exc:
                raise ValueError("package tree changed during anchored clear") from exc
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
            metadata = os.fstat(child_descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child_descriptor)
                raise ValueError(error_message)
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
