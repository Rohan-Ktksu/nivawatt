"""Synthetic apartment plant: tank mass balance, pump and EV-charging emulator, in model units.

Truth lives here only. Policies see observations. Switch positions change only through explicit
(simulated human) actions, never through proposal acceptance.
"""
import copy

DEFAULT_PARAMS = {
    "source_kind": "synthetic",
    "apartment_id": "APT_1",
    "model_dt_minutes": 15,
    "horizon_intervals": 96,
    "tank_max_l": 10000, "tank_min_l": 3000, "tank_init_l": 4500,
    "pump_inflow_lph": 6000, "pump_model_kw": 2.2,
    "ev_charger_model_kw": 3.3,
    "allowance_model_kw": 6.0,
    # Planning estimate == synthetic truth here; experiments may add disturbances to truth only.
    "withdrawal_profile_l": None,
    "source_outage_intervals": [],
    "ev_sessions": [{"ev_id": "EV_1", "arrival_interval": 0, "departure_interval": 32, "requested_model_kwh": 10}],
}


def default_withdrawals(n=96):
    """Synthetic daily profile (litres per 15 min): morning and evening use peaks. Not measured."""
    out = []
    for i in range(n):
        h = i * 15 / 60
        out.append(250 if 6 <= h < 9 else 200 if 18 <= h < 21 else 60 if 0 <= h < 5 else 110)
    return out


def make_params(overrides=None):
    p = copy.deepcopy(DEFAULT_PARAMS)
    p.update(overrides or {})
    if not p["withdrawal_profile_l"]:
        p["withdrawal_profile_l"] = default_withdrawals(p["horizon_intervals"])
    if len(p["withdrawal_profile_l"]) != p["horizon_intervals"]:
        raise ValueError("withdrawal_profile_l length must equal horizon_intervals")
    if not 0 <= p["tank_min_l"] <= p["tank_max_l"] or not 0 <= p["tank_init_l"] <= p["tank_max_l"]:
        raise ValueError("tank bounds invalid")
    for k in ("pump_inflow_lph", "pump_model_kw", "ev_charger_model_kw", "allowance_model_kw"):
        if p[k] < 0:
            raise ValueError(f"{k} must be >= 0")
    for s in p["ev_sessions"]:
        if not 0 <= s["arrival_interval"] < s["departure_interval"] <= p["horizon_intervals"] or s["requested_model_kwh"] < 0:
            raise ValueError(f"invalid EV session {s['ev_id']}")
    return p


def initial_truth(p):
    return {"tank_l": float(p["tank_init_l"]), "pump_on": False, "ev_on": False, "pump_starts": 0,
            "ev_delivered_model_kwh": {s["ev_id"]: 0.0 for s in p["ev_sessions"]},
            "unmet_water_l": 0.0, "overflow_l": 0.0}


def step(truth, p, i, pump_on, ev_on):
    """Advance interval i with actual switch positions. Returns (new_truth, interval_record)."""
    t = copy.deepcopy(truth)
    dt_h = p["model_dt_minutes"] / 60
    t["pump_starts"] += bool(pump_on and not t["pump_on"])
    t["pump_on"], t["ev_on"] = pump_on, ev_on
    source = i not in p["source_outage_intervals"]
    inflow = p["pump_inflow_lph"] * dt_h if (pump_on and source) else 0.0  # dry pump draws power, moves no water
    v = t["tank_l"] + inflow
    t["overflow_l"] += max(0.0, v - p["tank_max_l"])
    v = min(v, p["tank_max_l"])
    w = p["withdrawal_profile_l"][i]
    served = min(w, v)
    t["unmet_water_l"] += w - served
    t["tank_l"] = v - served
    ev_kwh = 0.0
    if ev_on:
        for s in p["ev_sessions"]:  # single charger: first present EV with remaining request
            rem = s["requested_model_kwh"] - t["ev_delivered_model_kwh"][s["ev_id"]]
            if s["arrival_interval"] <= i < s["departure_interval"] and rem > 1e-9:
                ev_kwh = min(p["ev_charger_model_kw"] * dt_h, rem)
                t["ev_delivered_model_kwh"][s["ev_id"]] += ev_kwh
                ev_id = s["ev_id"]
                break
    pump_kw = p["pump_model_kw"] if pump_on else 0.0
    ev_kw = ev_kwh / dt_h
    rec = {"interval_index": i, "tank_l": round(t["tank_l"], 2), "inflow_l": round(inflow, 2), "withdrawal_l": w,
           "source_water_available": source, "pump_model_kw": pump_kw, "ev_model_kw": round(ev_kw, 4),
           "ev_id": ev_id if ev_kwh else None, "aggregate_model_kw": round(pump_kw + ev_kw, 4),
           "unmet_water_l": round(t["unmet_water_l"], 2), "overflow_l": round(t["overflow_l"], 2)}
    return t, rec
