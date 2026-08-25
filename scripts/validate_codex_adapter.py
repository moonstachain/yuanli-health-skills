#!/usr/bin/env python3
"""Validate a generated Codex health Skill candidate using the standard library."""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from codex_adapter_reference import render_reference


PACKAGE_RELATIVE = Path("dist/codex/yuanli-health")
METADATA_RELATIVE = Path("releases/v0.1.0/release-metadata.json")


class DuplicateKeyError(ValueError):
    pass


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object)


def _load_validators(root: Path):
    sys.path.insert(0, str(root / "src"))
    from yuanli_health_skills.validator import (  # pylint: disable=import-outside-toplevel
        validate_contract,
        validate_receipt,
        validate_source_registry,
    )

    return validate_contract, validate_receipt, validate_source_registry


def _inspect(package: Path) -> tuple[dict[str, bytes], list[str]]:
    issues: list[str] = []
    files: dict[str, bytes] = {}
    if not package.exists() or package.is_symlink() or not package.is_dir():
        return {}, ["package root must be a real directory"]
    for directory, names, filenames in os.walk(package, followlinks=False):
        base = Path(directory)
        for name in names + filenames:
            path = base / name
            relative = path.relative_to(package).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                issues.append(f"symlink forbidden: {relative}")
            elif stat.S_ISREG(mode):
                if path.stat().st_nlink != 1:
                    issues.append(f"hardlink forbidden: {relative}")
                if mode & 0o111:
                    issues.append(f"executable forbidden: {relative}")
                files[relative] = path.read_bytes()
            elif not stat.S_ISDIR(mode):
                issues.append(f"special file forbidden: {relative}")
    return files, issues


def _safe_checksum_path(raw: str) -> bool:
    path = PurePosixPath(raw)
    return bool(raw) and not path.is_absolute() and ".." not in path.parts and "\\" not in raw


def _frontmatter(content: str) -> dict[str, str] | None:
    if not content.startswith("---\n"):
        return None
    end = content.find("\n---\n", 4)
    if end < 0:
        return None
    result: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        if key in result:
            return None
        result[key.strip()] = value.strip()
    return result


def _expected_paths(source_ids: tuple[str, ...]) -> set[str]:
    paths = {"SKILL.md", "LICENSE", "NOTICE", "registry-map.json", "SHA256SUMS", "contracts/suite-source-manifest.json"}
    paths.update(f"references/{item}.md" for item in source_ids)
    paths.update(f"contracts/capabilities/{item}.json" for item in source_ids)
    paths.update(f"contracts/qualification-receipts/{item}.json" for item in source_ids)
    return paths


def _markdown_targets(content: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?<!!)\[[^]\n]*\]\(([^)\n]+)\)", content))


def _local_link_path(markdown_path: str, raw_target: str) -> tuple[str | None, str | None]:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    else:
        target = target.split(maxsplit=1)[0]
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        scheme = target.split(":", 1)[0].lower()
        return (None, None) if scheme in {"http", "https", "mailto"} else (None, "unsupported link scheme")
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None, None
    path = PurePosixPath(target)
    if path.is_absolute() or "\\" in target:
        return None, "absolute link forbidden"
    parts: list[str] = []
    for part in (PurePosixPath(markdown_path).parent / path).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None, "link escapes package"
            parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts).as_posix(), None


def _validate_markdown_links(files: dict[str, bytes], expected: set[str], source_ids: tuple[str, ...]) -> list[str]:
    issues: list[str] = []
    markdown_paths = ("SKILL.md", *(f"references/{source_id}.md" for source_id in source_ids))
    for markdown_path in markdown_paths:
        for raw_target in _markdown_targets(files[markdown_path].decode("utf-8")):
            target, error = _local_link_path(markdown_path, raw_target)
            if error is not None:
                issues.append(f"markdown link invalid: {markdown_path}: {error}")
                continue
            if target is None:
                continue
            if target not in expected or target not in files:
                issues.append(f"markdown link target missing or forbidden: {markdown_path}")
                continue
            if markdown_path.startswith("references/"):
                source_id = markdown_path.removeprefix("references/").removesuffix(".md")
                contract_prefix = "contracts/capabilities/"
                receipt_prefix = "contracts/qualification-receipts/"
                if target.startswith(contract_prefix) and target != f"{contract_prefix}{source_id}.json":
                    issues.append(f"member contract link mismatch: {source_id}")
                if target.startswith(receipt_prefix) and target != f"{receipt_prefix}{source_id}.json":
                    issues.append(f"member receipt link mismatch: {source_id}")
    return issues


