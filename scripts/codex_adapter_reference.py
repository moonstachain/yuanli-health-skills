"""Pure deterministic rendering for generated Codex Markdown."""

import hashlib
import json
import re
from typing import Any


_CONTRACT_LABEL = "`contract.json`"
_CONTAINER_PREFIX = re.compile(r"^[ \t]{0,3}(?:>|[-+*][ \t]+|[0-9]+[.)][ \t]+)")

_EXPERIENCE_ROUTES = (
    ("first health session / 首次健康会话", "yuanli.health.experience.first-health-session"),
    ("90-day health experiment / 90 天健康实验", "yuanli.health.experience.ninety-day-health-experiment"),
    ("weekly health checkpoint / 每周健康检查点", "yuanli.health.experience.weekly-health-checkpoint"),
    ("doctor visit preparation / 问诊准备", "yuanli.health.experience.doctor-visit-prep"),
    ("outcome review / 结果复盘", "yuanli.health.experience.outcome-review"),
    ("learning reuse / 学习复用", "yuanli.health.experience.learning-reuse"),
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
            line_start = instructions.rfind("\n", 0, index) + 1
            line_prefix = instructions[line_start:index]
            if (
                (index > 0 and instructions[index - 1] == "!")
                or line_prefix.startswith(("    ", "\t"))
                or _CONTAINER_PREFIX.match(line_prefix)
            ):
                raise ValueError(f"source Markdown link policy: contract link container forbidden: {source_id}")
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


def validate_instruction_projection(source_id: str, instructions: str, contract_target: str) -> str:
    """Validate an emitted instruction projection and return its exact text."""
    return _closed_instruction_projection(
        source_id,
        instructions,
        contract_target=contract_target,
    )


def _rewrite_single_source_contract_link(source_id: str, instructions: str) -> str:
    return _closed_instruction_projection(
        source_id,
        instructions,
        contract_target="contract.json",
        replacement_target=f"../contracts/capabilities/{source_id}.json",
    )


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
description: Use when handling synthetic Yuanli Health candidate work, including First Health Session, health experiments or checkpoints, doctor-visit preparation, outcome review, learning reuse, and explicit internal Kernel or Meta requests.
---

# Yuanli Health

Use this adapter to select one bounded source capability and preserve its machine contract. Inputs stay synthetic and in memory. Never copy real or re-identifiable health material into repository files, receipts, logs, or generated references.

## Decide before routing

Clinical diagnosis, prescription, medication change, chest-pain or urgent/emergency risk never become model conclusions. Stop with concise bilingual guidance to contact a clinician or local emergency services; do not create WPK/ACT or protect a deadline. Refuse persistence and logging even when an owner requests them.

Route only these user JTBDs to Experiences:

{route_lines}

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
    rewritten = _rewrite_single_source_contract_link(source_id, instructions)
    packaged_contract = f"../contracts/capabilities/{source_id}.json"
    title = rewritten.splitlines()[0].removeprefix("# ")
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
        + rewritten.strip()
        + "\n"
    )
    return body.encode("utf-8")
