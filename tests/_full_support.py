import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "fixtures" / "full-suite" / "cases.json"


CAPABILITIES = {
    "yuanli.health.kernel.wpk": ("kernel", ["WPK"], ["DEC", "WPK"], "behavioral", "emit_wpk", "subject"),
    "yuanli.health.kernel.act": ("kernel", ["ACT"], ["WPK", "ACT"], "behavioral", "emit_act", "subject"),
    "yuanli.health.kernel.out": ("kernel", ["OUT"], ["ACT", "OUT"], "experimental", "adjudicate_out", "subject"),
    "yuanli.health.kernel.lrn": ("kernel", ["LRN"], ["OUT", "LRN"], "experimental", "emit_lrn", "subject"),
    "yuanli.health.experience.ninety-day-health-experiment": ("experience", ["WPK", "ACT"], ["DEC", "WPK", "ACT"], "experimental", "orchestrate_ninety_day_experiment", "subject"),
    "yuanli.health.experience.weekly-health-checkpoint": ("experience", ["ACT"], ["ACT"], "behavioral", "orchestrate_weekly_checkpoint", "subject"),
    "yuanli.health.experience.doctor-visit-prep": ("experience", ["CTX", "EVD", "DEC"], ["CTX", "EVD", "DEC"], "clinical", "prepare_doctor_visit", "subject"),
    "yuanli.health.experience.outcome-review": ("experience", ["OUT"], ["ACT", "OUT"], "experimental", "orchestrate_outcome_review", "subject"),
    "yuanli.health.experience.learning-reuse": ("experience", ["LRN"], ["OUT", "LRN"], "experimental", "orchestrate_learning_reuse", "subject"),
    "yuanli.health.meta.build": ("meta", ["WPK"], ["CTX", "EVD", "DEC", "WPK", "ACT", "OUT", "LRN"], "experimental", "build_capability_candidate", "system_contract"),
    "yuanli.health.meta.review": ("meta", ["DEC"], ["CTX", "EVD", "DEC", "WPK", "ACT", "OUT", "LRN"], "experimental", "review_capability_candidate", "system_contract"),
    "yuanli.health.meta.qualify": ("meta", ["LRN"], ["CTX", "EVD", "DEC", "WPK", "ACT", "OUT", "LRN"], "experimental", "qualify_synthetic_candidate", "system_contract"),
}


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def case_by_id(case_id: str) -> dict[str, Any]:
    return next(case for case in load_cases() if case["case_id"] == case_id)


def supplied_artifact_facts(case: dict[str, Any]) -> set[str]:
    facts: set[str] = set()
    for value in case["artifacts"].values():
        if isinstance(value, list):
            facts.update(value)
        elif value != "":
            facts.add(str(value))
    return facts


def walk_keys(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_keys(nested)
