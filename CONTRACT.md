# NivaWatt build contract v0.2

Status: proposed additive team build target; endpoints/source are not implemented by this documentation commit. No Sonia acceptance is recorded by this revision. Rohan is single writer. Sonia records ACK or an exact incompatibility against this version and commit SHA. All additions are additive until discussed; no silent field renames.

## Runtime and ownership

One local Python service, SQLite persistence and browser views /manager and /operator. Prefer one origin, JSON HTTP and browser polling; no WebSocket requirement. For a fresh build use forecasting/, backend/, scheduler/, simulation/, firmware/ and web/. Reused source may use equivalent directories if mapped once in TEAM_WORKFLOW.md.

API prefix: /api/v1. Default proposed port 8780, overridable if occupied. Backend owns computation and persistence. UI does not calculate final schedules or benchmark results. Scheduling is source=rules unless a separately implemented and tested optimizer is labelled optimization. Forecasting labels seasonal_naive, trained_regression and synthetic_fixture separately; a fixture is not a fitted model.

Local demonstration roles: manager is scoped to an apartment; operator owns allowance/event creation. Rohan supplies a lightweight local-demo session mechanism; server validates role/apartment on writes. Keep any local access codes in ignored config, not Git or URLs. These demo sessions do not establish production identity, real BESCOM access or customer authentication.

## Units, time and provenance

- server timestamps: UTC ISO-8601; monotonic sequence per device/session; reboot/session ID distinguishes counter resets.
- model clock: run_id + interval_index, with model_dt_minutes recorded once per run.
- raw bench: volts, amps, watts, water volume in litres after calibration; preserve raw sensor distance separately if needed. Integrate raw joules with actual elapsed seconds, then Wh=joules/3600.
- apartment model: kW, kWh, litres and simulated minutes. Use explicit model_* field names.
- source_kind: synthetic, hardware, or scaled_hardware. A scaled value is a model value, not a field measurement.
- calibration tolerances and time-alignment bounds are explicit configuration, not an assumed universal +/-1% or 80%-coverage proof.
- missing, stale, ambiguous and measured zero are distinct.

## Authoritative state

GET state contains schema_version, run_id, revision, mode, clock, apartment, active_commitment, pending_proposals, observation, execution, readiness and warnings. Version 0.2 adds forecast_id and active_advisory (nullable until an operator issues one). STATE_EXAMPLE.json is the shape fixture, explicitly synthetic.

Core apartment state: apartment_id, allowance_model_kw, model_tank_l, model_tank_min_l, model_tank_max_l, source_water_available, pump_state (ON/OFF/UNKNOWN), ev_sessions (id, arrival/departure interval, requested and remaining model kWh).

Raw observations never overwrite synthetic truth or model fields without the adapter preserving provenance. Unknown branch energy is null and includes a reason. EV-circuit electrical energy is not battery SoC unless a real vehicle interface establishes that meaning.

## Two independent lifecycles

Proposal: PROPOSED -> DELIVERED -> ACCEPTED | DECLINED | EXPIRED | SUPERSEDED. Acceptance is atomic, server-timed, authorized, for an exact option/version/run. Expired, obsolete, wrong-run or duplicate-conflicting actions return 409. Only one effective commitment exists per apartment/time. A delivered timer never extends absolute server expiry. Acceptance records effective_from_interval and does not actuate equipment.

Execution per commitment/interval: UNOBSERVED, CLAIMED_EXECUTED, OBSERVED_MATCH, OBSERVED_DEVIATION, AMBIGUOUS, STALE, OUTAGE. Preserve the claim even when observation disagrees. Verified allowance compliance, water reserve and charging readiness are separate outcomes; matching power alone does not prove service completion. Coverage gaps prevent unconditional verified-compliance claims unless explicit defensible bounds establish them.

Manager cannot change an operator allowance through acceptance, telemetry or requirement fields. A plan exceeding the allowance is a pending operator exception request, not an approved option. Actual overrides are recorded even when unauthorized; the scheduler does not rewrite measured history to conceal them.

## Minimal endpoints

