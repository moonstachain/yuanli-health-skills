# Weekly Health Checkpoint Experience

## Purpose

Produce the bounded yuanli.health.experience.weekly-health-checkpoint discussion candidate defined by [`contract.json`](contract.json). Successful results use the top-level `full-suite-candidate-v1` schema; the nested `envelope` conforms to `typed-candidate-envelope-v1`. The result remains non-canonical.

## Input contract

Require one supplied opaque `act_candidate_id`; an observation reference is optional. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit `checkpoint_candidate_ready` while preserving supplied references and emitting no OUT/LRN. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate ACT.
2. Retain an optional supplied observation without adjudicating it.
3. Keep uncertainty explicit.
4. Return a checkpoint candidate only.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop without ACT or at any clinical/emergency gate. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not silently construct OUT.
- Do not infer adherence, effectiveness, or learning.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
