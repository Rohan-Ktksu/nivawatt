# Rohan: paste this into your Claude Code terminal

You are implementing the core of oxydevelopers/adaptiveflow with Rohan. Read README.md, AGENTS.md, TEAM_WORKFLOW.md, CONTRACT.md, TEST_AND_DEMO.md and current coordination files. Inspect Git status, actual source and any existing instructions first. Confirm that origin is oxydevelopers/adaptiveflow; do not modify CampusResolve or point an unrelated checkout at this repository.

Work on feature/rohan-core. Own backend, scheduling, simulation, firmware review, shared configuration, CONTRACT.md and tests/core. Sonia owns web/ and her UI tests. Teammate 3 owns hardware preparation, calibration notes, scenarios and manual validation. Do not overwrite their files.

Target a usable software demo in a focused 6–8-hour session, with the first phone-to-backend integration inside two hours. This is a target, not permission to invent completed work. Start coding after a brief source inspection; do not reopen broad idea research or produce another architecture essay.

## Implement in this order

1. Establish .gitignore and the smallest local server skeleton. Inspect accessible OutageReady-FlexProof source for reusable controller/plant code; do not wait for unavailable old-repository access. No entire-directory replacement. For an empty implementation choose one FastAPI service, SQLite and plain web assets served on the same origin, port 8780 configurable. Document actual installation/startup commands once tested. No application model APIs or paid services.
2. Implement contract-v0.1 P0 endpoints with real persisted state. Supply a callable deterministic planner, one apartment, one pump and one EV request, a mass-balanced plant and explicit simulated clock. Keep raw hardware and apartment-model units separate. Initially produce one genuinely feasible option or an explicit shortfall. Do not block on MILP adoption if a bounded look-ahead/rule scheduler can establish the flow; label the implemented method honestly.
3. Wire proposal delivery, exact-version acceptance, expiry and claimed execution. Implement stale-version/run conflicts, idempotent retries and server-side role/apartment scope. No user-management product is needed; use a lightweight explicitly local-demo session design. Acceptance does not actuate physical switches.
4. Implement observed execution and revision from current evidence. Missing action, contradictory claim and stale data are explicit outcomes. A new proposal does not erase accepted history or change physical load before human action. Both replanners use the same actual tank observations.
5. Hand Sonia working /health, /state and proposal/claim endpoints immediately; update your coordination file, commit and push. Open a small PR. Do not wait for firmware, all baselines or perfect UI. Rohan reviews/merges checkpoints; never merge automatically without his authorization.
6. Add telemetry parsing and one physical-input adapter if components exist. Teammate 3 supplies exact parts/calibration; review firmware and signal-voltage compatibility before use. With a shared meter, ambiguous pump/EV attribution stays UNKNOWN. With two channels, integrate measured branch energy using actual elapsed time. If hardware is not ready, keep the synthetic demo usable and identify the limitation.
7. Add paired acknowledgement-vs-measured runs and simple-cap/open-loop/uncoordinated baselines, then a second simulated apartment if time. Metrics come from the evaluator and actual traces, never UI constants. Policies receive causal inputs; alternative physical outcomes are simulated shadow results unless independently measured.
8. Finish with matching scenarios, explicit cases where measured feedback ties/loses, evidence export and a reproducible startup/rehearsal path. No BESS, ML training, WhatsApp API, distributed solver or cloud deployment in this sprint.

## Required meaningful checks

- Tank balance and EV progress respect units, availability and physical bounds; individual shortfalls are not hidden.
- Accepting expired/wrong-version proposals fails; duplicate clicks do not duplicate commitments.
- A done tap without action never creates observed execution.
- Revision pending/expired does not apply a proposed action. Power loss takes precedence over planned ON states.
- Missing/ambiguous readings cannot establish complete compliance or exact branch delivery.
- Acknowledgement and measured methods share scheduler, requirements, tank observations and human-response assumptions. Perfect execution should be able to produce a tie.
- Runtime and savings are measured, not promised by the planning document.

Keep each handoff small. Record actual commands/results and known gaps in COORDINATION_ROHAN.md. Before final PR, run meaningful core checks and git diff --check; do not stage runtime data, secrets, another person's files or environments.

Your first output should be a short implementation decision and immediate work, followed by a pushed core checkpoint and exact instructions Sonia can run. Continue within the authorized scope without asking Rohan to approve routine reversible choices.
