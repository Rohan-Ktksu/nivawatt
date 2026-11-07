"""Paired policy comparison on the synthetic apartment (simulation only; not a bench result).

Policies
- uncoordinated (automatic_local): float-switch pump, EV charges on arrival until full. Context only.
- demand_cap (automatic_local): same, but EV pauses whenever pump+EV would exceed the allowance (water priority).
- fixed_plan (human_advisory): one rules plan at t=0, never revised.
- ack_replan (human_advisory): rules scheduler; tank from observations; EV progress credited from done claims.
- measured_replan (human_advisory): same scheduler and same tank observations; EV progress from measured EV energy.
- aggregate_replan (human_advisory): same scheduler and tank observations, but only one meter on the combined
  participating circuits. EV progress = claimed energy, withdrawn only where the aggregate reading is zero
  (claim contradicted). It never attributes energy to an individual EV from the aggregate (observability variant).

Shared across policies within a seed: plant parameters, withdrawal disturbance, advisory peak intervals, and the
human-response draws (a miss for interval i / action kind applies to whichever policy issues that action).
The human claims done for every instructed ON action, including missed ones (false done). Policies never see truth.
Automatic policies are a different authority class: they are not subject to human misses.

Run: python -m simulation.experiment   -> results/experiments/<id>/{runs.csv,summary.json}
"""
import copy
import csv
import json
import os
import random
import statistics
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from scheduler import rules
from simulation import plant
from simulation.metrics import run_metrics

ROOT = Path(__file__).resolve().parent.parent
POLICIES = ["uncoordinated", "demand_cap", "fixed_plan", "ack_replan", "measured_replan", "aggregate_replan"]
# Electrical meters each policy relies on (tank sensor common to the advisory ones). Prices unknown until the BOM exists.
ELECTRICAL_METERS = {"uncoordinated": 0, "demand_cap": 2, "fixed_plan": 0, "ack_replan": 0, "measured_replan": 2,
                     "aggregate_replan": 1}
SCENARIOS = {
    "perfect": {"p_miss_pump": 0, "p_miss_ev": 0, "p_drop": 0, "stochastic": False},
    "missed_ev_false_done": {"p_miss_pump": 0, "p_miss_ev": 0.3, "p_drop": 0, "stochastic": True},
    "missed_pump_false_done": {"p_miss_pump": 0.3, "p_miss_ev": 0, "p_drop": 0, "stochastic": True},
    "stale_telemetry": {"p_miss_pump": 0, "p_miss_ev": 0.15, "p_drop": 0.2, "stochastic": True},
    "extra_withdrawal": {"p_miss_pump": 0, "p_miss_ev": 0, "p_drop": 0, "withdrawal_noise": 0.3, "stochastic": True},
    # Default day has no load in the 10:00-13:00 IST advisory hours; this case exercises shifting and the cap.
    "daytime_ev_tight_allowance": {"p_miss_pump": 0, "p_miss_ev": 0.15, "p_drop": 0, "stochastic": True,
                                   "params": {"allowance_model_kw": 4.0,
                                              "ev_sessions": [{"ev_id": "EV_1", "arrival_interval": 36,
                                                               "departure_interval": 72, "requested_model_kwh": 10}]}},
    # Pump and EV overlap (low tank, daytime EV) so non-zero aggregate readings cannot reveal a missed EV action.
    "missed_ev_overlapping_pump": {"p_miss_pump": 0, "p_miss_ev": 0.3, "p_drop": 0, "stochastic": True,
                                   "params": {"tank_init_l": 3200, "allowance_model_kw": 6.0}},
    "infeasible_ev": {"p_miss_pump": 0, "p_miss_ev": 0, "p_drop": 0, "stochastic": False,
                      "params": {"ev_sessions": [{"ev_id": "EV_1", "arrival_interval": 0, "departure_interval": 32,
                                                  "requested_model_kwh": 40}]}},
}
TANK_TOL_L, EV_TOL_KWH = 50.0, 0.05


def constraints(p):
    c = {k: p[k] for k in ("horizon_intervals", "model_dt_minutes", "tank_max_l", "tank_min_l", "pump_model_kw",
                           "ev_charger_model_kw", "pump_inflow_lph", "allowance_model_kw")}
    c["expected_withdrawal_l"] = p["withdrawal_profile_l"]  # planner's estimate (truth may differ)
    return c


