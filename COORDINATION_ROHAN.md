# Rohan core handoff

Status: CORE + SIMULATED COMPARISON + SENSING-SCOPE UPDATE. PR #2 (core) is merged into main. The experiment and sensing work (commits 07a6e81, b7e75e8, 1512d28 plus results) is in a follow-up PR from feature/rohan-core. Hardware is still open.
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
`.venv\Scripts\python -m pytest`: **20 passed**. Includes experiment fairness and API, plus SMART_METER_EVIDENCE cases: aggregate-only ambiguity with no EV credit, aggregate pump-without-water via the tank sensor, and late reading (gap → LATE with capture/receive intervals). Coverage:
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

## Smart-meter evidence update (SMART_METER_EVIDENCE.md)
- Capability/inventory register: `data/SENSING_CAPABILITIES.md`. The utility smart meter is **Not connected**: no authorized export, no endpoint scraped. Unknown fields are left unknown.
- `observation_scope=aggregate` runs: combined reading only, so attribution is AMBIGUOUS, per-EV energy is null with a reason, and pump state is UNKNOWN. The tank sensor still decides water delivery. Branch scope remains the default.
- `delay_observation` step: an explicit STALE gap, then a LATE reading judged against the commitment that covered its interval.
- These fields are **proposed additive and need Sonia's review** (CONTRACT.md "Sensing scope and freshness additions"). Examples: `handoff/state_5_aggregate_only_ambiguous.json`, `state_6_reading_in_transit.json`, `step_7_late_reading_arrived.json`.
- Observability experiment (`exp-default`, 732 runs, commit 1512d28). Mean EV shortfall at departure (model kWh), aggregate_replan vs measured_replan (branch meters):

| scenario | aggregate | branch | branch better / tie / worse (paired seeds) |
|---|---|---|---|
| perfect | 0 | 0 | 0 / 1 / 0 |
| missed_ev_false_done | 0.005 | 0 | 1 / 19 / 0 |
| missed_ev_overlapping_pump | 0.035 | 0 | 7 / 13 / 0 |
| stale_telemetry | 0.04 | 0 | 8 / 12 / 0 |
| daytime_ev_tight_allowance | 0 | 0 | 0 / 20 / 0 |

A single aggregate meter that is checked against claims catches most false EV claims in this synthetic setup, because a zero reading contradicts them. Branch meters only add value when loads overlap, and the gain is small here. Branch policies use 2 electrical meters versus 1; costs are unknown until the BOM. This is no claim about any real BESCOM meter's delay or capability.
- Live HTTP was not re-run after this change. The API was exercised in-process by `scripts/demo_flow.py` and pytest.

## Response to Sonia's review (main 7e4edfb, after PRs #4 and #5)
- Merge order: #4 merged before #5, so main has the sensing fields.
- **Defect fixed:** unlocked reads on the shared SQLite connection. All statements in `backend/db.py` now take the reentrant `LOCK`.
  - The new regression test (4 threads × 400 reads) failed before the fix (399/400) and passed 3 of 3 runs after it.
  - Live HTTP check, 4 workers × 400 authorized `GET /operator/state`: 400 × 200.
- OpenBLAS out-of-memory at first forecast load: `backend/__init__.py` and `forecasting/__init__.py` now default `OPENBLAS_NUM_THREADS=1`. I couldn't reproduce the original crash on this machine, so the fix follows Sonia's report.
- Unknown `apartment_params` keys are rejected (422); that was the root cause of the silent branch fallback on old main. Manager report is scoped, aggregate remaining energy is null, and `execution_history` and `GET /runs` were added (CONTRACT.md "Follow-ups").
- Checks: `pytest` 22 passed. Sonia's `node --test tests/ui/ui.test.js` passed 8, and her `tests/ui/e2e_flow.cjs` passed 18 of 18 against this backend; playwright-core was installed in a scratch folder, not the repo.
- **Still not run:** a physical phone over plain HTTP on the LAN (`python app.py --host 0.0.0.0`). This needs both of us before the demo. The experiments comparison view is Sonia's next piece.

