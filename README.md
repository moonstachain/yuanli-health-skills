# 原力健康 Skill Core v0.1.0

Yuanli Health Skill Core v0.1.0: 以90天为周期，持续改善创始人的恢复力，让健康成为长期创业的底盘。

Platform-neutral source for 16 qualified synthetic-only Yuanli Health
capabilities and a deterministic Codex adapter. Current state:
`QUALIFIED_SOURCE_CANDIDATE`.

The founder-facing journey is 创始人健康起盘 → 90天恢复力战役 → 五分钟每周校准 → 专业就医准备 → 30/60/90证据复盘 → 个人健康打法. A `90天起盘` request without a supplied opaque DEC begins at 创始人健康起盘 and stops at `decision_candidate_ready`; it may discuss a qualitative, evidence-linked Recovery Compass direction, one bottleneck candidate, one non-clinical action candidate, explicit evidence/unknowns, and escalation, but never fabricates WPK or ACT. The public Core remains synthetic-only, ephemeral, non-clinical, and score-free.

This is a qualified source candidate, not released, published, deployed,
Registry-admitted, clinically validated, or approved by the later Health Source
Human Gate. It is not the Health Domain Canon, a clinical authority, a personal
health datastore, or a runtime outcome ledger. Real or re-identifiable health
data must never enter repository files, receipts, fixtures, or workflow logs.

## Deterministic Codex candidate

Generate the candidate package and release metadata:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_codex_adapter.py
```

Verify that committed output is byte-exact and validate the complete candidate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_codex_adapter.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_codex_adapter.py --check-repository
PYTHONDONTWRITEBYTECODE=1 python3 scripts/scan_public_content.py --check-current --check-history
```

Candidate installation is by the verified directory
`dist/codex/yuanli-health` only. Verify `SHA256SUMS` and the repository validator
before copying that directory into a Codex skills location. No installer,
network call, telemetry, persistence, or runtime logging is provided.

All generated receipts are synthetic qualification non-claims. The package
cannot mutate Canon, assign Registry IDs, claim Human acceptance, publish a
release, diagnose, prescribe, change medication, claim a health outcome or
clinical effectiveness, or claim human runtime observation.
