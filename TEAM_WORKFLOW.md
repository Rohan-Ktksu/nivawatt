# NivaWatt three-person workflow v0.2

[NIVAWATT_BUILD_NOW.md](NIVAWATT_BUILD_NOW.md) is the complete current execution plan. Its gates restore the forecasting/advisory layer and supersede the earlier apartment-only schedule. This file is the short coordination reference.

## Ownership and first actions

| Person | Branch | First work |
|---|---|---|
| Rohan | feature/rohan-core | Validate demand data, baseline forecast, shared fixture/API, core/scheduler/simulation/firmware integration |
| Sonia | feature/sonia-ui | Operator forecast/advisory and apartment interfaces, one API client, phone checks |
| Third teammate | feature/hardware-validation | Exact inventory, calibration, costs, independent scenarios and evidence |

Rohan owns shared integration and CONTRACT.md. Sonia owns web/ and tests/ui/. Third teammate owns hardware/, validation/, scenarios/ under the agreed schema and presentation evidence. Each owns their coordination note. If existing source has equivalent different folders, map once rather than restructuring working code.

## Focused session targets

| Elapsed | Rohan | Sonia | Third teammate | Gate |
|---|---|---|---|---|
| 0-30 min | Inspect source, publish fixture/additive schema and local foundation | Build page shells from synthetic shapes | Confirm exact components/ratings | Shared handoff agreed |
| 30-120 min | Validate data, saved baseline forecast and advisory API | Forecast/advisory plus manager proposal rendering | Bench preparation with lab support | Forecast/advisory visible in both views |
| 2-4 hours | Apartment acceptance/claim/observation/revision | Real API, conflicts, separate execution states | Independent false-done/stale-action tests | Complete software loop |
| 4-6 hours | One candidate forecast model and/or device adapter as ready | Live state and provenance labels | Actual calibration/telemetry | Real inputs or explicit incomplete gate |
| 6-8 hours | Repair integration and paired evaluation | Computed comparison, phone checks | Rehearsal/evidence/costs | Connected demonstration, honest gaps |
| Further focused session | Wider scenarios and reproducible evaluation | Final fixes | Repeated trials and judge answers | Evidence ready |

The first connected software demonstration is the initial target. Hardware calibration and defensible results may need another session. Synthetic advice can unblock the apartment loop while the real-data gate remains explicitly open. If the loop fails, stop features and repair it. Add a second apartment only after core/evaluation work.

## Working together

Clone https://github.com/oxydevelopers/nivawatt.git into a separate directory. Use each person's own Git identity and only their role branch. If latest planning is in a PR, deliberately start from that branch or merge the reviewed PR first; main does not contain unmerged work.

Rohan proposes contract v0.2 implementation details. Sonia reads the exact pushed contract and records acknowledgement or concrete field requests. No invented agreement. Communicate through committed coordination files at natural handoffs. Each human resumes their own assistant.

Use git status --short and git diff --check. Stage explicit owned paths, commit and push. Open small PRs against main with actual commands/results and remaining limitations. Rohan reviews/merges ready checkpoints; assistants do not automatically merge main or force-push. After reviewed merges, fetch and merge origin/main into a clean role branch. Do not overwrite another developer's directory.

Third teammate may use GitHub's web editor to create a branch/PR for inventory/validation notes. Gemini provides text guidance, not assumed terminal/device/repository access.

## Evidence discipline

No paid services, secrets, runtime databases or environments in Git. Preserve dataset attribution and publication-lag assumptions. A forecast does not establish transformer capacity. Keep claims separate from observations and bench units separate from model values. No fake hardware, model training, results or savings.
