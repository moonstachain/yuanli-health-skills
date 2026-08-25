# Evidence Organization Kernel

## Purpose

Organize supplied evidence for inspection without deciding health priority. The machine contract is [`contract.json`](contract.json); outputs conform to `typed-candidate-envelope-v1`.

## Input contract

Accept ordered inert-JSON evidence entries with a stable reference, abstract fact, `self_report|wearable|clinical` source, and `supports|contradicts|unverified` status.

## Output contract

Return one EVD typed candidate envelope and preserve the complete evidence catalog in its original order. Supported facts retain their references; contradictory and unverified material stays explicit as unresolved.

## Procedure

1. Validate each evidence entry and unique reference.
2. Preserve entry order and source/status labels byte-for-byte.
3. Link supported facts to their supplied references.
4. Surface every contradiction and unverified entry as unresolved.

## Authority and privacy boundaries

The system contract governs evidence organization only. AI is assistive; devices supply evidence but never authority; automation and Router are non-final. Repository PHI is forbidden, and the runtime uses no persistence or logs.

## Stop and escalation rules

Stop on malformed evidence. Keep insufficient evidence at YELLOW. Route clinical-versus-wearable conflict to clinician review at RED without forming a conclusion.

## Anti-patterns

- Do not add priority, rank, a primary bottleneck, or a health-selection decision.
- Do not hide contradictory or unverified entries.
- Do not invent facts, diagnose, write Canon, persist, or log.
