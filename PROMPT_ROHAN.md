# Rohan: Claude Code implementation prompt v0.2

You are implementing NivaWatt in oxydevelopers/nivawatt on feature/rohan-core. Read README.md, AGENTS.md, NIVAWATT_BUILD_NOW.md, TEAM_WORKFLOW.md, CONTRACT.md, TEST_AND_DEMO.md and current coordination files. Inspect current source/Git status before editing. Do not alter the unrelated CampusResolve checkout.

Own forecasting/, data ingestion/provenance, backend/, scheduler/, simulation/, firmware/, scripts/, tests/core/, dependencies and shared integration. Sonia owns web/ and UI tests. Teammate 3 owns hardware/calibration/validation evidence. Preserve those boundaries.

## Execute in this order

1. Publish the smallest runnable local foundation, ignored credentials/runtime files and v0.2 JSON handoff. Use one service/SQLite/plain web assets for a fresh build; retain verified existing code when suitable. Give Sonia a stable fixture and working API checkpoint early.
2. Validate actual regional-demand data, its scope, coverage, time alignment and attribution. Candidate KPTCL-derived hourly demand is Karnataka state load, not a BESCOM feeder. Handle report-hour duplicates/missing rows and publication-lag assumptions. Record exact dates/fingerprint.
3. Implement the previous-week same-hour baseline and a saved 24-hour forecast. Use chronological testing. Derive the prototype top-three peak-hour advisory, with explicit operator approval. Add one small local regression after the baseline works; no deep-learning/LLM service dependency and no fabricated model confidence.
4. Implement the forecast/advisory additions in CONTRACT.md and include identifiers in manager/operator state. Never translate regional MW automatically into apartment capacity. Keep the configured participating-load allowance separate.
5. Build one apartment and a mass-balanced pump/tank/charging-emulator model, one feasible option or explicit shortfall, persisted exact-version acceptance, expiry, idempotent claims and server-side role/apartment checks. Acceptance does not actuate equipment.
6. Observe execution independently from claims, preserve accepted history, flag unsupported/missing/ambiguous evidence and propose revisions. Both comparison replanners receive available tank observations. A changed proposal does not physically execute or silently become accepted.
7. Hand Sonia the running forecast/advisory and apartment endpoints before firmware or all comparisons are finished. Record actual startup/checks, commit/push owned paths and open a focused PR.
8. Review the exact bench parts and calibration before firmware/adapter use. Pick one initially working USB or Wi-Fi path. Preserve raw bench units, sequence/reboot handling and provenance. A charging load is not a vehicle SoC sensor.
9. Evaluate acknowledgement and measured variants using the same planner and fair causal inputs, plus a sensible demand-cap rule and uncoordinated context. Export actual per-run metrics and shortfalls. Alternative outcomes on one bench are simulated unless independently measured.
10. Freeze features, repair the whole flow, publish reproducible startup/evidence and known limitations. Add the second software apartment only after core/evaluation gates pass.

## Required checks

Chronological leakage and scope; forecast/advisory persistence and authorization; tank/energy/time bounds; false done without action; pump power without water delivery; expired/stale/wrong-run decisions; retries; device reboot/missing/ambiguous data; impossible service requirements; fair comparison and perfect-execution ties; consistent run/revision/report and restart persistence.

Target a first connected software demonstration in a focused session. Hardware and defensible results may take another session. Keep synthetic fallbacks visibly labelled while real-data/hardware gates remain incomplete. No paid services, BESS, FDIA, transformer-health prediction, automatic mains control, unsupported savings or automatic main merge.

Record actual commands/results and peer requests in COORDINATION_ROHAN.md. Implement the first gate now rather than writing another project plan.