def run_policy(policy, base_p, truth_withdrawal, draws, scen, peaks):
    p_plan = base_p
    p_true = {**copy.deepcopy(base_p), "withdrawal_profile_l": truth_withdrawal}
    n, dt_h = base_p["horizon_intervals"], base_p["model_dt_minutes"] / 60
    t = plant.initial_truth(p_true)
    log, plans, deviations_seen = [], 0, 0
    obs_tank, credited = base_p["tank_init_l"], {s["ev_id"]: 0.0 for s in base_p["ev_sessions"]}
    plan_opt, missed_ev_actions = None, 0
    for i in range(n):
        if policy in ("uncoordinated", "demand_cap"):
            pump = t["tank_l"] < base_p["tank_min_l"] + 500 or (t["pump_on"] and t["tank_l"] < base_p["tank_max_l"] - 500)
            ev = True
            if policy == "demand_cap" and pump and base_p["pump_model_kw"] + base_p["ev_charger_model_kw"] > base_p["allowance_model_kw"]:
                ev = False
        else:
            need_plan = plan_opt is None
            if policy != "fixed_plan" and plan_opt is not None and i > plan_opt["effective_from_interval"]:
                k = i - 1 - plan_opt["effective_from_interval"]
                exp_tank = plan_opt["water_trajectory_model_l"][k]
                exp_ev = {e: plan_opt["ev_energy_trajectory_model_kwh"][e][k] + plan_base[e]
                          for e in plan_opt["ev_energy_trajectory_model_kwh"]}
                if abs(obs_tank - exp_tank) > TANK_TOL_L or any(abs(credited[e] - exp_ev[e]) > EV_TOL_KWH for e in exp_ev):
                    need_plan = True
                    deviations_seen += 1
            if need_plan:
                st = {"interval_index": i, "tank_l": obs_tank, "pump_on": t["pump_on"]}
                reqs = {"ev_sessions": [{**s, "remaining_model_kwh": max(0.0, s["requested_model_kwh"] - credited[s["ev_id"]])}
                                        for s in base_p["ev_sessions"]]}
                plan_opt = rules.plan(st, {"peak_intervals": peaks}, reqs, constraints(p_plan))["options"][0]
                plan_base = dict(credited)
                plans += 1
            a = plan_opt["actions"][i - plan_opt["effective_from_interval"]] if i >= plan_opt["effective_from_interval"] else None
            want_pump = bool(a and a["pump"] == "ON")
            want_ev = bool(a and a["ev"] != "OFF")
            pump = want_pump and draws["pump"][i] >= scen["p_miss_pump"]
            ev = want_ev and draws["ev"][i] >= scen["p_miss_ev"]
            missed_ev_actions += want_ev and not ev
        t, rec = plant.step(t, p_true, i, pump, ev)
        rec["allowance_model_kw"] = base_p["allowance_model_kw"]
        log.append(rec)
        # observations available to policies (identical tank observations for ack and measured)
        dropped = draws["drop"][i] < scen["p_drop"]
        if not dropped:
            obs_tank = rec["tank_l"]
        if policy == "measured_replan":
            if not dropped and rec["ev_id"]:
                credited[rec["ev_id"]] += rec["ev_model_kw"] * dt_h  # no credit without a measurement
        elif policy == "aggregate_replan" and plan_opt is not None:
            if want_ev and (dropped or rec["aggregate_model_kw"] > 0):  # a zero reading contradicts the claim
                e = a["ev"]
                sess = next(s for s in base_p["ev_sessions"] if s["ev_id"] == e)
                credited[e] = min(sess["requested_model_kwh"], credited[e] + base_p["ev_charger_model_kw"] * dt_h)
        elif policy in ("ack_replan", "fixed_plan") and plan_opt is not None:
            if want_ev:  # human claims every instructed action as done
                e = a["ev"]
                sess = next(s for s in base_p["ev_sessions"] if s["ev_id"] == e)
                credited[e] = min(sess["requested_model_kwh"], credited[e] + base_p["ev_charger_model_kw"] * dt_h)
    m = run_metrics(p_true, log, set(peaks))
    m.update({"plans_computed": plans, "deviations_detected": deviations_seen, "missed_ev_actions": missed_ev_actions,
              "electrical_meters": ELECTRICAL_METERS[policy],
              "authority": "automatic_local" if policy in ("uncoordinated", "demand_cap") else "human_advisory"})
    return m


def draws_for(seed, n, scen, base_withdrawal):
    rng = random.Random(seed)
    d = {k: [rng.random() for _ in range(n)] for k in ("pump", "ev", "drop")}
    noise = scen.get("withdrawal_noise", 0)
    w = [round(x * (1 + rng.uniform(-noise, noise)), 1) for x in base_withdrawal] if noise else list(base_withdrawal)
    return d, w