## Device emulator and telemetry-driven runs (no hardware available)
- Reference profile `simulation/profiles/apartment_reference.json`: mid-size Bengaluru block, 3 HP / 2.2 kW three-phase pump, 10,000 L overhead tank, 6,000 L sump, 3.3 kW charger (7.4 kW variant). Values come from public threads and articles, with sources listed; pump flow of 100 L/min is our own estimate.
- `observation_source=telemetry` runs: each step closes the interval from device readings. Raw W/Wh stay in `raw_bench`, energy is integrated over device seconds, model values use explicit scales, and duplicates, out-of-order readings and reboots are handled.
- Live HTTP check, 7 Nov 2026, service on port 8782 plus `bench_emulator.py --fast`:
  - plan followed → OBSERVED_MATCH;
  - false done with switches off → OBSERVED_DEVIATION / EV_CHARGING_NOT_OBSERVED and a revised proposal;
  - dropped interval → STALE (null, not zero);
  - reboot → NEW_DEVICE_SESSION;
  - duplicates → ignored;
  - no source water → PUMP_POWER_WITHOUT_WATER_DELIVERY.
- Bug found and fixed during that check: the emulator reused boot id `boot-1` across runs, so the server correctly rejected a second run's first readings as duplicates. The emulator now gets a fresh boot id per start, like a real power-up.
- `pytest`: 26 passed.
- Everything here is `source_kind=synthetic`. It shows the software path works; it is not bench validation. When real parts exist, the ESP32 posts the same JSON, and a bench profile with measured calibration replaces the reference values (non-1 scales are labelled `scaled_hardware`).

## Evidence pack
`python scripts/build_evidence.py` regenerates `results/evidence/`. Every number is computed from the data, the API or the exported results. Contents:
- dataset record;
- held-out forecast results per day: ridge wins 8 of 14 days, mean MAE 540.0 vs 580.9 MW;
- demo-day chart and table;
- false-done trace: emulator readings through the real API, with the claim contradicted in interval 1;
- simulated comparison tables;
- limitations.

## Demo runbook: emulator as device, phone as manager (all readings synthetic)
1. Laptop: `.venv\Scripts\python app.py --host 0.0.0.0`.
2. Second terminal: `.venv\Scripts\python scripts\bench_emulator.py --new-run --follow-plan --interactive`. It prints the run id, then waits at a prompt before each interval.
3. Operator page (opened via the laptop's Wi-Fi address): choose that run in the run picker, load the saved forecast, and approve and issue the advisory.
4. Phone (manager link): accept the plan. Back at the emulator, press Enter. Readings arrive and the interval closes, and both pages show "Sensors agree".
5. False done: tap done on the phone, then at the emulator prompt type `ev off` (or `pump off`) and press Enter. The phone shows "Sensors disagree" and a waiting proposal.
6. Accept the revision on the phone, then press Enter at the emulator, which follows the new plan. The phone shows "Sensors agree" and History keeps the contradicted report.
7. Optional extras at the prompt: `dry` (pump power, no water), `drop` (lost readings → Unknown), `reboot`.

Checked 7 Nov 2026 on an emulator-created run in Chrome at 390 px: the manager page showed "You reported" / "Sensors disagree" / History with no script errors. UI follow-ups for Sonia:
- hide the Advance/switch controls on telemetry runs;
- take outcome provenance text from `report.provenance.plant`;
- show the telemetry `raw_bench` summary (reading count, mean W).

Not yet run end to end with a person typing at the prompt.

## Imperfect-sensing scenarios (response to review: "the big win is built into the assumptions")
The original comparison used ideal sensors and a person who always reports done, so measurement had to win. `exp-default` now adds:
- `honest_misses`: acknowledgement **ties** measured in 20/20 seeds.
- `noisy_sensors_mixed_reports`: measured is still better on EV (17 better / 3 ties / 0 worse) but computes 44.8 plans per run vs 30.5, of which 36.6 follow no missed action.
- `noisy_late_sensors_false_done`: measured 0.005 and aggregate 0 kWh EV shortfall vs 1.79 for acknowledgement; aggregate needs fewer replans (25.8 vs 41.4).

Earlier scenarios are unchanged (0 differences). Present it as: "With ideal sensors, measured feedback catches every false report. With noise it still helps, but it triggers more replans; real sensor noise and delay are not yet measured."

Sonia: the comparison screen will list the three new scenario names and two new metrics (`plans_computed`, `replans_without_missed_action`). Please add plain-language labels.

## Next
- Hardware adapter, once the real inventory and calibration exist (Teammate 3). Raw bench units stay separate; scaling will be labelled scaled_hardware.
- Optionally widen the ridge alpha grid; add outage/restart and wrong-forecast scenarios.
- Second software apartment only after Sonia's integration passes.
