---
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

- 创始人健康起盘 / First Health Session: read [the exact member reference](references/yuanli.health.experience.first-health-session.md).
- 90天恢复力战役 / 90-Day Health Experiment: read [the exact member reference](references/yuanli.health.experience.ninety-day-health-experiment.md).
- 五分钟每周校准 / Weekly Health Checkpoint: read [the exact member reference](references/yuanli.health.experience.weekly-health-checkpoint.md).
- 专业就医准备 / Doctor Visit Preparation: read [the exact member reference](references/yuanli.health.experience.doctor-visit-prep.md).
- 30/60/90证据复盘 / Outcome Review: read [the exact member reference](references/yuanli.health.experience.outcome-review.md).
- 个人健康打法 / Learning Reuse: read [the exact member reference](references/yuanli.health.experience.learning-reuse.md).

A founder request for `90天起盘` without a supplied opaque `decision_candidate_id` routes to 创始人健康起盘 / First Health Session. Present one qualitative, evidence-linked Recovery Compass direction, not an aggregate health/readiness/wellness/performance score; name one current bottleneck candidate and one non-clinical action candidate only when evidence and the Authority gate permit. Make evidence, unknowns, assumptions, and escalation explicit. Stop at `decision_candidate_ready`: do not fabricate WPK or ACT. Only after a supplied opaque DEC may `90天起盘` continue to 90天恢复力战役 / the 90-Day Health Experiment, which orders WPK before ACT and emits no OUT.

The founder journey may explain three 30-day phases — 起盘与稳定, 实验与校准, 证据复盘与沉淀 — but they are not a formal plan before WPK/ACT prerequisites exist. Recovery Compass is a transparent discussion direction, never a diagnosis or score.

If none matches, return no route. Never fall back to Kernel or Meta and never decide health priority. Kernel and Meta are direct/internal only; read their reference only when the request explicitly names that capability and supplies its prerequisites:

- `yuanli.health.kernel.ctx`: [member reference](references/yuanli.health.kernel.ctx.md)
- `yuanli.health.kernel.evd`: [member reference](references/yuanli.health.kernel.evd.md)
- `yuanli.health.kernel.dec`: [member reference](references/yuanli.health.kernel.dec.md)
- `yuanli.health.kernel.wpk`: [member reference](references/yuanli.health.kernel.wpk.md)
- `yuanli.health.kernel.act`: [member reference](references/yuanli.health.kernel.act.md)
- `yuanli.health.kernel.out`: [member reference](references/yuanli.health.kernel.out.md)
- `yuanli.health.kernel.lrn`: [member reference](references/yuanli.health.kernel.lrn.md)
- `yuanli.health.meta.build`: [member reference](references/yuanli.health.meta.build.md)
- `yuanli.health.meta.review`: [member reference](references/yuanli.health.meta.review.md)
- `yuanli.health.meta.qualify`: [member reference](references/yuanli.health.meta.qualify.md)

## Execute the selected contract

Read only the selected reference and its packaged JSON contract. Preserve supplied facts with evidence references, explicit unknowns and assumptions, final Authority, candidate state, escalation/guardrail, `canonical_write=false`, and `persistence=none`. Do not invent IDs, evidence, receipts, unknown labels, machine fields, or missing prerequisites.

- First Health Session ends at `decision_candidate_ready`; it emits no WPK or ACT.
- OUT requires ACT plus observation; LRN requires OUT; REUSE requires LRN and distinct Task-2 preload/use receipts.
- DEC selects zero or one primary bottleneck and at most two blockers.
- Doctor Visit Prep prepares only supplied questions. Delegate provider selection, booking, pricing, and payment to `yuanli-medical-appointment-operator`; perform none here.
- Meta never self-admits, assigns Registry IDs, claims Human acceptance, tags, releases, publishes, or deploys.

If strict input cannot satisfy the selected member contract, stop at that contract's stable error boundary instead of fabricating an aggregate result. Qualification is synthetic-only: never claim a health outcome, clinical effectiveness, runtime observation, Canon mutation, Registry admission, or publication.
