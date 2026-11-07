# Rohan core handoff

Status: CORE SOFTWARE CHECKPOINT + SIMULATED COMPARISON. Forecast→advisory, the synthetic apartment P0 loop and the paired policy experiment work through the API. Hardware is still open.
Branch: feature/rohan-core (PR against main; see the PR for the commit SHA)
Contract target: v0.2 plus the "v0.2 implementation details" section in CONTRACT.md

## Implemented and working
- One FastAPI service (`app.py`, port 8780), SQLite in `runtime/` (ignored), same-origin `/operator` and `/manager` routes that serve `web/*.html` once Sonia adds them.
- Data: KPTCL-derived hourly **Karnataka state** grid load (ODbL, Vonter/kptcl-load-curve @ ed46df8, sha256 61538bc8…331ff), fetched by `scripts/fetch_kptcl.py`. Validation results:
  - 135,774 raw rows; no null or implausible loads.
  - 5,344 report-hour duplicates (hour 24 of D equals hour 0 of D+1), 277 with differing values; the hour-0 row is kept.
  - 6,611 missing hours, not imputed; incomplete days are excluded.
  - Coverage 2010-12-31T18:30Z to 2026-08-19T18:30Z. IST→UTC is an assumption. Publication lag is unvalidated.
- OpenCity BESCOM review: `data/OPENCITY_BESCOM_REVIEW.md`. All 22 CSVs were downloaded. None is an intraday load series (all annual/FY revenue ₹, energy MU/kWh, or asset registers). They are context only, so the Karnataka hourly series stays the forecasting input.
- Forecasting (`python -m forecasting.evaluate`, a historical timestamp-split backtest; every input lag is ≥48 h). On the 14 held-out test days (2026-08-03T18:30Z to 2026-08-19T18:30Z):
  - seasonal_naive (same hour, previous week): MAE **580.9 MW**, top-3 peak-hour overlap **0.905**.
  - ridge_lag_calendar (fitted closed-form ridge, alpha 100 picked on validation): MAE **540.0 MW**, overlap **0.929**.
  - Splits: train 56 / validation 14 / test 14 most recent complete days. Missing days make the calendar spans longer than the day counts.
  - alpha=100 is the largest candidate (boundary), so the grid could be widened. 14 days is a small test set; this is not proof of general superiority.
- Immutable forecast snapshots (`POST /forecasts/replay`, `GET /forecasts/{id}`) and operator-only `peak_advisory` events, validated against forecast hours and validity, effective only from `known_from_interval`.
- Rules scheduler (`scheduler/rules.py`, `source=rules`): water reserve first, then EV energy before departure, within the participating-load allowance, avoiding advisory hours. Infeasibility is reported as quantified shortfalls.
- Proposal lifecycle (exact-revision acceptance, server expiry, supersession, idempotent request_id), claims (record only), independent synthetic observations, execution verdicts, and automatic *pending* revision proposals after deviations. The SQLite history survives restart.

## Startup commands actually tested (Windows 11, Python 3.12.10)
See README "Run it". Live run on 7 Nov 2026: `python app.py`, then an HTTP script did login → replay ridge forecast for 2026-08-18T18:30Z → advisory → proposal → delivered → accept → claim EV done with switches OFF → step. Results:
- Forecast for 10:00–13:00 IST peak hours; that day's MAE was 418.3 MW.
- The step returned `OBSERVED_DEVIATION / EV_CHARGING_NOT_OBSERVED`, the claim was preserved, and a new `CLAIM_WITHOUT_OBSERVED_EXECUTION` proposal was left PROPOSED (not active).

## Tests actually run
`.venv\Scripts\python -m pytest`: **17 passed** (including experiment fairness and API). Coverage:
- P0 loop with false done → revision → executed match → restart persistence.
- Authorization/scope; manager allowance edit rejected; request_id reuse; advisory validation and no early knowledge.
- Superseded, wrong-revision, wrong-run and expired acceptance → 409.
- Impossible EV requirement → shortfall; pump power without water → deviation; stale observation ≠ zero.
- Telemetry duplicate/out-of-order/reboot; tank mass balance; EV departure cutoff; scheduler allowance/reserve bounds.
- Forecast leakage (poisoned post-cutoff data leaves the forecast unchanged), replay API immutability/auth, top-3 tie order.

## Hardware vs synthetic
Everything apartment-side is **synthetic** (`source_kind=synthetic`). Telemetry ingestion stores raw bench values unconverted, but it does not drive verdicts. No component inventory or calibration has been received, so no firmware or adapter was written.

## Peer action needed
- Sonia: integrate against `handoff/*.json` (real API responses from `scripts/demo_flow.py`) and CONTRACT.md "v0.2 implementation details". Record ACK or exact incompatibilities in COORDINATION_SONIA.md. **No acknowledgement is recorded yet.**
- Teammate 3: exact component inventory and calibration so the adapter can be written.

## Gate D: simulated comparison (synthetic only, not bench evidence)
`python -m simulation.experiment` writes `results/experiments/exp-default/{runs.csv,summary.json}`: 510 runs, generated at commit 07a6e81, 20 seeds per stochastic scenario. All policies share the plant, disturbances, advisory hours (intervals 40–51 = 10:00–13:00 IST from the demo forecast) and per-seed human-response draws. The human claims every instructed action, including missed ones. Ack and measured replanning use the same scheduler and the same tank observations; only the EV-progress evidence differs.

Mean per run. EV shortfall is model kWh at departure; reserve violations are intervals below reserve.

| scenario | uncoordinated* | demand_cap* | fixed_plan | ack_replan | measured_replan |
|---|---|---|---|---|---|
| perfect: EV shortfall / reserve | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 (tie) |
| missed_ev_false_done: EV shortfall | 0 | 0 | 2.95 | 2.95 | **0** (better in 20/20 paired seeds) |
| missed_pump_false_done: reserve | 0 | 0 | 57 | 3.15 | 3.15 (tie 20/20; both see the tank) |
| stale_telemetry: EV / reserve | 0 / 0 | 0 / 0 | 1.20 / **0** | 1.20 / 1.65 | 0 / 1.65 (stale tank readings hurt both replanners; fixed plan wins on water) |
| extra_withdrawal: reserve | 0 | 0 | 3.8 | 0.8 | 0.8 |
| daytime_ev_tight_allowance: peak-window kWh / EV | 6.7 / 0 | 6.7 / 0 | 0 / 1.34 | 0 / 1.34 | 0 / **0** |
| infeasible_ev (40 kWh asked, 26.4 possible): EV shortfall | 13.6 | 13.6 | 13.6 | 13.6 | 13.6 (shortfall visible for every policy) |

*Automatic local control, a different authority class: it is not subject to human misses, which is why it never violates the reserve. The demand cap never bound in these runs (pump and EV rarely overlapped), so it equals uncoordinated. That is reported, not tuned away. In the default day nothing loads during the advisory hours, which is why the daytime-EV case was added.

Fairness tests: `test_experiment_fairness_properties` checks perfect-execution ties, pump-miss ties via shared tank observations, that acknowledgement never beats measurement on EV under false done, infeasible shortfalls, and tank bounds.

## Next
- Hardware adapter, once the real inventory and calibration exist (Teammate 3). Raw bench units stay separate; scaling will be labelled scaled_hardware.
- Optionally widen the ridge alpha grid; add outage/restart and wrong-forecast scenarios.
- Second software apartment only after Sonia's integration passes.
