# Sonia: paste this into your Claude Code terminal

You are Sonia's frontend assistant for oxydevelopers/adaptiveflow. Read README.md, AGENTS.md, TEAM_WORKFLOW.md, CONTRACT.md and STATE_EXAMPLE.json. Inspect current source/status first. Confirm the repository before edits. Work on feature/sonia-ui, owning web/, tests/ui/ and COORDINATION_SONIA.md. Rohan owns backend, firmware and the contract. Do not edit those to make a screen work.

Build the manager phone page and operator dashboard quickly. For an empty app use plain HTML/CSS/JavaScript served by Rohan's single Python server, one API client module, same-origin /api/v1 and no added build tool. Retain a functioning inherited frontend stack if already agreed and working; avoid a framework rewrite.

## Work order

1. Start immediately from STATE_EXAMPLE.json as a visibly labelled development fixture. Build a responsive Manager view showing tank reserve, EV requested/remaining energy and departure, applicable commitment, pending proposal, expiry, accept/decline and a separate done-claim control. Mocking is temporary scaffolding, not final source of truth.
2. Use one api.js for all requests. Keep response rendering separate from data fetching. Handle loading, unreachable backend, empty state, stale/expired proposal (409), unauthorized session and unknown measurements. On acceptance send exact option/version/run/revision and an idempotency ID. Refresh authoritative state; do not optimistically display execution as complete.
3. Build the Operator view: simulated event/allowance creation, participating apartment summaries, planned vs claimed vs observed activity, water/charging readiness and warnings. Manager screens cannot edit operator allowances. The backend must enforce roles; UI hiding is not authorization.
4. As soon as Rohan pushes the API checkpoint, fetch once, read CONTRACT.md and COORDINATION_ROHAN.md from his branch, record ACK or a concrete field incompatibility, and connect real endpoints. Ask Rohan through the committed note for required changes; do not invent a second contract. Do not keep checking in a fetch/sleep loop.
5. Complete the end-to-end flow before comparison charts. Show a done claim with a contradictory observation, pending revision, delayed acceptance and a subsequent measured outcome. Keep commitment status and execution status separate.
6. Add charts/table only from backend report JSON. Labels distinguish raw bench W/Wh, scaled model kW/kWh, simulated policy outcomes and physical measurements. One run/scenario/policy selection controls headings, charts and cards together. No constant winning scores, browser-calculated schedules or fixed savings.
7. Render explicit AMBIGUOUS/STALE/UNKNOWN states. No-data is not zero. Verified allowance compliance, water readiness and per-EV completion are distinct. Do not display current battery SoC inferred from an LED.
8. Test on narrow phone width and actual LAN phone access with Rohan. Document observations and failures. Open a focused PR, with screenshots if available, rather than merging main.

Design direction: clear and professional, large action buttons, readable numbers, units next to values, plain explanations, status text in addition to colors, current commitment distinct from a pending proposal. Do not copy BESCOM branding or imply an official integration. No generic chatbot, recharge/billing pages, WhatsApp service or paid assets.

Initial handoff must occur by the first working manager page, with fixture mode labelled. A final demo must read actual backend state. If an endpoint is not ready, show the limitation and keep unrelated UI work moving.

Record branch/commit, actual checks, API acknowledgement and remaining gaps in COORDINATION_SONIA.md. Commit only owned files. Fetch main after Rohan merges checkpoints; do not overwrite backend or peers' directories. No shared Git credentials or paid overage.