| Method/path after /api/v1 | Owner/behavior |
|---|---|
| GET /health | Service + schema version; no claimed hardware connection without evidence |
| POST /demo/session | Local-demo role/session setup; final credential details owned by Rohan |
| POST /runs | Operator; create synthetic/demo run with scenario, clock mapping and apartment parameters; returns run_id |
| GET /state?run_id=...&apartment_id=... | Authoritative manager state; example shape provided |
| GET /operator/state?run_id=... | Operator view, participating scope, apartment summaries and event/coverage status |
| POST /events | Operator; allowance/outage/peak_advisory event with run_id, request_id and known_from_interval; peak_advisory references a forecast_id and exact selected peak_windows; no early future information |
| POST /requirements | Scoped manager; EV deadline/energy or water requirement changes; returns updated revision and proposal candidates |
| POST /proposals/{id}/delivered | Scoped manager acknowledgement of render; does not accept or execute |
| POST /proposals/{id}/decision | Scoped manager; run_id, expected_revision, decision ACCEPT/DECLINE, option_id, request_id; returns state |
| POST /execution/claims | Scoped manager; run_id, commitment_id, interval_index, action_id, request_id; records claim only |
| POST /telemetry | Authorized demo device/adapter; payload TELEMETRY_EXAMPLE.json; validates duplicate/order/reboot and source |
| POST /runs/{id}/step | Operator simulation control only; advances the synthetic clock/plant; returns state |
| GET /runs/{id}/report | Computed outcomes with provenance, coverage, per-EV shortfalls and metric definitions |
| POST /experiments | Operator; defined scenarios, policies and seeds; returns experiment_id; may be synchronous for short runs |
| GET /experiments/{id} | Status and calculated policy metrics; never fabricated constant winner results |

Only P0 endpoints needed for the first loop are implemented first. Experiments and the second apartment follow. Frontend must show unavailable P1 features honestly until the API exists.

Errors: 400 malformed command, 401 missing/invalid demo session, 403 wrong role/apartment, 404 unknown resource, 409 stale/expired/conflict, 422 invalid units/fields, 503 solver/adapter unavailable. JSON error body: {"error":{"code":"STALE_PROPOSAL","message":"Refresh before accepting this version."},"revision":8}. A solver failure preserves current applicable commitment and reports failure, not an invented successful plan.

Request_id makes repeated clicks/retries idempotent. Server owns identifiers, versions, clock progression, authorization, metric results and proposal activation. A client cannot upload its preferred final metrics or substitute claimed progress for verified progress.

## Scheduler callable boundary

plan(current_state, known_events, requirements, constraints) -> {source, options, infeasibilities, computation_ms}

Inputs are validated copies of currently available observations/estimates and event information. No database or hardware writes in plan(). Each option contains actions per model interval, effective time, predicted peak, water trajectory, per-EV energy trajectory, shortfalls and assumptions. Offer one valid option first; generate a second meaningfully different option only after integration. Never guarantee feasibility under arbitrary future human noncompliance.

Physical actuals and plans differ. Simulator applies delayed/missed/overridden actions through an explicit human-response model, not by applying solver outputs automatically. Pump history is derived from actual execution; cold restart starts are counted after outages.

Tank model: V_next = V + pump_inflow_Lph * dt_h * actual_pump_on - withdrawn_L. Withdrawal is interval volume, not a rate mixed without dt. Preserve physical 0 <= V <= capacity; model unmet water separately instead of negative water. Reserve is a service requirement with explicit violations; overflow/dry-run protection is independent. Upper/lower uncertainty bounds use appropriate high/low inflows and withdrawals; nominal overflow checks alone are not robust guarantees.

EV progress: measured or explicitly estimated delivered electrical energy integrated over the appropriate clock. Bound progress by the declared request and stop credit at departure; no transfer of one EV's excess to another. Do not infer current vehicle SoC from an LED.

True lexicographic priorities require sequential solves or justified finite bounds. Otherwise label objective weighted. Operator exception requests cannot be silently treated as accepted allowance increases.

## Comparison isolation

Same plant parameters, external disturbance-generation rules, known-event timing, human-response assumptions and action authority across policies. Each simulated policy has its own evolving plant state. Shared initial conditions do not imply shared realized tank trajectories after different actions.

Acknowledgement and measured replanners use the same scheduler and all available tank measurements. The controlled difference is electrical execution/energy-progress evidence. Do not restrict acknowledgement tank use to emergencies merely to create a win. Name it an experimental baseline, not a faithful reproduction of a cited paper.

Simulator truth is available to the evaluator only; policies receive their declared observations. A single physical run can have simulated shadow comparisons, clearly labelled. Repeated measured policy trials are required for hardware performance comparisons.

## Forecasting/advisory additions in v0.2

