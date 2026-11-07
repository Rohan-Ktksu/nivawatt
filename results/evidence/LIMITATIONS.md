# Limitations (state these when presenting)

- **No physical bench yet.** Apartment readings come from the server simulator or the device emulator (`source_kind=synthetic`). The telemetry path works end to end, but sensor noise, delay and calibration are unmeasured.
- **Regional data, not local.** The forecast uses Karnataka state load. It does not describe a BESCOM feeder, transformer or apartment, and it never sets an apartment allowance.
- **Historical replay.** Forecasts are backtests on archived data; the publication delay of KPTCL reports is not validated, and there is no live utility connection.
- **Small evaluation.** Forecast test set: 14 days. Policy comparison: synthetic plant, synthetic human behaviour, 20 seeds per stochastic scenario; not a significance test.
- **Reference apartment values** (3 HP pump, 10,000 L tank, 3.3 kW charger) come from public threads and articles; pump flow is our estimate.
- **Rules scheduler, not an optimiser.** Water reserve first, then EV energy; no minimum pump run time.
- **Charging load is not a battery.** Charger energy is electrical delivery, not vehicle state of charge.
- **No savings claims.** Nothing here measures bill, emissions or grid-outage effects.
- **Local demo security only.** Access codes are demo sessions, not production authentication.
- **Utility smart meter: not connected.** No authorized interval export exists for this prototype.
