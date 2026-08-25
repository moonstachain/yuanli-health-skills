# First Health Session Experience

## Purpose

Orchestrate the platform-neutral `CTX -> EVD -> DEC` Gold Slice into a `decision_candidate_ready` bundle. The machine contract is [`contract.json`](contract.json); every stage output conforms to `typed-candidate-envelope-v1`.

## Input contract

Accept one inert, explicitly synthetic First Health Session case with abstract context, evidence, decision candidates, request type, and risk flags. The Experience-only Router must select this source ID before execution.

## Output contract

Return `first-health-session-bundle-v1` with stage order, three typed envelopes, ordered evidence catalog, decision candidate, five-field learner view, Authority gate, and explicit non-claims. The result never contains a formal WPK, ACT, OUT, LRN, or REUSE claim.

## Procedure

1. Route only `first_health_session` to this Experience source.
2. Normalize CTX without interpretation.
3. Organize EVD without prioritization.
4. Apply DEC evidence and Authority gates.
5. Render one non-clinical learner view and clear ephemeral state.

## Authority and privacy boundaries

The subject remains final authority outside RED clinical gates. AI is assistive; devices are evidence sources; automation and Router are non-final. Repository PHI is forbidden. Execution is ephemeral, non-persistent, silent, and host-neutral.

## Stop and escalation rules

Return stable validation errors for malformed inert JSON. Preserve missing evidence and contradictions at YELLOW. Stop clinical and emergency paths at RED with concise Chinese/English clinician or emergency guidance.

## Anti-patterns

- Do not route to a Kernel or Meta capability or let Router decide health priority.
- Do not call the action candidate a formal ACT or treatment plan.
- Do not claim outcome, learning, reuse, release, Canon mutation, persistence, or logging.
