# Action Candidate Kernel

## Purpose

Produce the bounded yuanli.health.kernel.act discussion candidate defined by [`contract.json`](contract.json). Successful results use the top-level `full-suite-candidate-v1` schema; the nested `envelope` conforms to `typed-candidate-envelope-v1`. The result remains non-canonical.

## Input contract

Require one supplied opaque `wpk_candidate_id`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit a deterministic opaque `act_candidate_id` in `action_candidate_ready` state. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate strict inert input and closed vocabularies.
2. Require WPK before constructing ACT.
3. Preserve supplied epistemic fields exactly.
4. Emit only the ACT candidate.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop when WPK is absent. Clinical or emergency requests escalate without an action candidate. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not create ACT directly from DEC.
- Do not infer OUT or LRN.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
