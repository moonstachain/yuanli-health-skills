# Outcome Review Experience

## Purpose

Produce the bounded yuanli.health.experience.outcome-review discussion candidate defined by [`contract.json`](contract.json). The machine output conforms to `typed-candidate-envelope-v1` and remains non-canonical.

## Input contract

Require supplied opaque `act_candidate_id` and `observation_reference`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit an opaque OUT candidate in `outcome_candidate_ready` state without LRN or outcome claims. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate ACT and observation prerequisites.
2. Keep observation provenance explicit.
3. Construct an OUT candidate only.
4. Preserve uncertainty and non-claims.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop without either prerequisite or at clinical/emergency gates. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not claim effectiveness or a real outcome.
- Do not silently emit LRN.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
