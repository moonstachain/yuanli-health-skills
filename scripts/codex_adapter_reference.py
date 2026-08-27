"""Pure deterministic rendering for generated Codex Markdown."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any


_CONTRACT_LABEL = "`contract.json`"
_PLAIN_TITLE = re.compile(r"# [A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*")

_EXPERIENCE_ROUTES = (
    ("创始人健康起盘 / First Health Session", "yuanli.health.experience.first-health-session"),
    ("90天恢复力战役 / 90-Day Health Experiment", "yuanli.health.experience.ninety-day-health-experiment"),
    ("五分钟每周校准 / Weekly Health Checkpoint", "yuanli.health.experience.weekly-health-checkpoint"),
    ("专业就医准备 / Doctor Visit Preparation", "yuanli.health.experience.doctor-visit-prep"),
    ("30/60/90证据复盘 / Outcome Review", "yuanli.health.experience.outcome-review"),
    ("个人健康打法 / Learning Reuse", "yuanli.health.experience.learning-reuse"),
)


def _contract_token(target: str) -> str:
    return f"[{_CONTRACT_LABEL}]({target})"


def _closed_instruction_projection(
    source_id: str,
    instructions: str,
    *,
    contract_target: str,
    replacement_target: str | None = None,
) -> str:
    """Lex the deliberately closed instruction grammar in one forward pass."""
    if "\r" in instructions or "\0" in instructions:
        raise ValueError(f"source Markdown link policy: non-canonical text bytes: {source_id}")
    if not instructions.endswith("\n") or instructions.endswith("\n\n"):
        raise ValueError(f"source Markdown link policy: exact final LF required: {source_id}")

    token = _contract_token(contract_target)
    replacement = _contract_token(replacement_target or contract_target)
    output: list[str] = []
    links = 0
    index = 0
    while index < len(instructions):
        if instructions.startswith(token, index):
            links += 1
            output.append(replacement)
            index += len(token)
            continue

        character = instructions[index]
        if character == "\\":
            raise ValueError(f"source Markdown link policy: backslash escapes forbidden: {source_id}")
        if character in "[]":
            raise ValueError(f"source Markdown link policy: unsupported bracket syntax: {source_id}")
        if character in "<>":
            raise ValueError(f"source Markdown link policy: raw autolink syntax forbidden: {source_id}")
        if character == "~" and instructions.startswith("~~~", index):
            raise ValueError(f"source Markdown link policy: fenced code forbidden: {source_id}")
        if character == "`":
            if (index > 0 and instructions[index - 1] == "`") or instructions.startswith("``", index):
                raise ValueError(f"source Markdown link policy: multi-backtick runs forbidden: {source_id}")
            close = instructions.find("`", index + 1)
            newline = instructions.find("\n", index + 1)
            if close < 0 or (newline >= 0 and newline < close) or close == index + 1:
                raise ValueError(f"source Markdown link policy: invalid inline code span: {source_id}")
            if close + 1 < len(instructions) and instructions[close + 1] == "`":
                raise ValueError(f"source Markdown link policy: multi-backtick runs forbidden: {source_id}")
            output.append(instructions[index:close + 1])
            index = close + 1
            continue
        output.append(character)
        index += 1

    if links != 1:
        raise ValueError(f"source Markdown link policy: expected one exact contract link: {source_id}")
    return "".join(output)


def read_instruction_source(path: Path, source_id: str) -> str:
    """Read exact instruction bytes and decode strict UTF-8 without newline translation."""
    raw = path.read_bytes()
    if b"\0" in raw:
        raise ValueError(f"source Markdown link policy: non-canonical text bytes: {source_id}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"source Markdown link policy: invalid UTF-8: {source_id}") from exc


def _source_document_projection(
    source_id: str,
    instructions: str,
    *,
    contract_target: str,
    replacement_target: str | None = None,
) -> tuple[str, str]:
    """Validate the one fixed source shape and return its title and operation."""
    token = _contract_token(contract_target)
    lines = instructions.splitlines()
    purpose_line = lines[4] if len(lines) > 4 else ""
    token_offset = purpose_line.find(token)
    purpose_is_plain = (
        bool(purpose_line)
        and purpose_line == purpose_line.lstrip(" \t")
        and re.match(r"(?:>|[-+*][ \t]+|[0-9]+[.)][ \t]+|```|~~~)", purpose_line) is None
        and token_offset >= 0
        and (token_offset == 0 or purpose_line[token_offset - 1] != "!")
        and purpose_line[:token_offset].count("`") % 2 == 0
    )
    if (
        len(lines) < 6
        or _PLAIN_TITLE.fullmatch(lines[0]) is None
        or lines[1] != ""
        or lines[2] != "## Purpose"
        or lines[3] != ""
        or not purpose_is_plain
        or lines[5] != ""
        or instructions.count(token) != 1
        or token not in lines[4]
    ):
        raise ValueError(f"source Markdown link policy: fixed document shape required: {source_id}")
    rewritten = _closed_instruction_projection(
        source_id,
        instructions,
        contract_target=contract_target,
        replacement_target=replacement_target,
    )
    title = lines[0][2:]
    source_prefix = f"# {title}\n\n"
    if not rewritten.startswith(source_prefix):
        raise ValueError(f"source Markdown link policy: fixed title boundary required: {source_id}")
    return title, rewritten[len(source_prefix):]


def validate_instruction_operation(
    source_id: str,
    title: str,
    operation: str,
    contract_target: str,
) -> str:
    """Validate one emitted operation under the same fixed document shape."""
    validated_title, validated_operation = _source_document_projection(
        source_id,
        f"# {title}\n\n{operation}",
        contract_target=contract_target,
    )
    if validated_title != title or validated_operation != operation:
        raise ValueError(f"source Markdown link policy: emitted operation mismatch: {source_id}")
    return operation


def render_checksum_manifest(files: dict[str, bytes]) -> bytes:
    """Render exact lowercase SHA-256 entries in lexical path order with one final LF."""
    return "".join(
        f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
        for relative, content in sorted(files.items())
        if relative != "SHA256SUMS"
    ).encode("utf-8")


def render_root(source_ids: tuple[str, ...]) -> bytes:
    """Render the exact root Skill from the ordered source identities."""
    route_lines = "\n".join(
        f"- {trigger}: read [the exact member reference](references/{source_id}.md)."
        for trigger, source_id in _EXPERIENCE_ROUTES
    )
    route_ids = {item[1] for item in _EXPERIENCE_ROUTES}
    internal_lines = "\n".join(
        f"- `{source_id}`: [member reference](references/{source_id}.md)"
        for source_id in source_ids
        if source_id not in route_ids
    )
    return f"""---
