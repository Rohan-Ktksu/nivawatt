"""Deterministic deadline-aware rules scheduler (source="rules"). Pure: no DB or hardware writes.

Priority is sequential, not a weighted objective: (1) keep tank >= reserve, (2) meet EV energy before
departure, both inside the participating-load allowance, preferring intervals outside advisory peak windows.
Infeasible service is reported as a quantified shortfall, never hidden.
"""
import time

EPS = 1e-9


def plan(current_state, known_events, requirements, constraints):
    t0 = time.perf_counter()
    st, c = current_state, constraints
    start, end = st["interval_index"], c["horizon_intervals"]
    dt_h = c["model_dt_minutes"] / 60
    idx = list(range(start, end))
    peak = set(known_events.get("peak_intervals", []))
    source_ok = known_events.get("source_water_available", {})  # interval -> bool (known outages)
    withdraw = c["expected_withdrawal_l"]
    allow = c["allowance_model_kw"]
    pump_kw, ev_kw, inflow = c["pump_model_kw"], c["ev_charger_model_kw"], c["pump_inflow_lph"] * dt_h
    pump = {i: False for i in idx}
    ev = {i: None for i in idx}  # ev_id charging in interval (one charger)
    infeas = []

    def load(i):
        return (pump_kw if pump[i] else 0) + (ev_kw if ev[i] else 0)

    def tank_path():
        v, path, unmet, viol = st["tank_l"], [], 0.0, []
        for i in idx:
            if pump[i] and source_ok.get(i, True):
                v += inflow
            v = min(v, c["tank_max_l"])  # overflow protection is physical, independent of the plan
            w = withdraw[i]
            served = min(w, v)
            unmet += w - served
            v -= served
            path.append(round(v, 1))
            if v < c["tank_min_l"] - EPS:
                viol.append(i)
        return path, unmet, viol

    # 1) water: add pump slots before the first reserve violation, latest-feasible-first? No: earliest
    #    non-peak slot after the previous fill keeps reserve margin; fall back to peak slots.
    for _ in range(len(idx)):
        path, _, viol = tank_path()
        if not viol:
            break
        first = viol[0]
        cands = [i for i in idx if i <= first and not pump[i] and source_ok.get(i, True)
                 and load(i) + pump_kw <= allow + EPS and _fits(path, idx, i, inflow, c["tank_max_l"])]
        if not cands:
            break
        cands.sort(key=lambda i: (i in peak, -i))  # non-peak first, then as late as possible before need
        pump[cands[0]] = True
    path, unmet_water, viol = tank_path()
    if viol:
        infeas.append({"kind": "WATER_RESERVE", "intervals_below_reserve": len(viol),
                       "first_interval": viol[0], "unmet_withdrawal_l": round(unmet_water, 1)})

    # 2) EV energy before departure (earliest-deadline first), non-peak preferred.
    ev_traj, shortfall = {}, {}
    for s in sorted(requirements.get("ev_sessions", []), key=lambda e: e["departure_interval"]):
        need = s["remaining_model_kwh"]
        slots = [i for i in idx if s["arrival_interval"] <= i < s["departure_interval"] and ev[i] is None
                 and load(i) + ev_kw <= allow + EPS]
        slots.sort(key=lambda i: (i in peak, i))
        for i in slots:
            if need <= EPS:
                break
            ev[i] = s["ev_id"]
            need -= min(ev_kw * dt_h, need)
        shortfall[s["ev_id"]] = round(max(need, 0.0), 3)
        if need > EPS:
            infeas.append({"kind": "EV_ENERGY", "ev_id": s["ev_id"], "shortfall_model_kwh": round(need, 3)})
        got, cum = s["remaining_model_kwh"], 0.0
        traj = []
        for i in idx:
            if ev[i] == s["ev_id"]:
                cum = min(got, cum + ev_kw * dt_h)
            traj.append(round(cum, 3))
        ev_traj[s["ev_id"]] = traj

    loads = [load(i) for i in idx]
    starts, prev = 0, bool(st.get("pump_on"))  # unknown pump state counts as OFF for planned starts
    for i in idx:
        starts += pump[i] and not prev
        prev = pump[i]
    option = {
        "option_id": "o1",
        "label": "Rules schedule: water reserve first, then EV energy, outside peak windows when possible",
        "effective_from_interval": start,
        "actions": [{"interval_index": i, "pump": "ON" if pump[i] else "OFF", "ev": ev[i] or "OFF"} for i in idx],
        "predicted_peak_model_kw": round(max(loads, default=0), 3),
        "predicted_peak_window_energy_model_kwh": round(sum(l * dt_h for i, l in zip(idx, loads) if i in peak), 3),
        "water_trajectory_model_l": path,
        "predicted_min_tank_model_l": min(path, default=st["tank_l"]),
        "ev_energy_trajectory_model_kwh": ev_traj,
        "ev_shortfall_model_kwh": shortfall,
        "water_shortfall": {"intervals_below_reserve": len(viol), "unmet_withdrawal_l": round(unmet_water, 1)},
        "pump_starts": {"history": st.get("pump_starts_history"), "planned": starts},  # history None = not measurable
        "requires_operator_exception": False,
        "assumptions": ["expected withdrawal profile is a planning estimate",
                        "source water available unless a known outage event says otherwise",
                        "manual switching; acceptance does not operate equipment"],
    }
    return {"source": "rules", "options": [option], "infeasibilities": infeas,
            "computation_ms": round((time.perf_counter() - t0) * 1000, 2)}


def _fits(path, idx, i, inflow, vmax):
    """Adding inflow at i must not push the planned tank above capacity at i (no planned overflow)."""
    before = path[idx.index(i) - 1] if idx.index(i) > 0 else None
    return before is None or before + inflow <= vmax + EPS
