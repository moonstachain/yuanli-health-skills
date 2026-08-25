# Capability Build Meta Skill

## Purpose

Produce the bounded yuanli.health.meta.build discussion candidate defined by [`contract.json`](contract.json). Successful results use the top-level `full-suite-candidate-v1` schema; the nested `envelope` conforms to `typed-candidate-envelope-v1`. The result remains non-canonical.

## Input contract

Require one supplied opaque `draft_capability_id`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit an opaque `built_candidate_id` in `build_candidate_ready` state. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate the draft prerequisite.
2. Build a candidate without qualifying it.
3. Preserve all supplied epistemic fields.
4. Return a non-release build candidate.

## Authority and privacy boundaries

Final authority is `system_contract` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop without a draft or at clinical/emergency gates. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not self-review or self-qualify.
- Do not assign a Registry ID, admit, or release.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
