# AdaptiveFlow build contract v0.1

Status: initial team build target; endpoints/source are not implemented by this documentation commit. Rohan is single writer. Sonia records ACK or an exact incompatibility against this version and commit SHA. All additions are additive until discussed; no silent field renames.

## Runtime and ownership

One local Python service, SQLite persistence and browser views /manager and /operator. Prefer one origin, JSON HTTP and browser polling; no WebSocket requirement. For a fresh build use backend/, scheduler/, simulation/, firmware/ and web/. Reused source may use equivalent directories if mapped once in TEAM_WORKFLOW.md.

API prefix: /api/v1. Default proposed port 8780, overridable if occupied. Backend owns computation and persistence. UI does not calculate final schedules or benchmark results. Initial app behavior is source=rules unless a separately implemented and tested optimizer is labelled optimization. No trained model is assumed.

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

GET state contains schema_version, run_id, revision, mode, clock, apartment, active_commitment, pending_proposals, observation, execution, readiness and warnings. STATE_EXAMPLE.json is the shape fixture, explicitly synthetic.

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
| POST /events | Operator; allowance/outage event with known_from_interval; no future-only information disclosed early |
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