def validate_package(root: Path, package: Path) -> tuple[list[str], str | None, int]:
    validate_contract, validate_receipt, validate_source_registry = _load_validators(root)
    issues: list[str] = []
    source_registry = _json(root / "registry/source-capabilities.json")
    source_ids = tuple(member["source_capability_id"] for member in source_registry["members"])
    files, inspection = _inspect(package)
    issues.extend(inspection)
    expected = _expected_paths(source_ids)
    if set(files) != expected:
        issues.append(f"package paths differ: missing={sorted(expected - set(files))} extra={sorted(set(files) - expected)}")
    if issues:
        return issues, None, len(files)

    checksum_entries: list[tuple[str, str]] = []
    for line in files["SHA256SUMS"].decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None or not _safe_checksum_path(match.group(2)):
            issues.append("invalid checksum entry")
            continue
        checksum_entries.append((match.group(2), match.group(1)))
    expected_checksum_paths = sorted(expected - {"SHA256SUMS"})
    if [path for path, _ in checksum_entries] != expected_checksum_paths:
        issues.append("checksum paths must be unique, lexical, and exact")
    for relative, digest in checksum_entries:
        if relative not in files or hashlib.sha256(files[relative]).hexdigest() != digest:
            issues.append(f"checksum mismatch: {relative}")

    frontmatter = _frontmatter(files["SKILL.md"].decode("utf-8"))
    if frontmatter is None or set(frontmatter) != {"name", "description"}:
        issues.append("malformed Skill frontmatter")
    elif frontmatter["name"] != "yuanli-health" or not frontmatter["description"].startswith("Use when"):
        issues.append("invalid Skill discovery metadata")
    links = set(re.findall(r"\(references/([a-z0-9.-]+)\.md\)", files["SKILL.md"].decode("utf-8")))
    if links != set(source_ids):
        issues.append("root Skill member links mismatch")
    issues.extend(_validate_markdown_links(files, expected, source_ids))

    manifest = _json(package / "contracts/suite-source-manifest.json")
    manifest_result = validate_source_registry(manifest)
    if not manifest_result.ok or manifest != source_registry:
        issues.append("suite source manifest mismatch")
    registry_map = _json(package / "registry-map.json")
    expected_map = {"schema": "codex-health-registry-map-v1", "source_suite_id": source_registry["source_suite_id"], "members": source_registry["members"]}
    if registry_map != expected_map:
        issues.append("registry map identity/order/null mismatch")

    for source_id in source_ids:
        source_contract = _json(root / "capabilities" / source_id / "contract.json")
        contract = _json(package / "contracts/capabilities" / f"{source_id}.json")
        receipt = _json(package / "contracts/qualification-receipts" / f"{source_id}.json")
        if not validate_contract(contract).ok or contract != source_contract:
            issues.append(f"contract mismatch: {source_id}")
        expected_receipt = {
            "schema": "qualification-receipt-v1",
            "source_capability_id": source_id,
            "qualification_basis": "synthetic_only",
            "claims": ["non_clinical", "non_release"],
            "candidate_state": "qualified",
            "canonical_write": False,
        }
        if not validate_receipt(receipt).ok or receipt != expected_receipt:
            issues.append(f"receipt mismatch: {source_id}")
        reference_bytes = files[f"references/{source_id}.md"]
        reference = reference_bytes.decode("utf-8")
        if reference.count(f"Source capability: `{source_id}`") != 1:
            issues.append(f"reference identity mismatch: {source_id}")
        source_instructions = (root / "capabilities" / source_id / "instructions.md").read_text(encoding="utf-8")
        if reference_bytes != render_reference(source_id, source_contract, source_instructions):
            issues.append(f"reference source correspondence mismatch: {source_id}")

    if files["LICENSE"] != (root / "LICENSE").read_bytes() or not files["LICENSE"].startswith(b"Apache License\nVersion 2.0"):
        issues.append("license mismatch")
    if files["NOTICE"] != (root / "NOTICE").read_bytes():
        issues.append("notice mismatch")
    return issues, hashlib.sha256(files["SHA256SUMS"]).hexdigest(), len(files)


