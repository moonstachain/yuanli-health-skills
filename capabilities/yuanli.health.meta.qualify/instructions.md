# Synthetic Qualification Meta Skill

## Purpose

Produce the bounded yuanli.health.meta.qualify discussion candidate defined by [`contract.json`](contract.json). Successful results use the top-level `full-suite-candidate-v1` schema; the nested `envelope` conforms to `typed-candidate-envelope-v1`. The result remains non-canonical.

## Input contract

Require `review_candidate_id` and integer `synthetic_case_count>=10`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit `qualified_candidate_ready` as synthetic-only qualification; never human acceptance, admission, or release. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate independent review and count prerequisites.
2. Apply only the synthetic qualification threshold.
3. Preserve supplied facts and uncertainty.
4. Return a non-release qualification candidate.

## Authority and privacy boundaries

Final authority is `system_contract` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop below ten synthetic cases, without review, or at clinical/emergency gates. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not claim human acceptance or runtime observation.
- Do not assign a Registry ID, self-admit, or release.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