These additions preserve existing apartment fields. Rohan confirms implementation details and Sonia acknowledges exact version/commit before live integration. Examples are explicitly synthetic.

| Method/path after /api/v1 | Proposed behaviour |
|---|---|
| POST /forecasts/replay | Operator-only historical replay from a registered dataset and model; returns immutable forecast snapshot |
| GET /forecasts/{id} | Authorized read of forecast provenance, 24 hourly points and selected peak windows |

Replay input: request_id, dataset_id, model_name and forecast_start. The backend derives/verifies the cutoff, available history and chronological split. It does not trust a client to supply future observations or preferred evaluation metrics. Evaluator-only future actuals do not appear in planning inputs.

Forecast fields: forecast_id, source_kind (historical_replay or synthetic), source_name, source_url, geographic_scope, resolution_minutes, demand_unit, model_name, model_kind, dataset_fingerprint, training_end, last_observation_time, issued_at, availability_assumptions, forecast_start, forecast_end, points[{start,end,predicted_mw}], peak_windows[{start,end}] and evaluation_reference. Source/coverage/time fields are factual or explicitly unknown. Synthetic fixtures may have null source/training/fingerprint fields and must remain visibly synthetic.

Initial peak selection uses the top three forecast hours, deterministic tie order by earliest start. Keep disjoint hours separate. A real-data snapshot has 24 hourly points covering forecast_start inclusive to forecast_end exclusive. No automatic conversion from regional MW to an apartment allowance occurs. Model intervals may repeat hourly advisories without implying higher-resolution source data.

POST /events with kind=peak_advisory approves selected windows from a saved forecast for a run/apartment set. Required inputs: run_id, request_id, known_from_interval, forecast_id, target_apartments, peak_windows, valid_from and valid_until. Backend validates operator role, temporal ordering, run mapping and window containment, generates advisory_id/issued_at/approved_by_demo_operator, persists the event and updates apartment state only when known/effective. Client display cannot issue an advisory. ADVISORY_EXAMPLE.json is the resulting record, not a request body.

active_advisory contains the saved record or null. forecast_id is the forecast associated with that active advisory, or null before issue. A newer forecast alone does not silently replace an active advisory. Pending proposals include the advisory reference/assumptions used to generate them. Existing event known-time semantics and role/idempotency checks still apply.

A historical_replay snapshot is not a live forecast connection. Publication availability/latency assumptions are explicit. State-level demand is not BESCOM feeder demand. A participating-load allowance is not a whole-building limit without appropriate measurement.

FORECAST_EXAMPLE.json, ADVISORY_EXAMPLE.json and STATE_EXAMPLE.json are shape fixtures, not chronological experiment evidence. Computed evaluation uses chronological held-out forecasts, known signal timing and fair service constraints.

## v0.2 implementation details (Rohan, feature/rohan-core)

Implemented and tested on feature/rohan-core. Responses captured from the running API are in `handoff/` (regenerate with `python scripts/demo_flow.py`). Sonia's acknowledgement is **not** recorded yet. She records ACK or concrete incompatibilities in COORDINATION_SONIA.md against the commit named in COORDINATION_ROHAN.md.

