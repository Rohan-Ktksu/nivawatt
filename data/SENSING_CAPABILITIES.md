# Measurement source capability register

Follows SMART_METER_EVIDENCE.md item 4. Unknown fields stay **unknown**; nothing here claims access or a connection.

| Field | Local branch sensing (synthetic now) | Bench hardware (target) | Utility smart meter (optional future) |
|---|---|---|---|
| Status | Implemented in simulation (`observation_scope=branch` / `aggregate`) | Not connected. The telemetry path is exercised end to end by `scripts/bench_emulator.py` (synthetic, reference apartment profile); inventory and calibration not received | **Not connected.** No documented, authorized export identified |
| Utility | n/a | n/a | unknown (BESCOM and CESC Mysore are different utilities) |
| Connection / meter association | simulated participating circuits of APT_1 | unknown until Teammate 3's inventory | unknown |
| Device model | none (simulated) | unknown | unknown |
| Documented export format | API JSON (`observation`) | TELEMETRY_EXAMPLE.json shape via `POST /telemetry` | unknown; no endpoint will be scraped or reverse-engineered |
| Interval | 15 min model interval | device sample period unknown; energy integrated from actual elapsed seconds | unknown |
| Capture time | `interval_index` (model clock) | device monotonic ms + session/sequence | unknown |
| Received time / latency | `received_at`, `received_at_interval`; `quality=LATE` when delivered after its interval | server `received_at` per sample | unknown; not assumed real-time |
| Units | model kW / kWh / litres | raw V, A, W, litres (calibrated), stored unconverted | unknown (bill kWh ≠ interval kW) |
| Quality flags | VALID, LATE, STALE (missing ≠ zero) | ACCEPTED, DUPLICATE, OUT_OF_ORDER, NEW_DEVICE_SESSION | unknown |
| Permission / access basis | own simulation | college lab bench with supervision | none held. Private bills and account IDs are never committed |
| Scope | branch (pump and EV separately) or aggregate (combined participating circuits); tank sensor separate | intended: pump branch, charging-emulator branch, tank level | whole connection (aggregate) at most; includes unmetered background load |

## Rules applied in code

- **Aggregate reading** (`measurement_scope=aggregate`): `branch_attribution=AMBIGUOUS` when non-zero, so the verdict is `AMBIGUOUS` and no individual EV energy is credited (`verified_ev_delivered_model_kwh=null` with a reason). A zero aggregate supports "nothing on". Pump state and start history are `UNKNOWN`/null.
- **Pump power without tank rise** is a deviation in both scopes. In aggregate scope the tank sensor alone decides water delivery.
- **Late or missing readings:** the interval shows `STALE` until a reading arrives. A late reading is stored as `LATE` with both capture interval and receive interval, then judged. It is never shown as live.
- **Sanctioned load ≠ allowance:** a flat's sanctioned load is not the common-pump or participating-load allowance. The allowance is operator-configured.
- **A utility smart-meter import adapter** is deferred until authorized interval data exists. The smallest additive contract change will be proposed with Sonia first.

## Observability experiment

`aggregate_replan` vs `measured_replan` in `simulation/experiment.py` (same scheduler, tank observations, authority and human draws). Per-policy electrical meter counts are recorded. Their **costs are unknown** until Teammate 3's BOM.