def validate_metadata(path: Path, content_hash: str, file_count: int) -> list[str]:
    document = _json(path)
    expected = {
        "schema": "yuanli-health-release-candidate-v1",
        "version": "0.1.0",
        "source_suite_id": "YL-SUITE-HEALTH-20260823-0001",
        "catalog_suite_id": "zk:suite:yuanli-health",
        "state": "qualified_source_candidate",
        "published": False,
        "registry_admission": False,
        "deployment": "none",
        "release_basis": "synthetic_qualification_only",
        "human_runtime_observed": False,
        "health_outcome": "not_observed",
        "clinical_effectiveness": "not_claimed",
        "n5_pilot": "waived_by_human_owner",
        "package_path": "dist/codex/yuanli-health",
        "package_content_sha256": content_hash,
        "package_file_count": file_count,
        "package_file_count_convention": "all_regular_files_including_SHA256SUMS",
        "source_commit": None,
        "source_tree": None,
        "registry_commit": None,
        "registry_capability_ids": None,
        "resolution_gate": "candidate_commit_then_human_and_registry_gates",
    }
    return [] if document == expected else ["release metadata mismatch or false release claim"]


def validate_repository(root: Path) -> list[str]:
    issues: list[str] = []
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if not license_text.startswith("Apache License\nVersion 2.0") or "END OF TERMS AND CONDITIONS" not in license_text:
        issues.append("root license is not Apache-2.0")
    readme = (root / "README.md").read_text(encoding="utf-8").lower()
    for required in ("16 qualified", "synthetic-only", "qualified source candidate", "not released", "registry-admitted", "canon"):
        if required not in readme:
            issues.append(f"README candidate boundary missing: {required}")
    workflow = (root / ".github/workflows/health-skills-ci.yml").read_text(encoding="utf-8")
    forbidden = ("secrets.", "pull_request_target", "permissions: write", "contents: write")
    if any(item in workflow for item in forbidden):
        issues.append("workflow secret or write authority forbidden")
    for required in (
        "python3 -m unittest discover -s tests -v",
        "scripts/validate_capabilities.py",
        "scripts/generate_codex_adapter.py --check",
        "scripts/validate_codex_adapter.py --check-repository",
        "scripts/scan_public_content.py --check-current --check-history",
        "fetch-depth: 0",
    ):
        if required not in workflow:
            issues.append(f"workflow gate missing: {required}")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project.get("requires-python") != ">=3.11" or project.get("dependencies") != []:
        issues.append("runtime dependency boundary changed")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--package", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--check-repository", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    package = args.package.resolve() if args.package else root / PACKAGE_RELATIVE
    metadata = args.metadata.resolve() if args.metadata else (root / METADATA_RELATIVE if args.check_repository else None)
    try:
        issues, content_hash, file_count = validate_package(root, package)
        if not issues and metadata is not None:
            issues.extend(validate_metadata(metadata, content_hash or "", file_count))
        if args.check_repository:
            issues.extend(validate_repository(root))
    except (OSError, ValueError, json.JSONDecodeError, DuplicateKeyError, ImportError) as exc:
        issues = [f"validation exception: {exc}"]
        content_hash = None
        file_count = 0
    for issue in issues:
        print(issue, file=sys.stderr)
    if issues:
        return 1
    print(f"adapter valid files={file_count} content_sha256={content_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
