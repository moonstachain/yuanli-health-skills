---
name: yuanli-health
description: Use when handling synthetic Yuanli Health candidate work, including First Health Session, health experiments or checkpoints, doctor-visit preparation, outcome review, learning reuse, and explicit internal Kernel or Meta requests.
---

# Yuanli Health

Use this adapter to select one bounded source capability and preserve its machine contract. Inputs stay synthetic and in memory. Never copy real or re-identifiable health material into repository files, receipts, logs, or generated references.

## Decide before routing

Clinical diagnosis, prescription, medication change, chest-pain or urgent/emergency risk never become model conclusions. Stop with concise bilingual guidance to contact a clinician or local emergency services; do not create WPK/ACT or protect a deadline. Refuse persistence and logging even when an owner requests them.

Route only these user JTBDs to Experiences:

- first health session / 首次健康会话: read [the exact member reference](references/yuanli.health.experience.first-health-session.md).
- 90-day health experiment / 90 天健康实验: read [the exact member reference](references/yuanli.health.experience.ninety-day-health-experiment.md).
- weekly health checkpoint / 每周健康检查点: read [the exact member reference](references/yuanli.health.experience.weekly-health-checkpoint.md).
- doctor visit preparation / 问诊准备: read [the exact member reference](references/yuanli.health.experience.doctor-visit-prep.md).
- outcome review / 结果复盘: read [the exact member reference](references/yuanli.health.experience.outcome-review.md).
- learning reuse / 学习复用: read [the exact member reference](references/yuanli.health.experience.learning-reuse.md).

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
