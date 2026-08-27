# Context Candidate Kernel

## Purpose

Normalize only supplied goal, constraints, declared unknowns, and assumptions into a CTX candidate. The machine contract is [`contract.json`](contract.json); outputs conform to `typed-candidate-envelope-v1`.

## Input contract

Accept inert JSON containing an abstract goal or an explicit missing goal, string constraints, declared unknowns, and assumptions. Treat every value as supplied candidate material, never as verified health state.

## Output contract

Return one CTX typed candidate envelope. Every known goal or constraint retains a stable input reference. Preserve all declared unknowns and assumptions. A missing goal remains an unknown.

## Procedure

1. Check the declared inert-JSON shape.
2. Copy the supplied goal and constraints without interpretation.
3. Keep unknowns and assumptions in their distinct envelope fields.
4. Emit a non-canonical, non-persistent candidate.

## Authority and privacy boundaries

The subject is final authority. AI is assistive; devices are evidence sources; automation and Router are non-final. Repository PHI is forbidden, and the runtime uses no persistence or logs.

## Stop and escalation rules

Stop candidate normalization when the input shape is invalid. If the goal is absent, request subject context and keep `goal_not_supplied` explicit. Clinical or emergency requests pass to the DEC safety gate without interpretation.

## Anti-patterns

- Do not diagnose, prioritize, rank, select a bottleneck, or create evidence.
- Do not promote assumptions to known facts.
- Do not write Canon, files, logs, telemetry, or external services.
