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

_JSON_KEYS = {
    "patient_id": "patient_identifier",
    "patient_identifier": "patient_identifier",
    "member_id": "patient_identifier",
    "member_identifier": "patient_identifier",
    "patient_name": "person_name",
    "full_name": "person_name",
    "device_id": "patient_identifier",
    "device_identifier": "patient_identifier",
    "medical_record_id": "medical_record_identifier",
    "medical_record_identifier": "medical_record_identifier",
    "medical_record_number": "medical_record_identifier",
    "mrn": "medical_record_identifier",
    "email": "email_address",
    "email_address": "email_address",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "date_of_birth": "date_of_birth",
    "dob": "date_of_birth",
    "home_address": "postal_address",
}


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


def _json_key_classes(value: Any) -> set[str]:
    findings: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[ -]+", "_", key.strip().lower())
            if normalized in _JSON_KEYS:
                findings.add(_JSON_KEYS[normalized])
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
