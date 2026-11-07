# NivaWatt acceptance checks and demonstration v0.2

Status: planned checks, not execution evidence. Record real commands/results and run IDs as work lands. Meaningful core checks are required; no test suite is claimed to exist yet.

## Forecast/advisory gate

Validate actual dataset source/scope, timestamps, units, nulls/duplicates, coverage and attribution. Record exact train/validation/test dates and fingerprint. Hold out future data and account for available-at-issue-time assumptions. Report unvalidated publication lag.

Compare a seasonal baseline and, when fitted, one small regression on held-out demand error and top-three peak-hour overlap. Forecast values remain hourly. A saved replay is not a live BESCOM connection.

Create an immutable forecast snapshot, approve an advisory as the operator, and display the same identifiers/windows on both views. A manager cannot issue a utility advisory or derive/change a cap from regional MW. Forecast replacement alone cannot silently alter an active advisory.

Test empty/missing datasets, invalid chronology, unknown model, unauthorized approval, expired advisory and repeated request IDs. Synthetic fallback unblocks integration but does not pass the real-data gate.

## P0 gate: first complete apartment loop

1. Create one explicitly synthetic apartment run with a pump, tank, one EV request, a feasible participating-load allowance and no outage. Connect an operator-approved advisory; forecast/bench provenance remains separate. Record parameter units and interval duration.
2. Backend computes one option; phone displays it with source and expiry. Its trajectories must respect physical bounds and show any service shortfalls.
3. Manager accepts the exact option/version. Backend records ACCEPTED without observed execution.
4. Manager claims done but actual simulated switch state stays unchanged. Observations arrive independently of the claim.
5. Backend retains the claim, detects supported execution deviation (or ambiguity), and proposes a revision. It does not automatically operate the plant.
6. Manager accepts the revision and physically/simulatedly performs the action. Subsequent observations update execution and service progress.
7. Refresh phone, then restart service if persistence is intended. Commitments/claims/history remain accurate. A pending/expired proposal never masquerades as an active commitment.

This gate must work before polished comparison charts or a second apartment.

## Core correctness checks

| Test | Required result |
|---|---|
| Mass and energy conservation | Consistent units/time; no negative tank volume or invented EV progress |
| Physical source absent/outage | Pump cannot deliver water; no grid demand reduction credit for disconnected intervals |
| Expired/superseded/wrong-run acceptance | 409 conflict, no activation |
| Double click/retried request | Idempotent outcome; no duplicate commitment or claim |
| Pending revision / delayed action | Current physical state remains actual, not replaced by proposed values |
| Pump history across replans | Actual min ON/OFF history and starts retained |
| Manager attempts allowance edit | Manager API rejects it; exception remains pending operator decision |
| Stale/out-of-order/duplicate/device-reboot telemetry | Explicit handling, no silent history corruption |
| Shared-meter attribution ambiguity | UNKNOWN branch progress, not a fabricated exact energy result |
| Missing measurement | Zero remains distinct from missing; no unconditional compliance verification |
| Impossible deadline/reserve | Explicit quantified shortfall; no invented successful schedule |
| Perfect truthful execution | Measured and acknowledgement methods can tie |

## Comparison experiment

Minimum meaningful comparison: same scheduler and actual tank observations; acknowledge-driven electrical progress vs measurement-driven electrical progress. Additional baselines: simple reactive cap, initial plan/no replan and uncoordinated operation. Do not attach a cited author's name to our approximation.

Use matched initial conditions, known-event availability and human-response generation rules. Human delays/missed actions must affect all advisory methods. A directly automated limiter is a separate authority class; do not present its differences as solely scheduling quality.

Test normal operation, delayed acceptance, done-without-action, action-without-report, manual override, extra withdrawals, changed EV deadline, announced outage, unannounced interruption and lost telemetry. Include fault-free ties and cases where simple rules win. Use multiple held-out scenarios/seeds; report exact count rather than making a promised 20-run result.

Metric definitions:
- Peak participating demand: maximum interval-average model kW, interval duration stated; optional separate raw bench W maximum.
- Allowance: maximum excess kW, duration, and sum(max(0, P-A)*dt_hours) in model kWh. No outage-zero reduction credit.
- Service: reserve-violation duration/volume, unmet water where physically empty, each EV's energy shortfall at its departure, not just aggregate target percentage.
- Pump starts, proposal count, human interaction count, observation coverage and actual solve time.
- One metric/report revision determines headline, chart and selected-scenario table. No stale heading from another scenario.

Hardware: record calibration and real dt, then a genuine successful run plus missed action and sensor-loss cases. Physical comparisons require matched separate trials. Shadow alternatives on one bench are simulated, clearly labelled.

## Forecast and comparison evidence

Include forecast source/scope and held-out baseline comparison alongside the execution experiment. Use an evaluation horizon that includes deferred work/deadlines, total delivered energy and final tank state. Load shedding cannot masquerade as successful shifting. Do not fabricate bill or emissions benefits from peak shifting alone.

## Five-minute explanation (adapt to actual implemented features)

0:00–0:45: show saved regional forecast/source and operator-approved advisory, explain participating circuits/allowance, then show the apartment proposal and acceptance.

0:45–1:45: claim done while leaving a switch unchanged. Show what measurements establish and any ambiguity, then the pending revision. Acceptance alone must not change measured power.

1:45–2:45: perform the revised action and show observed progress. Change water demand or EV deadline; show feasible choice or honest shortfall.

2:45–3:45: show outage handling if implemented. Announced and unexpected cases have different information; staggered recommendations remain human-executed. Tie all step times to one displayed model clock.

3:45–5:00: show a measured overrun or lost input, then the calculated comparison report, provenance, service outcomes and limitations. Do not promise a scenario the build cannot execute.

## Release evidence

Rohan supplies tested install/start commands, a known-good commit, actual test output and a run export. Sonia records phone/browser checks and screenshots. Teammate 3 records hardware inventory, calibration, manual-test results and rehearsal gaps. Evidence is NOT RUN until actually observed. Keep a fully local synthetic fallback, clearly labelled.