name: yuanli-health
description: Use when handling synthetic Yuanli Health Skill Core candidate work, including founder recovery journeys, weekly calibration, professional-visit preparation, evidence review, and explicit internal Kernel or Meta requests.
---

# 原力健康 Skill Core v0.1.0

Yuanli Health Skill Core v0.1.0: 以90天为周期，持续改善创始人的恢复力，让健康成为长期创业的底盘。

Use this adapter to select one bounded source capability and preserve its machine contract. Inputs stay synthetic and in memory. Never copy real or re-identifiable health material into repository files, receipts, logs, or generated references.

This public Skill Core is not a managed Health OS: it has no cloud vault, health steward, real-person persistence, human-runtime evidence, or clinical-effectiveness claim. Founder context is limited to user-supplied critical-campaign timing, travel/time-zone pressure, workload rhythm, and recovery constraints; do not ingest meeting content or confidential business details.

## Decide before routing

Clinical diagnosis, prescription, medication change, chest-pain or urgent/emergency risk never become model conclusions. Stop with concise bilingual guidance to contact a clinician or local emergency services; do not create WPK/ACT or protect a deadline. Refuse persistence and logging even when an owner requests them.

Route only these user JTBDs to Experiences:

{route_lines}

A founder request for `90天起盘` without a supplied opaque `decision_candidate_id` routes to 创始人健康起盘 / First Health Session. Present one qualitative, evidence-linked Recovery Compass direction, not an aggregate health/readiness/wellness/performance score; name one current bottleneck candidate and one non-clinical action candidate only when evidence and the Authority gate permit. Make evidence, unknowns, assumptions, and escalation explicit. Stop at `decision_candidate_ready`: do not fabricate WPK or ACT. Only after a supplied opaque DEC may `90天起盘` continue to 90天恢复力战役 / the 90-Day Health Experiment, which orders WPK before ACT and emits no OUT.

