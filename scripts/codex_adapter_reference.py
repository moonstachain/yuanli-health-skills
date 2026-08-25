"""Pure deterministic rendering for generated Codex Markdown."""

import json
import re
from typing import Any


_SOURCE_CONTRACT_LINK = re.compile(
    r"(?<!!)\[(?P<label>[^]\r\n]+)\]\((?P<target>[^()\r\n]+)\)"
)

_EXPERIENCE_ROUTES = (
    ("first health session / 首次健康会话", "yuanli.health.experience.first-health-session"),
    ("90-day health experiment / 90 天健康实验", "yuanli.health.experience.ninety-day-health-experiment"),
    ("weekly health checkpoint / 每周健康检查点", "yuanli.health.experience.weekly-health-checkpoint"),
    ("doctor visit preparation / 问诊准备", "yuanli.health.experience.doctor-visit-prep"),
    ("outcome review / 结果复盘", "yuanli.health.experience.outcome-review"),
    ("learning reuse / 学习复用", "yuanli.health.experience.learning-reuse"),
)


def _escaped(content: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and content[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def mask_markdown_code_literals(content: str) -> str:
    """Mask closed code spans/fences while preserving offsets and newlines."""
    masked = list(content)
    index = 0
    fence: tuple[str, int] | None = None
    while index < len(content):
        line_start = content.rfind("\n", 0, index) + 1
        at_line_prefix = content[line_start:index].strip(" ") == ""
        if at_line_prefix and index - line_start <= 3 and content[index] in {"`", "~"}:
            marker = content[index]
            run_end = index
            while run_end < len(content) and content[run_end] == marker:
                run_end += 1
            run_length = run_end - index
            if run_length >= 3:
                if fence is None:
                    fence = (marker, run_length)
                elif fence[0] == marker and run_length >= fence[1]:
                    fence = None
                line_end = content.find("\n", run_end)
                stop = len(content) if line_end < 0 else line_end
                for position in range(index, stop):
                    masked[position] = " "
                index = stop
                continue
        if fence is not None:
            if content[index] != "\n":
                masked[index] = " "
            index += 1
            continue
        if content[index] == "`" and not _escaped(content, index):
            run_end = index
            while run_end < len(content) and content[run_end] == "`":
                run_end += 1
            marker = content[index:run_end]
            close = content.find(marker, run_end)
            if close < 0:
                raise ValueError("source Markdown link policy: unterminated code span")
            for position in range(index, close + len(marker)):
                if content[position] != "\n":
                    masked[position] = " "
            index = close + len(marker)
            continue
        index += 1
    if fence is not None:
        raise ValueError("source Markdown link policy: unterminated code fence")
    return "".join(masked)


def _rewrite_single_source_contract_link(source_id: str, instructions: str) -> str:
    normalized = instructions.replace("\r\n", "\n").replace("\r", "\n")
    links = tuple(_SOURCE_CONTRACT_LINK.finditer(normalized))
    if len(links) != 1 or links[0].group("target") != "contract.json":
        raise ValueError(f"source Markdown link policy: expected one contract.json link: {source_id}")
    link = links[0]
    masked_link = normalized[:link.start()] + " " * (link.end() - link.start()) + normalized[link.end():]
    active = mask_markdown_code_literals(masked_link)
    if re.search(r"(?<!\\)!?\[|(?<!\\)\]", active):
        raise ValueError(f"source Markdown link policy: unsupported bracket syntax: {source_id}")
    for autolink in re.finditer(r"(?<!\\)<([^>\r\n]+)>", active):
        body = autolink.group(1)
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", body) or re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+",
            body,
        ):
            raise ValueError(f"source Markdown link policy: autolink forbidden: {source_id}")
    packaged_contract = f"../contracts/capabilities/{source_id}.json"
    return normalized[:link.start("target")] + packaged_contract + normalized[link.end("target"):]


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
