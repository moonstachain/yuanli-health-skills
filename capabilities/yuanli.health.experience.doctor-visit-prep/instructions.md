# Doctor Visit Preparation Experience

## Purpose

Produce the bounded yuanli.health.experience.doctor-visit-prep discussion candidate defined by [`contract.json`](contract.json). Successful results use the top-level `full-suite-candidate-v1` schema; the nested `envelope` conforms to `typed-candidate-envelope-v1`. The result remains non-canonical.

## Founder-facing name

Primary display name: 专业就医准备. It organizes only supplied abstract questions for a clinician; diagnosis, prescription, medication change, and urgent risk stay outside recovery experiments and at the concise bilingual RED escalation boundary.

## Input contract

Require a non-empty list of supplied abstract `visit_questions`. Request type is closed to `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim|appointment_logistics`; risk flags are closed to `clinical_escalation|emergency|guardrail_requested`.

## Output contract

Emit only the supplied questions in `visit_prep_candidate_ready`; clinical requests add RED bilingual guardrails, and `appointment_logistics` delegates explicitly. Canonical write, persistence, Registry admission, release, health-outcome claims, clinical-effectiveness claims, and runtime-observed claims are always false.

## Procedure

1. Validate abstract question tokens.
2. Copy questions without answering them.
3. For clinical requests add clinician/emergency guardrails.
4. For appointment logistics delegate to `yuanli-medical-appointment-operator` without booking state.

## Authority and privacy boundaries

Final authority is `subject` under the machine contract. AI is assistive; device evidence, automation, and Router are non-final. Repository PHI is forbidden. Runtime is ephemeral with no persistence and no logs.

## Stop and escalation rules

Stop rather than diagnose, prescribe, change medication, select a provider, book, or pay. Emergency risk directs the learner to local emergency services; other clinical gates require clinician review.

## Anti-patterns

- Do not answer the supplied questions.
- Do not copy provider, booking, payment, or appointment state.
- Do not fabricate known facts, hide unknowns or assumptions, write Canon, persist, log, admit, or release.
