#!/usr/bin/env python3
"""Scan tracked public text and reachable Git history for PHI-shaped content."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


_PATTERNS = (
    ("email_address", re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")),
    ("phone_number", re.compile(r"(?i)(?:\b(?:phone|telephone|mobile|tel)\s*[:=]\s*|(?<!\w)\+\d{1,3}[ .-])(?:\+\d{1,3}[ .-]?)?(?:\(?\d{2,4}\)?[ .-]?){2,4}\d{3,4}(?!\w)")),
    ("iso_date", re.compile(r"(?<!\d)(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)")),
    ("patient_identifier", re.compile(r"(?i)\b(?:patient|member)\s*(?:id|identifier)\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9._-]{2,}")),
    ("medical_record_identifier", re.compile(r"(?i)\b(?:medical[ -]*record(?:[ -]*(?:id|identifier|number))?|mrn)\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9._-]{2,}")),
    ("person_name", re.compile(r"(?i)\b(?:patient|member|full)[ -]*name\s*[:=]\s*[A-Za-z][A-Za-z .'-]{1,80}")),
    ("postal_address", re.compile(r"(?i)\b(?:home|street|patient|member)[ -]*address\s*[:=]\s*[A-Za-z0-9][^\r\n]{2,120}")),
    ("date_of_birth", re.compile(r"(?i)\b(?:date[ -]*of[ -]*birth|dob)\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9 ./-]{2,40}")),
    ("health_measurement", re.compile(r"(?i)\b(?:blood[ _-]*pressure|bp)\s*[:=]\s*\d{2,3}/\d{2,3}(?:\s*mmhg)?\b")),
    ("health_measurement", re.compile(r"(?i)\b(?:heart[ _-]*rate|pulse)\s*[:=]\s*\d{2,3}(?:\s*bpm)?\b")),
    ("health_measurement", re.compile(r"(?i)\b(?:glucose|blood[ _-]*sugar)\s*[:=]\s*\d{2,3}(?:\.\d+)?\s*(?:mg/dl|mmol/l)\b")),
    ("health_measurement", re.compile(r"(?i)\b(?:weight|body[ _-]*weight)\s*[:=]\s*\d{2,3}(?:\.\d+)?\s*(?:kg|lb|lbs)\b")),
    ("health_measurement", re.compile(r"(?i)\b(?:bmi|spo2|oxygen[ _-]*saturation|temperature)\s*[:=]\s*\d{1,3}(?:\.\d+)?\s*(?:%|c|f|°c|°f)?\b")),
)

_ASCII_LABEL_AT = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[ _-]+[A-Za-z0-9]+){0,5}")
_INERT_PLACEHOLDER = re.compile(r"\{[A-Za-z][A-Za-z0-9_]*\}")
_TAXONOMY_DECLARATION = re.compile(
    r'''(?x)\s*["']
    (?P<key>[A-Za-z][A-Za-z0-9]*(?:[ _-]+[A-Za-z0-9]+){0,5})
    ["']\s*:\s*["'](?P<value>[a-z_]+)["']\s*,?\s*'''
)

_IDENTIFIER_SUBJECTS = frozenset(("patient", "subject", "person", "member", "user", "device"))
_IDENTIFIER_TERMS = frozenset(("id", "identifier"))
_MEASUREMENT_KEYS = frozenset(
    (
        ("heart", "rate"),
        ("pulse",),
        ("blood", "pressure"),
        ("bp",),
        ("glucose",),
        ("blood", "glucose"),
        ("blood", "sugar"),
        ("weight",),
        ("body", "weight"),
        ("bmi",),
        ("spo2",),
        ("oxygen", "saturation"),
        ("temperature",),
    )
)


def _git(root: Path, *arguments: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=not binary,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git command failed: {' '.join(arguments)}")
    return result.stdout


def _text(content: bytes) -> str | None:
    if b"\0" in content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _normalize_machine_key(key: str) -> tuple[str, ...]:
    split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())
    split = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", split)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", split).strip("_").lower()
    words = tuple(part for part in normalized.split("_") if part)
    return ("spo2",) if words == ("sp", "o2") else words


def _machine_key_class(key: str) -> str | None:
    words = _normalize_machine_key(key)
    if len(words) == 2 and words[0] in _IDENTIFIER_SUBJECTS and words[1] in _IDENTIFIER_TERMS:
        return "patient_identifier"
    if words == ("mrn",) or words == ("medical", "record") or (
        len(words) == 3 and words[:2] == ("medical", "record") and words[2] in _IDENTIFIER_TERMS | {"number"}
    ):
        return "medical_record_identifier"
    if words in (("email",), ("email", "address")) or (
        len(words) == 2 and words[0] in _IDENTIFIER_SUBJECTS | {"contact"} and words[1] == "email"
    ):
        return "email_address"
    if words in (("phone",), ("phone", "number"), ("telephone",), ("telephone", "number"), ("mobile",), ("mobile", "number")) or (
        len(words) == 2 and words[0] in _IDENTIFIER_SUBJECTS | {"contact"} and words[1] in {"phone", "telephone", "mobile"}
    ):
        return "phone_number"
    if len(words) == 2 and words[0] in _IDENTIFIER_SUBJECTS | {"full", "first", "middle", "last", "given", "family"} and words[1] == "name":
        return "person_name"
    if words == ("address",) or (
        len(words) == 2
        and words[0] in _IDENTIFIER_SUBJECTS | {"home", "street", "postal", "mailing"}
        and words[1] == "address"
    ):
        return "postal_address"
    if words in (("date", "of", "birth"), ("birth", "date"), ("dob",)) or (
        len(words) >= 2 and words[0] in _IDENTIFIER_SUBJECTS and words[1:] in (("date", "of", "birth"), ("birth", "date"), ("dob",))
    ):
        return "date_of_birth"
    if words in _MEASUREMENT_KEYS:
        return "health_measurement"
    return None


def _safe_label_start(line: str, start: int) -> bool:
    if start == 0:
        return True
    previous = line[start - 1]
    if previous not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-":
        return True
    if previous != "_":
        return False
    wrapper_start = start - 1
    while wrapper_start > 0 and line[wrapper_start - 1] == "_":
        wrapper_start -= 1
    return wrapper_start == 0 or line[wrapper_start - 1] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"


def _label_closer_tokens(tail: str) -> tuple[str, ...] | None:
    """Lex the closed wrapper grammar between a candidate label and relation."""
    tokens: list[str] = []
    index = 0
    while index < len(tail):
        character = tail[index]
        if character in " \t":
            index += 1
            continue
        if character == "\\" and index + 1 < len(tail) and tail[index + 1] in "\\\"'[]":
            tokens.append(tail[index:index + 2])
            index += 2
            continue
        if character in "\"']":
            tokens.append(character)
            index += 1
            continue
        if character in "`*_":
            end = index + 1
            while end < len(tail) and tail[end] == character:
                end += 1
            tokens.append(tail[index:end])
            index = end
            continue
        return None
    return tuple(tokens)


def _balanced_label_wrappers(prefix: str, start: int, closers: tuple[str, ...]) -> bool:
    expected_openers = {"\\]": "\\[", "]": "["}
    cursor = start
    for closer in closers:
        while cursor > 0 and prefix[cursor - 1] in " \t":
            cursor -= 1
        opener = expected_openers.get(closer, closer)
        if not prefix[:cursor].endswith(opener):
            return False
        cursor -= len(opener)
    return True


def _quoted_candidate_is_concatenated(prefix: str, start: int, tail: str) -> bool:
    opener = start - 1
    if opener >= 0 and prefix[opener] in "\"'":
        quote = prefix[opener]
    elif opener >= 1 and prefix[opener - 1] == "\\" and prefix[opener] in "\"'":
        quote = prefix[opener]
        opener -= 1
    else:
        return False
    stripped_tail = tail.lstrip(" \t")
    if not (stripped_tail.startswith(quote) or stripped_tail.startswith("\\" + quote)):
        return False
    before = prefix[:opener].rstrip(" \t")
    return before.endswith("+")


def _label_candidates(prefix: str):
    for start, character in enumerate(prefix):
        if not character.isascii() or not character.isalpha() or not _safe_label_start(prefix, start):
            continue
        match = _ASCII_LABEL_AT.match(prefix, start)
        tail = prefix[match.end():] if match is not None else ""
        closers = _label_closer_tokens(tail)
        if (
            match is not None
            and closers is not None
            and _balanced_label_wrappers(prefix, start, closers)
            and not _quoted_candidate_is_concatenated(prefix, start, tail)
        ):
            yield match.group(0), start


def _containing_quote(line: str, separator: int) -> str | None:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line[:separator]):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in "\"'":
            if character == "'" and 0 < index < len(line) - 1 and line[index - 1].isalnum() and line[index + 1].isalnum():
                continue
            quote = character
    return quote


def _relation_value(line: str, start: int, containing_quote: str | None) -> str:
    while start < len(line) and line[start] in " \t":
        start += 1
    if start >= len(line):
        return ""
    if containing_quote is not None:
        index = start
        escaped = False
        while index < len(line):
            character = line[index]
            if not escaped and character == "\\" and index + 1 < len(line) and line[index + 1] == "n":
                break
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == containing_quote:
                break
            index += 1
        return line[start:index].strip()
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {"{": "}", "[": "]", "(": ")"}
    index = start
    while index < len(line):
        character = line[index]
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif quote is not None:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character in pairs:
            stack.append(pairs[character])
        elif stack and character == stack[-1]:
            stack.pop()
        elif not stack and character in ";,|":
            break
        index += 1
    return line[start:index].strip()


def _exact_taxonomy_declaration(line: str) -> bool:
    match = _TAXONOMY_DECLARATION.fullmatch(line)
    if match is None:
        return False
    finding = _machine_key_class(match.group("key"))
    return finding is not None and match.group("value") == finding


def _machine_label_classes(text: str) -> set[str]:
    findings: set[str] = set()
    for line in text.splitlines():
        if _exact_taxonomy_declaration(line):
            continue
        for separator, character in enumerate(line):
            if character not in ":=":
                continue
            raw_value = _relation_value(line, separator + 1, _containing_quote(line, separator))
            if not raw_value or _INERT_PLACEHOLDER.fullmatch(raw_value):
                continue
            prefix = line[:separator]
            for key, start in _label_candidates(prefix):
                finding = _machine_key_class(key)
                if finding is None:
                    continue
                diagnostic_prefix = prefix[max(0, start - 16):start]
                normalized_key = "_".join(_normalize_machine_key(key))
                if diagnostic_prefix.endswith(("PHI_CURRENT:", "PHI_HISTORY:")) and normalized_key == finding:
                    continue
                findings.add(finding)
    return findings


def _json_key_classes(value: Any) -> set[str]:
    findings: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            finding = _machine_key_class(key)
            inert_placeholder = isinstance(child, str) and _INERT_PLACEHOLDER.fullmatch(child.strip()) is not None
            empty_scalar = isinstance(child, str) and not child.strip()
            if finding is not None and not inert_placeholder and not empty_scalar:
                findings.add(finding)
            findings.update(_json_key_classes(child))
    elif isinstance(value, list):
        for child in value:
            findings.update(_json_key_classes(child))
    return findings


def finding_classes(path: str, content: bytes) -> tuple[str, ...]:
    text = _text(content)
    if text is None:
        return ()
    findings = {label for label, pattern in _PATTERNS if pattern.search(text)}
    findings.update(_machine_label_classes(text))
    if Path(path).suffix.lower() == ".json":
        try:
            findings.update(_json_key_classes(json.loads(text)))
        except json.JSONDecodeError:
            pass
    return tuple(sorted(findings))


def scan_current(root: Path) -> tuple[list[str], int]:
    raw = _git(root, "ls-files", "-z", binary=True)
    paths = tuple(item.decode("utf-8") for item in raw.split(b"\0") if item)
    findings: list[str] = []
    checked = 0
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        checked += 1
        for label in finding_classes(relative, path.read_bytes()):
            findings.append(f"PHI_CURRENT:{label}:{relative}")
    return sorted(set(findings)), checked


def scan_history(root: Path) -> tuple[list[str], int]:
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise ValueError("reachable history is shallow")
    commits = tuple(line for line in _git(root, "rev-list", "--reverse", "--all").splitlines() if line)
    findings: list[str] = []
    cache: dict[tuple[str, str], tuple[str, ...]] = {}
    checked_blobs: set[str] = set()
    for commit in commits:
        tree = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit, binary=True)
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            _mode, object_type, object_id = metadata.decode("ascii").split()
            if object_type != "blob":
                continue
            path = raw_path.decode("utf-8")
            cache_key = (object_id, Path(path).suffix.lower())
            if cache_key not in cache:
                content = _git(root, "cat-file", "-p", object_id, binary=True)
                cache[cache_key] = finding_classes(path, content)
            checked_blobs.add(object_id)
            for label in cache[cache_key]:
                findings.append(f"PHI_HISTORY:{label}:{commit}:{path}")
    return sorted(set(findings)), len(checked_blobs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-current", action="store_true")
    parser.add_argument("--check-history", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    check_current = args.check_current or not (args.check_current or args.check_history)
    check_history = args.check_history or not (args.check_current or args.check_history)
    findings: list[str] = []
    current_count = 0
    history_count = 0
    try:
        if check_current:
            current_findings, current_count = scan_current(root)
            findings.extend(current_findings)
        if check_history:
            history_findings, history_count = scan_history(root)
            findings.extend(history_findings)
    except (OSError, ValueError) as exc:
        print(f"SCAN_ERROR:repository:{type(exc).__name__}", file=sys.stderr)
        return 1
    for finding in sorted(set(findings)):
        print(finding, file=sys.stderr)
    if findings:
        return 1
    print(f"public content scan OK current_files={current_count} history_blobs={history_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
