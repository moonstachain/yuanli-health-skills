# Learning Reuse Experience

## Purpose

Produce the bounded yuanli.health.experience.learning-reuse discussion candidate defined by [`contract.json`](contract.json). The machine output conforms to `typed-candidate-envelope-v1` and remains non-canonical.

## Input contract

Require `lrn_candidate_id` plus distinct non-empty `task2_preload_receipt` and `task2_use_receipt`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit `reuse_candidate_ready` without promotion, admission, or release. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate LRN.
2. Require independent preload and use receipts.
3. Preserve all receipts as supplied facts.
4. Emit only a reuse discussion candidate.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop if either receipt is missing, empty, or equal, or at clinical/emergency gates. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not treat one receipt as two independent observations.
- Do not publish or canonize learning.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
