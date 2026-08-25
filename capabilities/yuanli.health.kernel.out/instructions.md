# Outcome Candidate Kernel

## Purpose

Produce the bounded yuanli.health.kernel.out discussion candidate defined by [`contract.json`](contract.json). The machine output conforms to `typed-candidate-envelope-v1` and remains non-canonical.

## Input contract

Require supplied opaque `act_candidate_id` and `observation_reference`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit a deterministic opaque `out_candidate_id` in `outcome_candidate_ready` state without a health-outcome claim. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate both prerequisite artifacts.
2. Keep the observation as supplied evidence rather than an adjudicated truth.
3. Preserve unknowns and assumptions.
4. Emit only an OUT candidate.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop without both ACT and observation. Clinical or emergency requests escalate. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not claim a real health outcome.
- Do not emit LRN.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
