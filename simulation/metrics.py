"""Outcome metrics computed from evaluator truth records (one per simulated interval)."""

METRIC_DEFINITIONS = {
    "peak_participating_model_kw": "max interval-average pump+EV model kW over simulated intervals",
    "allowance_exceedance_model_kwh": "sum(max(0, P - allowance) * dt_h); outage intervals get no reduction credit",
    "peak_window_energy_model_kwh": "participating energy inside advisory peak intervals",
    "reserve_violation_intervals": "intervals ending with tank below reserve",
    "unmet_withdrawal_l": "water demanded but not available (physically empty tank)",
    "ev_shortfall_at_departure_model_kwh": "requested - delivered by departure, per EV; null if departure not reached",
    "pump_starts": "OFF->ON transitions of the actual pump",
}


def run_metrics(p, truth, peak_intervals):
    dt_h = p["model_dt_minutes"] / 60
    n = len(truth)
    delivered = {s["ev_id"]: 0.0 for s in p["ev_sessions"]}
    by_dep = {}
    peak_kw = exceed = peak_e = total_e = 0.0
    viol = starts = 0
    prev_pump = False
    for rec in truth:
        i, kw = rec["interval_index"], rec["aggregate_model_kw"]
        peak_kw = max(peak_kw, kw)
        exceed += max(0.0, kw - rec.get("allowance_model_kw", p["allowance_model_kw"])) * dt_h
        total_e += kw * dt_h
        if i in peak_intervals:
            peak_e += kw * dt_h
        viol += rec["tank_l"] < p["tank_min_l"] - 1e-9
        on = rec["pump_model_kw"] > 0
        starts += on and not prev_pump
        prev_pump = on
        if rec.get("ev_id"):
            delivered[rec["ev_id"]] += rec["ev_model_kw"] * dt_h
        for s in p["ev_sessions"]:
            if i + 1 == s["departure_interval"]:
                by_dep[s["ev_id"]] = delivered[s["ev_id"]]
    ev_short = {}
    for s in p["ev_sessions"]:
        if s["ev_id"] in by_dep:
            ev_short[s["ev_id"]] = round(max(0.0, s["requested_model_kwh"] - by_dep[s["ev_id"]]), 4)
        else:
            ev_short[s["ev_id"]] = None  # departure not yet reached
    return {
        "intervals_simulated": n,
        "model_dt_minutes": p["model_dt_minutes"],
        "peak_participating_model_kw": round(peak_kw, 4),
        "allowance_exceedance_model_kwh": round(exceed, 4),
        "peak_window_energy_model_kwh": round(peak_e, 4),
        "total_participating_energy_model_kwh": round(total_e, 4),
        "reserve_violation_intervals": viol,
        "unmet_withdrawal_l": round(truth[-1]["unmet_water_l"], 2) if truth and truth[-1].get("unmet_water_l") is not None
        else (0.0 if not truth else None),
        "final_tank_l": truth[-1]["tank_l"] if truth else p["tank_init_l"],
        "ev_shortfall_at_departure_model_kwh": ev_short,
        "ev_delivered_model_kwh": {k: round(v, 4) for k, v in delivered.items()},
        "pump_starts": starts,
        "definitions": METRIC_DEFINITIONS,
    }
