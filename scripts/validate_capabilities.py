#!/usr/bin/env python3
"""Validate health-skill ABI JSON files without third-party dependencies."""

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yuanli_health_skills.validator import (  # noqa: E402
    ValidationError,
    ValidationResult,
    validate_contract,
    validate_envelope,
    validate_receipt,
    validate_source_registry,
)


class DuplicateJsonKeyError(ValueError):
    pass


def _reject_non_finite(constant: str) -> None:
    raise ValueError(f"non-standard JSON constant: {constant}")


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_strict_json(raw: str) -> object:
    return json.loads(
        raw,
        parse_constant=_reject_non_finite,
        object_pairs_hook=_object_without_duplicates,
    )


def _paths(arguments: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for argument in arguments:
        path = Path(argument)
        paths.extend(sorted(path.glob("*.json")) if path.is_dir() else [path])
    return paths


def _validate(document: object) -> ValidationResult:
    schema = document.get("schema") if isinstance(document, dict) else None
    validators = {
        "health-skill-contract-v1": validate_contract,
        "typed-candidate-envelope-v1": validate_envelope,
        "qualification-receipt-v1": validate_receipt,
        "suite-source-manifest-v1": validate_source_registry,
    }
    validator = validators.get(schema)
    if validator is None:
        return ValidationResult((ValidationError("INVALID_SCHEMA", "schema", "unsupported or missing schema"),))
    return validator(document)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="JSON file or directory; defaults to the source registry")
    args = parser.parse_args(argv)
    paths = _paths(args.paths or [str(ROOT / "registry" / "source-capabilities.json")])
    if not paths:
        print("NO_DOCUMENTS:$:no JSON documents found", file=sys.stderr)
        return 1
    failed = False
    for path in paths:
        try:
            document = _load_strict_json(path.read_text(encoding="utf-8"))
        except DuplicateJsonKeyError as exc:
            print(f"{path}:DUPLICATE_JSON_KEY:$:{exc}", file=sys.stderr)
            failed = True
            continue
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"{path}:INVALID_JSON:$:{exc}", file=sys.stderr)
            failed = True
            continue
        result = _validate(document)
        if result.ok:
            print(f"{path}:OK")
            continue
        failed = True
        for error in result.errors:
            print(f"{path}:{error.code}:{error.path}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
