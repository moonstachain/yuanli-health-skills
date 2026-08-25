# Yuanli Health Skills

Platform-neutral source for 16 qualified synthetic-only Yuanli Health
capabilities and a deterministic Codex adapter. Current state:
`QUALIFIED_SOURCE_CANDIDATE`.

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
