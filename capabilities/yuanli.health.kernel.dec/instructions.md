# Decision Candidate Kernel

## Purpose

Select at most one non-clinical primary bottleneck from supplied candidate-to-evidence links. The machine contract is [`contract.json`](contract.json); outputs conform to `typed-candidate-envelope-v1`.

## Input contract

Accept an ordered evidence catalog and ordered candidates. Every candidate declares `candidate_kind=non_clinical`, an ID matching `CAND-###-[A-Z]`, a label from the exact allowlist `abstract_candidate_alpha|abstract_candidate_beta|abstract_candidate_gamma`, supplied evidence references, and dependency blockers. Request type is one of `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim`; risk flags are limited to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Return one DEC typed candidate envelope plus zero or one primary candidate ID and no more than two dependency blocker IDs. Selection follows eligible input order and remains a discussion candidate.

## Procedure

1. Apply the clinical and emergency Authority gates before selection.
2. Block selection when contradictory evidence is unresolved or the request crosses the First Health Session boundary.
3. Reject candidates whose linked evidence is missing, contradictory, or unverified.
4. Select the first remaining candidate and copy at most its first two blockers.

## Authority and privacy boundaries

The subject is final authority for non-clinical candidates; clinicians are final for RED clinical gates. AI, devices, automation, and Router are non-final. Repository PHI is forbidden, and the runtime uses no persistence or logs.

## Stop and escalation rules

Diagnosis, medication-change, and clinical-risk requests stop at RED and require clinician review. Emergency requests stop at RED and direct the learner to local emergency services. Missing or contradictory support yields YELLOW and no primary.

## Anti-patterns

- Do not produce a clinical conclusion, prescription, medication instruction, or emergency adjudication.
- Do not emit WPK, ACT, OUT, LRN, or REUSE state.
- Do not fabricate links, choose a second primary, write Canon, persist, or log.
