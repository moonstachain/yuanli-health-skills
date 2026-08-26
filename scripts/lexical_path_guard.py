"""No-follow identity checks for caller-selected package roots."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LexicalPathIdentity:
    path: Path
    components: tuple[tuple[str, int, int, int], ...]
    first_missing: str | None
    error_message: str


def absolute_lexical_path(path: Path) -> Path:
    """Make a path absolute without resolving any symbolic link."""
    return Path(os.path.abspath(os.fspath(path)))


def inspect_lexical_path(
    path: Path,
    error_message: str = "package root must be a real directory",
) -> LexicalPathIdentity:
    """Inspect each existing lexical component in order with no-follow metadata."""
    absolute = absolute_lexical_path(path)
    current = Path(absolute.anchor)
    components: list[tuple[str, int, int, int]] = []
    first_missing: str | None = None

    for part in absolute.parts:
        if part == absolute.anchor:
            candidate = current
        else:
            candidate = current / part
            current = candidate
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            first_missing = str(candidate)
            break
        mode = metadata.st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(error_message)
        if not stat.S_ISDIR(mode):
            raise ValueError(error_message)
        components.append(
            (
                str(candidate),
                metadata.st_dev,
                metadata.st_ino,
                stat.S_IFMT(mode),
            )
        )

    return LexicalPathIdentity(
        path=absolute,
        components=tuple(components),
        first_missing=first_missing,
        error_message=error_message,
    )


def revalidate_lexical_path(identity: LexicalPathIdentity) -> None:
    """Fail closed if any checked component or missing boundary changed."""
    current = inspect_lexical_path(identity.path, identity.error_message)
    if (
        current.components != identity.components
        or current.first_missing != identity.first_missing
    ):
        raise ValueError(identity.error_message)
