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

_MAX_CONTENT_BYTES = 2 * 1024 * 1024
_MAX_JSON_DEPTH = 128
_MAX_JSON_NODES = 100_000
_MAX_RELATIONS_PER_LINE = 512


class ScanError(ValueError):
    """Base class for stable, redacted scanner failures."""


class ScanBudgetError(ScanError):
    """Input exceeded a deterministic scanner work budget."""


class ScanDepthError(ScanError):
    """Structured input exceeded the accepted nesting depth."""


class ScanFormatError(ScanError):
    """Structured input is malformed."""


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


def _ascii_identifier_before_quote(
    line: str,
    quote_index: int,
) -> bool:
    start = quote_index
    while start > 0 and (
        line[start - 1].isascii()
        and (line[start - 1].isalnum() or line[start - 1] == "_")
    ):
        start -= 1
    prefix = line[start:quote_index]
    return not (
        not prefix
        or not prefix[0].isascii()
        or not (prefix[0].isalpha() or prefix[0] == "_")
        or any(not (character.isascii() and (character.isalnum() or character == "_")) for character in prefix)
    )


def _last_unescaped_quotes(line: str) -> dict[str, int]:
    escaped = False
    positions: dict[str, int] = {}
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character in "\"'":
            positions[character] = index
    return positions


def _identifier_prefixed_quote_opener(
    line: str,
    quote_index: int,
    sensitive_relation_starts: frozenset[int],
    last_unescaped_quotes: dict[str, int],
) -> bool:
    """Recognize definite identifier-prefixed quoted extents."""
    if not _ascii_identifier_before_quote(line, quote_index):
        return False
    if quote_index < last_unescaped_quotes.get(line[quote_index], -1):
        return True
    label_start = quote_index + 1
    while label_start < len(line) and line[label_start] in " \t":
        label_start += 1
    return label_start in sensitive_relation_starts


def _relation_quote_states(
    line: str,
    initial_quote: str | None,
    sensitive_relation_starts: frozenset[int],
) -> tuple[dict[int, str | None], str | None, int | None]:
    quote = initial_quote
    escaped = False
    points: dict[int, str | None] = {}
    ambiguous_opener: int | None = None
    last_unescaped_quotes = _last_unescaped_quotes(line)
    for index, character in enumerate(line):
        if character in ":=":
            points[index] = quote
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif quote is not None:
            if character == quote:
                quote = None
        elif character in "\"'":
            possible_apostrophe = (
                character == "'"
                and 0 < index < len(line) - 1
                and line[index - 1].isalnum()
                and line[index + 1].isalnum()
            )
            definite_opener = _identifier_prefixed_quote_opener(
                line,
                index,
                sensitive_relation_starts,
                last_unescaped_quotes,
            )
            if possible_apostrophe and not definite_opener:
                if ambiguous_opener is None and _ascii_identifier_before_quote(line, index):
                    ambiguous_opener = index
            else:
                quote = character
    return points, quote, ambiguous_opener


def _label_relation_candidates(line: str) -> dict[int, list[tuple[str, int]]]:
    """Find supported label/relation pairs in one bounded forward pass."""
    candidates: dict[int, list[tuple[str, int]]] = {}
    allowed_tail = " \t\\\"']`*_"
    for start, character in enumerate(line):
        if not character.isascii() or not character.isalpha() or not _safe_label_start(line, start):
            continue
        match = _ASCII_LABEL_AT.match(line, start)
        if match is None:
            continue
        cursor = match.end()
        while cursor < len(line) and line[cursor] in allowed_tail:
            cursor += 1
        if cursor >= len(line) or line[cursor] not in ":=":
            continue
        tail = line[match.end():cursor]
        closers = _label_closer_tokens(tail)
        if (
            closers is not None
            and _balanced_label_wrappers(line, start, closers)
            and not _quoted_candidate_is_concatenated(line, start, tail)
        ):
            candidates.setdefault(cursor, []).append((match.group(0), start))
    return candidates


def _same_line_value_state(line: str, start: int, containing_quote: str | None) -> str:
    while start < len(line) and line[start] in " \t":
        start += 1
    if start == len(line):
        return "empty"
    if containing_quote is not None and line[start] == containing_quote:
        return "empty"
    placeholder = _INERT_PLACEHOLDER.match(line, start)
    if placeholder is not None:
        cursor = placeholder.end()
        while cursor < len(line) and line[cursor] in " \t":
            cursor += 1
        if cursor == len(line) or (
            containing_quote is not None
            and (
                line[cursor] == containing_quote
                or line.startswith("\\n", cursor)
                or line.startswith("\\r", cursor)
            )
        ):
            return "placeholder"
    return "observable"


def _exact_taxonomy_declaration(line: str) -> bool:
    match = _TAXONOMY_DECLARATION.fullmatch(line)
    if match is None:
        return False
    finding = _machine_key_class(match.group("key"))
    return finding is not None and match.group("value") == finding


def _initial_quoted_fragment(line: str, quote: str) -> tuple[str, bool]:
    """Return text before the first unescaped closing quote on this line."""
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == quote:
            return line[:index], True
    return line, False


def _quoted_fragment_is_inert(fragment: str) -> bool:
    stripped = fragment.strip()
    return not stripped or _INERT_PLACEHOLDER.fullmatch(stripped) is not None


