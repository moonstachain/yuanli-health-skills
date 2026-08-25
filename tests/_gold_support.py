import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "fixtures" / "gold-slice" / "cases.json"


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def case_by_id(case_id: str) -> dict[str, Any]:
    return next(case for case in load_cases() if case["case_id"] == case_id)


def walk_keys(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_keys(nested)


def supplied_facts(case: dict[str, Any]) -> set[str]:
    facts = set(case["constraints"])
    if isinstance(case["goal"], str) and case["goal"]:
        facts.add(case["goal"])
    facts.update(entry["fact"] for entry in case["evidence"])
    return facts
