# False-done trace (emulated device, real API)

Run `run-b3fb36e79b`. A ridge forecast for 2026-08-19 produced an operator-approved advisory, and the apartment plan was accepted.
The device emulator (`simulation/device_emulator.py`, reference profile `apartment_reference_v1`) posted one reading per second; each step closed a 15-minute model interval.
In interval 1 the manager reported done while every switch was left off.

| Interval | Plan | Actual switches | Manager report | Readings | Mean pump W | Mean EV W | Tank L | Verdict from readings | New proposal |
|---|---|---|---|---|---|---|---|---|---|
| 0 | pump OFF, EV ON | pump OFF, EV ON | - | 15 | 0 | 3310 | 4447 | **OBSERVED_MATCH**  | - |
| 1 | pump OFF, EV ON | pump OFF, EV OFF | done (ev) | 15 | 0 | 0 | 4376 | **OBSERVED_DEVIATION** EV_CHARGING_NOT_OBSERVED | CLAIM_WITHOUT_OBSERVED_EXECUTION |
| 2 | pump OFF, EV ON | pump OFF, EV ON | - | 15 | 0 | 3281 | 4340 | **OBSERVED_MATCH**  | - |
| 3 | pump OFF, EV ON | pump OFF, EV ON | - | 15 | 0 | 3277 | 4243 | **OBSERVED_MATCH**  | - |

- interval 0: manager accepted proposal (PEAK_ADVISORY_ISSUED)
- interval 2: manager accepted proposal (CLAIM_WITHOUT_OBSERVED_EXECUTION)

Report counts: {"proposals": 2, "acceptances": 2, "claims": 1, "observed_deviations": 1, "claims_contradicted": 1}. Observation coverage: 4 of 4 intervals.

**All readings are `source_kind=synthetic`** (emulated device, not a physical sensor). Acceptance never switched anything; the manager's report stayed on record after the readings contradicted it, and the revision was not active until accepted.