def _machine_label_classes(text: str) -> set[str]:
    findings: set[str] = set()
    quote: str | None = None
    pending_quote_classes: set[str] = set()
    ambiguous_quote: str | None = None
    pending_ambiguous_classes: set[str] = set()
    for line in text.splitlines():
        if quote is not None and pending_quote_classes:
            fragment, quote_closes = _initial_quoted_fragment(line, quote)
            if not _quoted_fragment_is_inert(fragment):
                findings.update(pending_quote_classes)
                pending_quote_classes.clear()
            elif quote_closes:
                pending_quote_classes.clear()
        candidates = _label_relation_candidates(line)
        sensitive_relation_starts = frozenset(
            start
            for relations in candidates.values()
            for key, start in relations
            if _machine_key_class(key) is not None
        )
        relation_quotes, next_quote, possible_ambiguous_opener = _relation_quote_states(
            line,
            quote,
            sensitive_relation_starts,
        )
        if _exact_taxonomy_declaration(line):
            quote = next_quote
            continue
        if len(relation_quotes) > _MAX_RELATIONS_PER_LINE:
            raise ScanBudgetError("relation budget exceeded")
        for separator, containing_quote in relation_quotes.items():
            for key, start in candidates.get(separator, ()):
                finding = _machine_key_class(key)
                if finding is None:
                    continue
                diagnostic_prefix = line[max(0, start - 16):start]
                normalized_key = "_".join(_normalize_machine_key(key))
                if diagnostic_prefix.endswith(("PHI_CURRENT:", "PHI_HISTORY:")) and normalized_key == finding:
                    continue
                value_state = _same_line_value_state(line, separator + 1, containing_quote)
                if value_state == "observable" or (
                    value_state == "empty" and containing_quote is None
                ):
                    findings.add(finding)
                elif (
                    value_state in {"empty", "placeholder"}
                    and containing_quote is not None
                    and next_quote == containing_quote
                ):
                    pending_quote_classes.add(finding)

        ambiguous_start: int | None = None
        ambiguous_end: int | None = None
        ambiguous_continues = False
        if ambiguous_quote is not None:
            fragment, closes = _initial_quoted_fragment(line, ambiguous_quote)
            ambiguous_start = 0
            ambiguous_end = len(fragment)
            ambiguous_continues = not closes
            if pending_ambiguous_classes:
                if not _quoted_fragment_is_inert(fragment):
                    findings.update(pending_ambiguous_classes)
                    pending_ambiguous_classes.clear()
                elif closes:
                    pending_ambiguous_classes.clear()
        elif possible_ambiguous_opener is not None:
            ambiguous_quote = line[possible_ambiguous_opener]
            ambiguous_start = possible_ambiguous_opener + 1
            ambiguous_end = len(line)
            ambiguous_continues = True

        if ambiguous_start is not None and ambiguous_end is not None:
            for separator in relation_quotes:
                if not ambiguous_start <= separator < ambiguous_end:
                    continue
                for key, start in candidates.get(separator, ()):
                    finding = _machine_key_class(key)
                    if finding is None:
                        continue
                    diagnostic_prefix = line[max(0, start - 16):start]
                    normalized_key = "_".join(_normalize_machine_key(key))
                    if diagnostic_prefix.endswith(("PHI_CURRENT:", "PHI_HISTORY:")) and normalized_key == finding:
                        continue
                    value_state = _same_line_value_state(
                        line[:ambiguous_end],
                        separator + 1,
                        ambiguous_quote,
                    )
                    if value_state == "observable":
                        findings.add(finding)
                    elif value_state in {"empty", "placeholder"} and ambiguous_continues:
                        pending_ambiguous_classes.add(finding)

        if not ambiguous_continues:
            ambiguous_quote = None
        quote = next_quote
    findings.update(pending_quote_classes)
    findings.update(pending_ambiguous_classes)
    return findings


def _preflight_json(text: str) -> None:
    stack: list[str] = []
    quote = False
    escaped = False
    pairs = {"{": "}", "[": "]"}
    for character in text:
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = False
            continue
        if character == '"':
            quote = True
        elif character in pairs:
            stack.append(pairs[character])
            if len(stack) > _MAX_JSON_DEPTH:
                raise ScanDepthError("JSON depth exceeded")
        elif character in "}]":
            if not stack or stack.pop() != character:
                raise ScanFormatError("JSON delimiter mismatch")
    if quote or stack:
        raise ScanFormatError("JSON delimiter incomplete")


def _json_key_classes(value: Any) -> set[str]:
    findings: set[str] = set()
    stack = [value]
    nodes = 0
    while stack:
        current = stack.pop()
        nodes += 1
        if nodes > _MAX_JSON_NODES:
            raise ScanBudgetError("JSON node budget exceeded")
        if isinstance(current, dict):
            for key, child in current.items():
                finding = _machine_key_class(key)
                inert_placeholder = (
                    isinstance(child, str)
                    and _INERT_PLACEHOLDER.fullmatch(child.strip()) is not None
                )
                if finding is not None and not inert_placeholder:
                    findings.add(finding)
                stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)
    return findings


def finding_classes(path: str, content: bytes) -> tuple[str, ...]:
    if len(content) > _MAX_CONTENT_BYTES:
        raise ScanBudgetError("content byte budget exceeded")
    structured_path = Path(path).suffix.lower() == ".json"
    if structured_path:
        if b"\0" in content:
            raise ScanFormatError("malformed JSON bytes")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ScanFormatError("malformed JSON bytes") from exc
    else:
        text = _text(content)
        if text is None:
            return ()
    structured: Any | None = None
    if structured_path:
        _preflight_json(text)
        try:
            structured = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ScanFormatError("malformed JSON") from exc
        except RecursionError as exc:
            raise ScanDepthError("JSON decoder depth exceeded") from exc
    findings = {label for label, pattern in _PATTERNS if pattern.search(text)}
    findings.update(_machine_label_classes(text))
    if structured is not None:
        findings.update(_json_key_classes(structured))
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
