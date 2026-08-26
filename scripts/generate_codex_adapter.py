#!/usr/bin/env python3
"""Deterministically generate or check the local Codex health Skill candidate."""

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from codex_adapter_reference import (
    read_instruction_source,
    render_checksum_manifest,
    render_reference,
    render_root,
)
from lexical_path_guard import (
    LexicalPathIdentity,
    absolute_lexical_path,
    inspect_lexical_path,
    revalidate_lexical_path,
)


PACKAGE_RELATIVE = Path("dist/codex/yuanli-health")
METADATA_RELATIVE = Path("releases/v0.1.0/release-metadata.json")
PRODUCT_SCHEMA_NAMES = (
    "health-evidence-view-v1",
    "recovery-compass-snapshot-v1",
    "quarter-health-campaign-v1",
    "weekly-experiment-v1",
    "professional-escalation-v1",
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validators(root: Path):
    sys.path.insert(0, str(root / "src"))
    from yuanli_health_skills.validator import (  # pylint: disable=import-outside-toplevel
        validate_contract,
        validate_source_registry,
    )

    return validate_contract, validate_source_registry


def build_package(root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    validate_contract, validate_source_registry = _load_validators(root)
    registry = _load_json(root / "registry/source-capabilities.json")
    registry_result = validate_source_registry(registry)
    if not registry_result.ok:
        raise ValueError("source registry is invalid: " + ", ".join(f"{e.code}:{e.path}" for e in registry_result.errors))
    source_ids = tuple(member["source_capability_id"] for member in registry["members"])
    files: dict[str, bytes] = {
        "SKILL.md": render_root(source_ids),
        "LICENSE": (root / "LICENSE").read_bytes(),
        "NOTICE": (root / "NOTICE").read_bytes(),
        "contracts/suite-source-manifest.json": _json_bytes(registry),
        "registry-map.json": _json_bytes(
            {
                "schema": "codex-health-registry-map-v1",
                "source_suite_id": registry["source_suite_id"],
                "members": registry["members"],
            }
        ),
    }
    for schema_name in PRODUCT_SCHEMA_NAMES:
        schema_path = root / "contracts" / f"{schema_name}.schema.json"
        schema_bytes = schema_path.read_bytes()
        schema = json.loads(schema_bytes.decode("utf-8"))
        if (
            schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
            or schema.get("properties", {}).get("schema", {}).get("const") != schema_name
        ):
            raise ValueError(f"product schema identity mismatch: {schema_name}")
        files[f"contracts/product-contracts/{schema_name}.schema.json"] = schema_bytes
    for source_id in source_ids:
        source_directory = root / "capabilities" / source_id
        contract = _load_json(source_directory / "contract.json")
        result = validate_contract(contract)
        if not result.ok:
            raise ValueError(f"invalid source contract {source_id}: " + ", ".join(f"{e.code}:{e.path}" for e in result.errors))
        if contract["source_capability_id"] != source_id:
            raise ValueError(f"source identity mismatch: {source_id}")
        instructions = read_instruction_source(
            source_directory / "instructions.md",
            source_id,
        )
        files[f"references/{source_id}.md"] = render_reference(source_id, contract, instructions)
        files[f"contracts/capabilities/{source_id}.json"] = _json_bytes(contract)
        files[f"contracts/qualification-receipts/{source_id}.json"] = _json_bytes(
            {
                "schema": "qualification-receipt-v1",
                "source_capability_id": source_id,
                "qualification_basis": "synthetic_only",
                "claims": ["non_clinical", "non_release"],
                "candidate_state": "qualified",
                "canonical_write": False,
            }
        )
    files["SHA256SUMS"] = render_checksum_manifest(files)
    return files, registry


def _metadata(files: dict[str, bytes], registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "yuanli-health-release-candidate-v1",
        "version": "0.1.0",
        "source_suite_id": registry["source_suite_id"],
        "catalog_suite_id": registry["catalog_suite_id"],
        "state": "qualified_source_candidate",
        "published": False,
        "registry_admission": False,
        "deployment": "none",
        "release_basis": "synthetic_qualification_only",
        "human_runtime_observed": False,
        "health_outcome": "not_observed",
        "clinical_effectiveness": "not_claimed",
        "n5_pilot": "waived_by_human_owner",
        "package_path": PACKAGE_RELATIVE.as_posix(),
        "package_content_sha256": hashlib.sha256(files["SHA256SUMS"]).hexdigest(),
        "package_file_count": len(files),
        "package_file_count_convention": "all_regular_files_including_SHA256SUMS",
        "source_commit": None,
        "source_tree": None,
        "registry_commit": None,
        "registry_capability_ids": None,
        "resolution_gate": "candidate_commit_then_human_and_registry_gates",
    }


def _existing_files(root: LexicalPathIdentity) -> tuple[dict[str, bytes], list[str]]:
    return root.snapshot()


def _clear_output(output: LexicalPathIdentity) -> None:
    _, issues = _existing_files(output)
    if issues:
        raise ValueError("unsafe generated output: " + "; ".join(issues))
    output.clear_contents()


def _write_package(
    output: LexicalPathIdentity,
    files: dict[str, bytes],
) -> None:
    revalidate_lexical_path(output)
    _clear_output(output)
    output.write_files(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = absolute_lexical_path(args.output) if args.output else root / PACKAGE_RELATIVE
    metadata_path = absolute_lexical_path(args.metadata) if args.metadata else (root / METADATA_RELATIVE if args.output is None else None)
    try:
        with contextlib.ExitStack() as stack:
            output_identity = stack.enter_context(inspect_lexical_path(output))
            metadata_identity = (
                stack.enter_context(inspect_lexical_path(metadata_path.parent)) if metadata_path is not None else None
            )
            deferred_metadata_parent = metadata_identity is not None and not metadata_identity.exists
            files, registry = build_package(root)
            metadata = _metadata(files, registry)
            if args.check:
                revalidate_lexical_path(output_identity)
                existing, issues = _existing_files(output_identity)
                if issues or existing != files:
                    print("generated package is missing, extra, unsafe, or byte-different", file=sys.stderr)
                    return 1
                if metadata_identity is not None and metadata_identity.read_regular_file(metadata_path.name) != _json_bytes(metadata):
                    print("release metadata is missing or byte-different", file=sys.stderr)
                    return 1
            else:
                _write_package(output_identity, files)
                if deferred_metadata_parent:
                    metadata_identity.create_missing_root_from(output_identity)
                if metadata_identity is not None:
                    metadata_identity.write_regular_file(metadata_path.name, _json_bytes(metadata))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"adapter OK files={len(files)} content_sha256={hashlib.sha256(files['SHA256SUMS']).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
