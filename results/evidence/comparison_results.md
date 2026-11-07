# Simulated policy comparison

Source: `results/experiments/exp-default/` (generated at commit `1512d28`, 20 seeds per stochastic scenario). **Synthetic simulation, not bench evidence.**

Mean per run. EV = energy short at departure (model kWh). Reserve = 15-min intervals below the water reserve. Peak = participating energy inside advisory hours (model kWh).

| Scenario | Metric | uncoordinated | demand_cap | fixed_plan | ack_replan | aggregate_replan | measured_replan |
|---|---|---|---|---|---|---|---|
| daytime_ev_tight_allowance | EV | 0 | 0 | 1.3375 | 1.3375 | 0 | 0 |
| daytime_ev_tight_allowance | Reserve | 0 | 0 | 0 | 0 | 0 | 0 |
| daytime_ev_tight_allowance | Peak | 6.7 | 6.7 | 0 | 0 | 0 | 0 |
| extra_withdrawal | EV | 0 | 0 | 0 | 0 | 0 | 0 |
| extra_withdrawal | Reserve | 0 | 0 | 3.8 | 0.8 | 0.8 | 0.8 |
| extra_withdrawal | Peak | 0 | 0 | 0 | 0 | 0 | 0 |
| infeasible_ev | EV | 13.6 | 13.6 | 13.6 | 13.6 | 13.6 | 13.6 |
| infeasible_ev | Reserve | 0 | 0 | 0 | 0 | 0 | 0 |
| infeasible_ev | Peak | 0 | 0 | 0 | 0 | 0 | 0 |
| missed_ev_false_done | EV | 0 | 0 | 2.9463 | 2.9463 | 0.005 | 0 |
| missed_ev_false_done | Reserve | 0 | 0 | 0 | 0 | 0 | 0 |
| missed_ev_false_done | Peak | 0 | 0 | 0 | 0 | 0 | 0 |
| missed_ev_overlapping_pump | EV | 0 | 0 | 2.9463 | 2.9463 | 0.035 | 0 |
| missed_ev_overlapping_pump | Reserve | 0 | 0 | 0 | 0 | 0 | 0 |
| missed_ev_overlapping_pump | Peak | 0 | 0 | 0 | 0 | 0 | 0 |
| missed_pump_false_done | EV | 0 | 0 | 0 | 0 | 0 | 0 |
| missed_pump_false_done | Reserve | 0 | 0 | 57 | 3.15 | 3.15 | 3.15 |
| missed_pump_false_done | Peak | 0 | 0 | 0 | 0.165 | 0.165 | 0.165 |
| perfect | EV | 0 | 0 | 0 | 0 | 0 | 0 |
| perfect | Reserve | 0 | 0 | 0 | 0 | 0 | 0 |
| perfect | Peak | 0 | 0 | 0 | 0 | 0 | 0 |
| stale_telemetry | EV | 0 | 0 | 1.2038 | 1.2038 | 0.04 | 0 |
| stale_telemetry | Reserve | 0 | 0 | 0 | 1.65 | 1.65 | 1.65 |
| stale_telemetry | Peak | 0 | 0 | 0 | 0 | 0 | 0 |

## Paired comparisons (same seed, same human behaviour)

| Scenario | Measured vs acknowledgement: EV better / tie / worse | Branch vs aggregate meter: EV better / tie / worse |
|---|---|---|
| daytime_ev_tight_allowance | 20 / 0 / 0 | 0 / 20 / 0 |
| extra_withdrawal | 0 / 20 / 0 | 0 / 20 / 0 |
| infeasible_ev | 0 / 1 / 0 | 0 / 1 / 0 |
| missed_ev_false_done | 20 / 0 / 0 | 1 / 19 / 0 |
| missed_ev_overlapping_pump | 20 / 0 / 0 | 7 / 13 / 0 |
| missed_pump_false_done | 0 / 20 / 0 | 0 / 20 / 0 |
| perfect | 0 / 1 / 0 | 0 / 1 / 0 |
| stale_telemetry | 18 / 2 / 0 | 8 / 12 / 0 |

## Reading this honestly

- With perfect execution every policy ties; the advantage comes only from catching false or missed actions.
- Missed pump actions tie between acknowledgement and measured replanning because both see the same tank level.
- With stale telemetry the fixed plan beats both replanners on water: stale tank readings mislead replanning.
- Automatic policies (uncoordinated, demand_cap) have more control authority and are not subject to human misses; their water results are not a scheduling comparison.
- The demand cap never bound in these runs, so it equals uncoordinated.
- A single aggregate meter checked against claims catches most false EV claims; branch meters add a small gain when loads overlap.
