# First Health Session Experience

## Purpose

Orchestrate the platform-neutral `CTX -> EVD -> DEC` Gold Slice into a `decision_candidate_ready` bundle. The machine contract is [`contract.json`](contract.json); every stage output conforms to `typed-candidate-envelope-v1`.

## Founder-facing name

Primary display name: 创始人健康起盘. A founder `90天起盘` request without a supplied opaque DEC starts here, not in the DEC-dependent experiment. The bounded founder context is limited to user-supplied critical-campaign timing, travel/time-zone pressure, workload rhythm, and recovery constraints; never request meeting content or confidential business detail.

## Input contract

Accept one inert, explicitly synthetic First Health Session case with abstract context and evidence. Every decision candidate declares `candidate_kind=non_clinical`, an ID matching `CAND-###-[A-Z]`, and a label from the exact allowlist `abstract_candidate_alpha|abstract_candidate_beta|abstract_candidate_gamma`. Request type is one of `diagnosis|emergency|formal_plan|learning_claim|medication_change|non_clinical|outcome_adjudication|reuse_claim`; risk flags are limited to `clinical_escalation|emergency|guardrail_requested`. The Experience-only Router must select this source ID before execution.

## Output contract

Return `first-health-session-bundle-v1` with stage order, three typed envelopes, ordered evidence catalog, decision candidate, five-field learner view, Authority gate, and explicit non-claims. The learner view presents one qualitative, evidence-linked Recovery Compass direction rather than an aggregate health/readiness/wellness/performance score; it names at most one current bottleneck candidate and one non-clinical action candidate when the evidence and Authority gate permit, while keeping evidence, unknowns, assumptions, and escalation explicit. The result never contains a formal WPK, ACT, OUT, LRN, or REUSE claim.

## Procedure

1. Route only `first_health_session` to this Experience source.
2. Normalize CTX without interpretation.
3. Organize EVD without prioritization.
4. Apply DEC evidence and Authority gates.
5. Render one non-clinical learner view and clear ephemeral state. Stop at `decision_candidate_ready`; do not fabricate WPK or ACT.

## Authority and privacy boundaries

The subject remains final authority outside RED clinical gates. AI is assistive; devices are evidence sources; automation and Router are non-final. Repository PHI is forbidden. Execution is ephemeral, non-persistent, silent, and host-neutral.

## Stop and escalation rules

Return stable validation errors for malformed inert JSON. Preserve missing evidence and contradictions at YELLOW. Stop clinical and emergency paths at RED with concise Chinese/English clinician or emergency guidance.

## Anti-patterns

- Do not route to a Kernel or Meta capability or let Router decide health priority.
- Do not call the action candidate a formal ACT or treatment plan.
- Do not claim outcome, learning, reuse, release, Canon mutation, persistence, or logging.