def run(scenarios=None, policies=None, n_seeds=20, peaks=None, params=None):
    scenarios, policies = scenarios or list(SCENARIOS), policies or POLICIES
    unknown = (set(scenarios) - set(SCENARIOS)) | (set(policies) - set(POLICIES))
    if unknown:
        raise ValueError(f"unknown scenario/policy {sorted(unknown)}")
    peaks = list(range(40, 52)) if peaks is None else peaks
    rows = []
    for sname in scenarios:
        scen = SCENARIOS[sname]
        p = plant.make_params({**(params or {}), **scen.get("params", {})})
        seeds = list(range(n_seeds)) if scen["stochastic"] else [0]
        for seed in seeds:
            d, w = draws_for(seed, p["horizon_intervals"], scen, p["withdrawal_profile_l"])
            for pol in policies:
                m = run_policy(pol, p, w, d, scen, peaks)
                rows.append({"scenario": sname, "seed": seed, "policy": pol, "authority": m["authority"],
                             "electrical_meters": m["electrical_meters"],
                             "peak_participating_model_kw": m["peak_participating_model_kw"],
                             "allowance_exceedance_model_kwh": m["allowance_exceedance_model_kwh"],
                             "peak_window_energy_model_kwh": m["peak_window_energy_model_kwh"],
                             "total_participating_energy_model_kwh": m["total_participating_energy_model_kwh"],
                             "reserve_violation_intervals": m["reserve_violation_intervals"],
                             "unmet_withdrawal_l": m["unmet_withdrawal_l"], "final_tank_l": m["final_tank_l"],
                             "ev_shortfall_model_kwh": sum(v or 0 for v in m["ev_shortfall_at_departure_model_kwh"].values()),
                             "pump_starts": m["pump_starts"], "plans_computed": m["plans_computed"],
                             "deviations_detected": m["deviations_detected"], "missed_ev_actions": m["missed_ev_actions"]})
    return rows, summarize(rows), {"peak_intervals": peaks, "seeds_per_stochastic_scenario": n_seeds,
                                   "scenarios": {s: SCENARIOS[s] for s in scenarios}, "policies": policies}


METRICS = ["peak_participating_model_kw", "allowance_exceedance_model_kwh", "peak_window_energy_model_kwh",
           "reserve_violation_intervals", "unmet_withdrawal_l", "ev_shortfall_model_kwh", "pump_starts"]


def summarize(rows):
    out = {}
    for s in sorted({r["scenario"] for r in rows}):
        out[s] = {}
        for pol in sorted({r["policy"] for r in rows}, key=POLICIES.index):
            rs = [r for r in rows if r["scenario"] == s and r["policy"] == pol]
            out[s][pol] = {"runs": len(rs), **{m: {"mean": round(statistics.mean(r[m] for r in rs), 4),
                                                   "sd": round(statistics.pstdev(r[m] for r in rs), 4)} for m in METRICS}}
        for name, base in (("paired_measured_minus_ack", "ack_replan"), ("paired_branch_minus_aggregate", "aggregate_replan")):
            a = {r["seed"]: r for r in rows if r["scenario"] == s and r["policy"] == base}
            b = {r["seed"]: r for r in rows if r["scenario"] == s and r["policy"] == "measured_replan"}
            if a and b:
                diffs = {m: [b[k][m] - a[k][m] for k in a if k in b] for m in METRICS}
                # negative = measured_replan (branch meters) lower, i.e. better for these lower-is-better metrics
                out[s][name] = {m: {"mean": round(statistics.mean(v), 4), "min": round(min(v), 4), "max": round(max(v), 4),
                                    "measured_better_runs": sum(x < -1e-9 for x in v), "ties": sum(abs(x) <= 1e-9 for x in v),
                                    "baseline_better_runs": sum(x > 1e-9 for x in v)} for m, v in diffs.items()}
    return out


def commit():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "simulation", "scheduler"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return (sha + "-dirty" if dirty else sha) or None
    except OSError:
        return None


def export(rows, summary, config, exp_id=None):
    exp_id = exp_id or f"exp-{uuid.uuid4().hex[:8]}"
    d = Path(os.environ.get("NIVAWATT_RESULTS_DIR", ROOT / "results" / "experiments")) / exp_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    doc = {"experiment_id": exp_id, "source_kind": "synthetic_simulation", "software_commit": commit(),
           "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "config": config,
           "summary": summary, "notes": __doc__.split("Run:")[0].strip(),
           "limitations": ["synthetic plant and human-response model; not field or bench evidence",
                           "automatic_local policies have different control authority than human_advisory ones",
                           "initial seed set, not a significance test"]}
    (d / "summary.json").write_text(json.dumps(doc, indent=2))
    return exp_id, d


if __name__ == "__main__":
    rows, summary, cfg = run()
    eid, d = export(rows, summary, cfg, "exp-default")
    print(f"wrote {d} ({len(rows)} runs)")
    for s, v in summary.items():
        pm = v.get("paired_measured_minus_ack", {}).get("ev_shortfall_model_kwh")
        print(s, {pol: (v[pol]["ev_shortfall_model_kwh"]["mean"], v[pol]["reserve_violation_intervals"]["mean"],
                        v[pol]["peak_window_energy_model_kwh"]["mean"]) for pol in POLICIES if pol in v}, "paired EV:", pm)
