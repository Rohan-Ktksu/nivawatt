# Sonia UI handoff

Status: BOTH VIEWS CONNECTED to the real API. The complete software loop passes in a browser. Not yet checked on a physical phone.
Branch: feature/sonia-ui (see the PR for the commit SHA)
Contract target: v0.2 plus "v0.2 implementation details"

## Contract review
- **ACK** v0.2 and its implementation details at main `5c49984`.
- **ACK** "Sensing scope and freshness additions" at feature/rohan-core `7986ac3` (PR #4), used as written with no field changes.
- No field incompatibilities. The backend defect and the additive requests below are for Rohan to decide. No backend or contract file was edited.

## What was built
- `web/operator.html`, `web/manager.html` on the existing same-origin routes. Plain JavaScript and CSS, no new dependencies, no internet needed.
- `web/api.js` is the only API client. `web/ui.js` formats server values and computes no schedules or metrics.
- Forecast and advisory: source, scope, issue time, model, peak hours, evaluation-only actuals, backtest and data-quality values from the service, and explicit approval.
- Manager: next action and reason, accepted plan and pending proposal shown separately, accept/decline, a distinct done report, "You reported" beside "Sensors saw", tank and reserve, charging request and deadline, requirement changes, shortfalls.
- Fixtures were skipped: the backend checkpoint already existed, so no fixture values were ever on screen.

## Smart-meter evidence (SMART_METER_EVIDENCE.md)
Both views show measurement source, meter scope and freshness from existing fields, and "Utility smart meter: Not connected".
- Aggregate only: "Cannot tell", and verified energy, remaining energy and pump state read Unknown.
- Missing reading: Unknown, never zero. Late reading: labelled as arrived late, never live.
- Pump power without tank rise: "Sensors disagree", power alone not accepted as delivery.
- Operator scenario choices and sensor-reading controls exercise these cases.

## Checks actually run (7 Nov 2026, Windows 11, Chrome, Python 3.13.11, Node 24.22.1)
| Check | Backend | Result |
|---|---|---|
| `node --test tests/ui/ui.test.js` | none | 8 passed |
| `tests/ui/e2e_flow.cjs` | PR #4 `7986ac3` | 18 passed |
| Same, `NW_ONLY_TTL=1` with `NIVAWATT_PROPOSAL_TTL_S=3` (expired proposal) | PR #4 `7986ac3` | 2 passed |
| Same, `NW_SENSING=0` | main `5c49984` | 16 passed |
| `python -m pytest` | PR #4 `7986ac3` | 20 passed (not my suite; run to confirm the environment) |

The browser suite drives real pages against a live service with nothing mocked. It covers: forecast -> advisory -> acceptance -> done report -> contradiction -> revised proposal -> observed match, plus stale and expired proposals, double tap, impossible request, missing and late readings, aggregate-only, pump without water, invalid session, unknown run, 390 px width with no sideways scroll, and 44 px controls.

Screenshots from the PR #4 run: `tests/ui/screenshots/`. Key ones: `manager-4-contradicted-revision.png`, `manager-5-observed-match.png`, `manager-8-aggregate-only.png`, `manager-9-pump-without-water.png`, `operator-4-outcome.png`.

**NOT RUN:** a physical phone over the LAN (390 px emulation only, and plain http was not exercised because localhost is a secure context); service restart through the UI (API persistence is covered by tests/core); real or scaled hardware readings (labels exist, no such data exists yet).

## Peer action needed (Rohan)
1. **Defect, please fix before the demo:** `session()` (`backend/main.py:108`) reads the shared SQLite connection without `db.LOCK`, and `db.one` raised `sqlite3.InterfaceError` there. 400 authorized `GET /operator/state` calls gave 400 x 200 with one worker, but with four workers: 388 x 200, 6 x 401, 3 x 403, 3 x 500. Two people polling can hit this. Taking the lock inside `db.q`/`db.one`/`db.ex` would also cover other unlocked reads such as `forecast_get`. Until then `web/api.js` sends one request at a time per page and retries once (marked `shortcut:`); it should be removed after the fix.
2. **Merge PR #4 first, or together with this.** On main, `make_params` accepts `observation_scope` but ignores it, so the "One combined meter" scenario behaves like branch metering and the page shows "Meters: Not stated".
3. **Additive requests, not blockers:**
   - `state.execution` covers only the active commitment's latest interval, so after a revision is accepted the contradicted report remains only as a count. A per-interval execution/claim history would let the manager see it. Likewise `late_execution` reaches only the step response.
   - `GET /runs/{id}/report` gives a manager simulator-truth energy values, including under aggregate metering. The manager view shows only counts and coverage from it; consider scoping that response.
   - No run listing exists, so the operator page shows a manager link carrying the run ID.
   - Under aggregate metering `remaining_model_kwh` still equals the full request. The UI shows Unknown based on `charging_status_by_ev`.
4. **Startup note:** on this 8 GB machine the service crashed with an OpenBLAS memory-allocation error on the first forecast load. `OPENBLAS_NUM_THREADS=1` fixed it.

## Next
Physical phone check with Rohan on the local network, then fix whatever it finds. The computed comparison view (`/experiments`) is not built yet; it follows once the loop is signed off.