- Sessions: `POST /api/v1/demo/session {role: operator|manager, apartment_id (manager), access_code}` returns `{token}`. Send `Authorization: Bearer <token>` on every other call. Codes live in the ignored `config/local.json`, which is generated on first start. Device telemetry uses a device token from the same file.
- Revision: the run `revision` increments when a proposal is created or a decision is accepted. A decision's `expected_revision` must equal that proposal's `revision`. A superseded, expired, declined or already-accepted proposal, a different run, or a mismatched revision returns 409. A repeated `request_id` with the same body returns the stored response. The same `request_id` with a different body returns 409 `REQUEST_ID_REUSED`.
- Proposal expiry: absolute server time, `expires_at` (default 900 s, `NIVAWATT_PROPOSAL_TTL_S`). `delivered` never extends it.
- Acceptance: creates a commitment with `effective_from_interval = max(option.effective_from_interval, current interval)`. The previous commitment becomes SUPERSEDED with `ended_at_interval`. Nothing is switched.
- Claims: `action_id = "<commitment_id>:<interval_index>:pump|ev"`. The interval must lie inside the commitment and must not be in the future. A claim never changes plant state.
- Execution verdict reasons: `PUMP_NOT_OBSERVED_ON`, `PUMP_POWER_WITHOUT_WATER_DELIVERY`, `PUMP_ON_NOT_PLANNED`, `EV_CHARGING_NOT_OBSERVED`, `EV_CHARGING_NOT_PLANNED` (comma-joined). `STALE` applies when the interval has no valid observation.
- Revision reasons: `PEAK_ADVISORY_ISSUED`, `ALLOWANCE_CHANGED`, `OUTAGE_ANNOUNCED`, `REQUIREMENT_CHANGED`, `OBSERVED_DEVIATION`, `CLAIM_WITHOUT_OBSERVED_EXECUTION`.
- `POST /runs/{id}/step {request_id, actual_switches?: {pump, ev: ON|OFF}, drop_observation?: bool}` is operator simulation control. `actual_switches` is the simulated human physically switching. Switches persist until changed. Acceptance never sets them.
- `POST /runs {request_id, clock_start_utc, apartment_params?}`: interval 0 maps to `clock_start_utc` (use a forecast's `forecast_start`); the model interval is 15 min and the horizon 96 intervals.
- Forecast `model_name`: `seasonal_naive` (model_kind seasonal_naive) or `ridge_lag_calendar` (model_kind trained_regression, actually fitted). `forecast_start` must be 00:00 IST (18:30Z). Additive read endpoints: `GET /forecasts/evaluation` (backtest JSON) and `GET /forecasts/{id}/actuals` (evaluation-only actuals, never a planning input).
- Events: `peak_advisory` windows must be hours of the referenced forecast, inside both validity and forecast range. `known_from_interval` must be at or after the current interval. An event takes effect only when the clock reaches it.
- Additive state fields: `clock.horizon_intervals`, `clock.model_time_utc`, `apartment.allowance_scope`, `apartment.pump_starts_observed`, `active_commitment.option` (full actions), `execution.claims`, `execution.next_action`, `readiness.charging_status_by_ev`, `readiness.verified_ev_delivered_by_ev_model_kwh` and observation `quality`/`aggregate_model_kw`. Fixture fields keep their types; `observation.model_power_kw` equals the aggregate.
- Telemetry responses: `ACCEPTED`, `DUPLICATE`, `OUT_OF_ORDER`, `NEW_DEVICE_SESSION`. Raw bench values are stored unconverted and exposed as `observation.raw_bench`. Telemetry does not yet drive execution verdicts; the hardware gate is open.
- Web: `/operator` and `/manager` serve `web/operator.html` / `web/manager.html` when present, and `/web/*` serves static assets. The API returns 404 `UI_NOT_PRESENT` until Sonia's files land.
- Experiments: `POST /experiments {request_id, scenarios?, policies?, seeds_per_scenario? (1..50, default 20), run_id? (use that run's advisory hours)}` runs synchronously (~2 s for the full default set) and returns `{experiment_id, status: COMPLETED, runs}`. `GET /experiments/{id}` returns config, per-scenario/policy mean and sd, paired measured-minus-acknowledgement differences with win/tie/loss counts, and every per-run row. `source_kind` is `synthetic_simulation`. Scenario and policy names are listed in `simulation/experiment.py`.

### Sensing scope and freshness additions (SMART_METER_EVIDENCE.md), proposed additive, Sonia review requested

All of these default to the earlier behaviour (`observation_scope=branch`, no delay), so existing consumers are unaffected. Sonia: ACK or request changes in COORDINATION_SONIA.md before relying on them.
- Run input `apartment_params.observation_scope`: `branch` (default; pump and EV metered separately) or `aggregate` (one meter on the combined participating circuits). The tank sensor is independent in both.
- Observation fields: `measurement_scope` (`branch`|`aggregate`) and `received_at_interval` (model interval in which the reading arrived; null while missing). `quality` adds `LATE` (real reading delivered after its interval; never present it as live). `branch_attribution` adds `AMBIGUOUS` (non-zero aggregate) and `AGGREGATE_ZERO`.
- Aggregate scope: `pump_model_kw`, `ev_model_kw` and `ev_id` are null (unknown, not zero); `apartment.pump_state=UNKNOWN`; `pump_starts_observed=null`. `readiness.charging_status` and `charging_status_by_ev` are `UNVERIFIED`; `verified_ev_delivered_model_kwh` and `verified_ev_delivered_by_ev_model_kwh` are null, and the new `verified_ev_unavailable_reason` explains why.
- Verdicts: aggregate non-zero → `AMBIGUOUS / AGGREGATE_ONLY_BRANCH_UNATTRIBUTED` (no revision triggered); aggregate zero while an action is due → `OBSERVED_DEVIATION / NO_PARTICIPATING_LOAD_OBSERVED`; pump due but tank not rising → `PUMP_WATER_DELIVERY_NOT_OBSERVED`. Late readings append ` (late reading)` to the reason.
- Step input `delay_observation: true` (simulation): interval i is recorded as STALE now and the reading arrives as LATE at the next step. The step response adds `late_execution` (verdict for that earlier interval or null). It cannot be combined with `drop_observation`.
- Experiments add policy `aggregate_replan`, scenario `missed_ev_overlapping_pump`, per-run `electrical_meters`, and summary block `paired_branch_minus_aggregate`.
- Not implemented on purpose: any utility smart-meter endpoint. A future import adapter needs a documented, authorized export and a separate contract proposal.

### Follow-ups to Sonia's integration review (COORDINATION_SONIA.md)
- Fixed: every SQLite statement now takes the shared lock. Concurrent authorized reads no longer return false 401/403/500 (4 workers × 400 requests over HTTP: 400 × 200). The one-request-at-a-time and retry shortcut in `web/api.js` can be removed; that file is Sonia's.
- `POST /runs` rejects unknown `apartment_params` keys with 422 instead of silently ignoring them.
- `GET /runs/{id}/report` for a **manager** returns only `counts`, `observation_coverage`, `provenance` and `scope`. Simulator-truth outcomes stay operator/evaluator-only.
- Under aggregate metering, `apartment.ev_sessions[].remaining_model_kwh` is `null` (unknown), not the full request.
- Additive `state.execution_history`: one entry per judged or claimed interval across all commitments, with `commitment_id`, `interval_index`, `observation_status`, `reason`, `claims[]`, `quality` and `received_at_interval`. Contradicted claims and late verdicts remain visible after a revision.
- Additive `GET /runs` (operator): `runs[]` with `run_id`, `apartment_id`, `observation_scope`, `interval_index`, `revision`, `clock_start_utc` and `created_at`, newest first.

### Telemetry-driven runs and the device emulator (additive; Sonia review requested)
- Run input `apartment_params.observation_source`: `simulator` (default, unchanged) or `telemetry`. A telemetry run takes its observations from `POST /telemetry` readings instead of the server's synthetic plant. `telemetry_power_scale` and `telemetry_volume_scale` (default 1.0) convert device units to model units explicitly.
- In a telemetry run, `POST /runs/{id}/step {request_id}` closes the current interval from readings received since the previous close. It rejects simulated switches and faults (422 `TELEMETRY_RUN`).
  - Readings with status ACCEPTED or NEW_DEVICE_SESSION count; duplicates are never stored and OUT_OF_ORDER readings are excluded.
  - Mean watts and Wh are integrated over actual device `device_monotonic_ms` deltas within one device session; no elapsed time is assumed across a reboot.
  - Model kW = mean W × power_scale / 1000. Tank = last reading × volume_scale.
  - EV energy is attributed only when exactly one EV session is present and branch meters exist.
  - No readings, or no tank reading, makes the interval STALE.
- `observation.raw_bench` for telemetry runs is the interval summary: `sample_count`, `excluded_samples`, `duration_s`, `device_sessions`, mean W and Wh per branch, `last_tank_volume_l` and the scales. The newest raw reading moves to the additive `observation.latest_device_reading`.
- `observation.source_kind`: `synthetic` for emulator readings; `hardware` for device readings at scale 1; `scaled_hardware` when scales differ from 1. `branch_attribution` adds `MEASURED_BRANCHES`.
- `POST /telemetry` now also requires `device_monotonic_ms` (int ≥ 0) and an `apartment_id` matching the run.
- Report for telemetry runs: outcomes come from usable observations. `provenance.plant` says "device telemetry", and `unmet_withdrawal_l` is null because it can't be observed.
- Emulator: `scripts/bench_emulator.py` with profile `simulation/profiles/apartment_reference.json`. All its readings are `source_kind=synthetic`.
- Additive `observation_source` (`simulator`|`telemetry`) in `GET /state`, `GET /operator/state` and each `GET /runs` row. UI: for `telemetry`, hide the simulated switch, reading and Advance controls (the device closes intervals), and take outcome provenance text from `report.provenance.plant`.