The founder journey may explain three 30-day phases — 起盘与稳定, 实验与校准, 证据复盘与沉淀 — but they are not a formal plan before WPK/ACT prerequisites exist. Recovery Compass is a transparent discussion direction, never a diagnosis or score.

If none matches, return no route. Never fall back to Kernel or Meta and never decide health priority. Kernel and Meta are direct/internal only; read their reference only when the request explicitly names that capability and supplies its prerequisites:

{internal_lines}

## Execute the selected contract

Read only the selected reference and its packaged JSON contract. Preserve supplied facts with evidence references, explicit unknowns and assumptions, final Authority, candidate state, escalation/guardrail, `canonical_write=false`, and `persistence=none`. Do not invent IDs, evidence, receipts, unknown labels, machine fields, or missing prerequisites.

- First Health Session ends at `decision_candidate_ready`; it emits no WPK or ACT.
- OUT requires ACT plus observation; LRN requires OUT; REUSE requires LRN and distinct Task-2 preload/use receipts.
- DEC selects zero or one primary bottleneck and at most two blockers.
- Doctor Visit Prep prepares only supplied questions. Delegate provider selection, booking, pricing, and payment to `yuanli-medical-appointment-operator`; perform none here.
- Meta never self-admits, assigns Registry IDs, claims Human acceptance, tags, releases, publishes, or deploys.

If strict input cannot satisfy the selected member contract, stop at that contract's stable error boundary instead of fabricating an aggregate result. Qualification is synthetic-only: never claim a health outcome, clinical effectiveness, runtime observation, Canon mutation, Registry admission, or publication.
""".encode("utf-8")


def render_reference(source_id: str, contract: dict[str, Any], instructions: str) -> bytes:
    """Render one exact reference from its frozen source identity and content."""
    packaged_contract = f"../contracts/capabilities/{source_id}.json"
    title, rewritten_operation = _source_document_projection(
        source_id,
        instructions,
        contract_target="contract.json",
        replacement_target=packaged_contract,
    )
    details = {
        "source_capability_id": source_id,
        "class": contract["class"],
        "profile_of": contract["profile_of"],
        "transition_intent": contract["transition_intent"],
        "final_authority": contract["authority"]["final_authority"],
        "objects": contract["objects"],
        "health_clock": contract["health_clock"],
        "registry_capability_id": contract["registry_capability_id"],
        "canonical_write": contract["mutates_canon"],
        "persistence": contract["runtime_requirements"]["persistence"],
        "logs": contract["runtime_requirements"]["logs"],
        "claims": contract["claims"],
    }
    body = (
        "<!-- Generated from platform-neutral source. Do not edit this file. -->\n"
        f"# {title}\n\n"
        f"Source capability: `{source_id}`\n\n"
        f"Packaged contract: `{packaged_contract}`\n\n"
        f"Qualification receipt: `../contracts/qualification-receipts/{source_id}.json`\n\n"
        "## Machine boundary\n\n"
        "```json\n"
        + json.dumps(details, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "## Platform-neutral operation\n\n"
        + rewritten_operation
    )
    return body.encode("utf-8")
