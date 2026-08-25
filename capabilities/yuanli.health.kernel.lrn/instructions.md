# Learning Candidate Kernel

## Purpose

Produce the bounded yuanli.health.kernel.lrn discussion candidate defined by [`contract.json`](contract.json). Successful results use the top-level `full-suite-candidate-v1` schema; the nested `envelope` conforms to `typed-candidate-envelope-v1`. The result remains non-canonical.

## Input contract

Require one supplied opaque `out_candidate_id`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit a deterministic opaque `lrn_candidate_id` in `learning_candidate_ready` state. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate the OUT prerequisite.
2. Preserve its supplied reference as known.
3. Keep uncertainty explicit.
4. Emit only an LRN candidate.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop when OUT is absent. Clinical or emergency requests escalate. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not learn directly from ACT.
- Do not publish or reuse the candidate.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
