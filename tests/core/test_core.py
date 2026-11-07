import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from forecasting import data, evaluate, models
from scheduler import rules
from simulation import plant

HAS_DATA = data.RAW.exists()
FS = "2026-08-18T18:30:00Z"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("NIVAWATT_DB", str(tmp_path / "t.db"))
    codes = tmp_path / "codes.json"
    codes.write_text(json.dumps({"operator_code": "op", "manager_codes": {"APT_1": "m1", "APT_2": "m2"},
                                 "device_tokens": {"bench-1": "devtok"}}))
    monkeypatch.setenv("NIVAWATT_CODES", str(codes))
    monkeypatch.setenv("NIVAWATT_RESULTS_DIR", str(tmp_path / "exp"))
    from backend import db, main
    db.reset()
    c = TestClient(main.app)

    def login(role, apt=None, code=None):
        r = c.post("/api/v1/demo/session", json={"role": role, "apartment_id": apt, "access_code": code})
        return {"Authorization": "Bearer " + r.json()["token"]}
    c.op, c.mgr, c.mgr2 = login("operator", code="op"), login("manager", "APT_1", "m1"), login("manager", "APT_2", "m2")
    c.dev = {"Authorization": "Bearer devtok"}
    yield c
    db.reset()


def new_run(c, **params):
    r = c.post("/api/v1/runs", headers=c.op, json={"request_id": f"run-{len(params)}-{id(params)}",
                                                   "clock_start_utc": FS, "apartment_params": params})
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def synthetic_forecast(c):
    """Insert a synthetic snapshot directly so API tests do not depend on the dataset."""
    from backend import db
    hours = pd.date_range(FS.replace("Z", ""), periods=24, freq="h")
    pts = [{"start": models.iso(t), "end": models.iso(t + models.H), "predicted_mw": 1000 + i} for i, t in enumerate(hours)]
    snap = {"forecast_id": "fc-synth", "source_kind": "synthetic", "geographic_scope": "Synthetic", "points": pts,
            "forecast_start": pts[0]["start"], "forecast_end": pts[-1]["end"], "peak_windows": pts[-3:]}
    with db.LOCK:
        db.ex("INSERT OR IGNORE INTO forecasts VALUES(?,?,?)", "fc-synth", db.dumps(snap), "x")
    return snap


def advise(c, run_id, windows, rid="adv-1", kfi=0):
    return c.post("/api/v1/events", headers=c.op, json={
        "request_id": rid, "run_id": run_id, "kind": "peak_advisory", "known_from_interval": kfi,
        "forecast_id": "fc-synth", "target_apartments": ["APT_1"], "peak_windows": windows,
        "valid_from": FS, "valid_until": "2026-08-19T18:30:00Z"})


def state(c, run_id, h=None):
    return c.get(f"/api/v1/state?run_id={run_id}&apartment_id=APT_1", headers=h or c.mgr).json()


def accept(c, run_id, prop, rid):
    return c.post(f"/api/v1/proposals/{prop['proposal_id']}/decision", headers=c.mgr, json={
        "run_id": run_id, "expected_revision": prop["revision"], "decision": "ACCEPT",
        "option_id": prop["options"][0]["option_id"], "request_id": rid})


def step(c, run_id, rid, **kw):
    r = c.post(f"/api/v1/runs/{run_id}/step", headers=c.op, json={"request_id": rid, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- the P0 loop ----------
def test_p0_loop_false_done_detected_and_revised(api):
    c = api
    snap = synthetic_forecast(c)
    run = new_run(c)
    assert state(c, run)["active_advisory"] is None
    # manager cannot issue an advisory
    r = c.post("/api/v1/events", headers=c.mgr, json={"request_id": "x", "run_id": run, "kind": "peak_advisory"})
    assert r.status_code == 403
    r = advise(c, run, snap["peak_windows"])
    assert r.status_code == 200, r.text
    adv = r.json()
    s = state(c, run)
    assert s["active_advisory"]["advisory_id"] == adv["advisory_id"] and s["forecast_id"] == "fc-synth"
    prop = s["pending_proposals"][0]
    assert prop["advisory_id"] == adv["advisory_id"] and prop["source"] == "rules"
    # accept exact version; retry is idempotent; acceptance does not operate equipment
    a1 = accept(c, run, prop, "acc-1")
    assert a1.status_code == 200
    assert accept(c, run, prop, "acc-1").json()["active_commitment"] == a1.json()["active_commitment"]
    assert accept(c, run, prop, "acc-2").status_code == 409  # already accepted -> stale
    s = state(c, run)
    com = s["active_commitment"]
    assert com and s["execution"]["observation_status"] == "UNOBSERVED"
    # find first interval where the plan wants something ON
    acts = com["option"]["actions"]
    first_on = next(a for a in acts if a["pump"] == "ON" or a["ev"] != "OFF")
    k = first_on["interval_index"]
    for j in range(k):  # follow the plan faithfully until then
        a = acts[j]
        step(c, run, f"s{j}", actual_switches={"pump": a["pump"], "ev": "ON" if a["ev"] != "OFF" else "OFF"})
    kind = "pump" if first_on["pump"] == "ON" else "ev"
    cl = c.post("/api/v1/execution/claims", headers=c.mgr, json={
        "run_id": run, "commitment_id": com["commitment_id"], "interval_index": k,
        "action_id": f"{com['commitment_id']}:{k}:{kind}", "request_id": "claim-1"})
    assert cl.status_code == 200 and cl.json()["status"] == "CLAIMED_EXECUTED"
    # claim does not make anything happen: switches stay OFF
    out = step(c, run, "s-false", actual_switches={"pump": "OFF", "ev": "OFF"})
    assert out["execution"]["observation_status"] == "OBSERVED_DEVIATION"
    s = out["state"]
    assert s["execution"]["claim"] == "CLAIMED_EXECUTED"  # claim preserved despite contradiction
    assert s["active_commitment"]["commitment_id"] == com["commitment_id"]  # revision not auto-activated
    rev = s["pending_proposals"][0]
    assert rev["reason"] == "CLAIM_WITHOUT_OBSERVED_EXECUTION" and rev["status"] == "PROPOSED"
    # accept the revision, actually perform it, observe a match
    assert accept(c, run, rev, "acc-rev").status_code == 200
    s = state(c, run)
    a = next(x for x in s["active_commitment"]["option"]["actions"] if x["interval_index"] == s["clock"]["interval_index"])
    out = step(c, run, "s-good", actual_switches={"pump": a["pump"], "ev": "ON" if a["ev"] != "OFF" else "OFF"})
    assert out["execution"]["observation_status"] == "OBSERVED_MATCH"
    rep = c.get(f"/api/v1/runs/{run}/report", headers=c.op).json()
    assert rep["counts"]["claims_contradicted"] == 1 and rep["counts"]["acceptances"] == 2
    # restart: new connection, same file -> history intact
    from backend import db
    db.reset()
    s2 = state(c, run)
    assert s2["active_commitment"]["commitment_id"] == s["active_commitment"]["commitment_id"]
    assert s2["execution"]["claims"] == s["execution"]["claims"]
    assert c.get(f"/api/v1/runs/{run}/report", headers=c.op).json()["counts"] == rep["counts"]


def test_authorization_and_scope(api):
    c = api
    run = new_run(c)
    assert c.get(f"/api/v1/state?run_id={run}&apartment_id=APT_1").status_code == 401
    assert c.get(f"/api/v1/state?run_id={run}&apartment_id=APT_1", headers=c.mgr2).status_code == 403
    assert c.post("/api/v1/runs", headers=c.mgr, json={"request_id": "r", "clock_start_utc": FS}).status_code == 403
    r = c.post("/api/v1/requirements", headers=c.mgr, json={"run_id": run, "request_id": "q", "allowance_model_kw": 99})
    assert r.status_code == 403
    assert state(c, run)["apartment"]["allowance_model_kw"] == 6.0
    assert c.post("/api/v1/demo/session", json={"role": "operator", "access_code": "bad"}).status_code == 401


def test_request_id_reuse_with_different_body_conflicts(api):
    c = api
    new_run(c)
    r = c.post("/api/v1/runs", headers=c.op, json={"request_id": "run-0-" , "clock_start_utc": FS})
    r2 = c.post("/api/v1/runs", headers=c.op, json={"request_id": "run-0-", "clock_start_utc": "2026-08-17T18:30:00Z"})
    assert r.status_code == 200 and r2.status_code == 409


def test_advisory_validation(api):
    c = api
    snap = synthetic_forecast(c)
    run = new_run(c)
    bad = [{"start": "2026-08-18T18:45:00Z", "end": "2026-08-18T19:45:00Z"}]
    assert advise(c, run, bad, "a1").status_code == 422  # not a forecast hour
    step(c, run, "s0")
    assert advise(c, run, snap["peak_windows"], "a2", kfi=0).status_code == 422  # retroactive
    # future-known advisory is not visible early
    assert advise(c, run, snap["peak_windows"], "a3", kfi=3).status_code == 200
    assert state(c, run)["active_advisory"] is None
    step(c, run, "s1"); step(c, run, "s2")
    assert state(c, run)["active_advisory"] is not None


def test_stale_revision_and_expiry(api, monkeypatch):
    c = api
    run = new_run(c)
    r1 = c.post("/api/v1/requirements", headers=c.mgr, json={"run_id": run, "request_id": "q1",
                "ev_sessions": [{"ev_id": "EV_1", "requested_model_kwh": 8}]}).json()["proposal"]
    r2 = c.post("/api/v1/requirements", headers=c.mgr, json={"run_id": run, "request_id": "q2",
                "ev_sessions": [{"ev_id": "EV_1", "requested_model_kwh": 9}]}).json()["proposal"]
    assert accept(c, run, r1, "a-old").status_code == 409  # superseded
    bad = dict(r2, revision=r2["revision"] - 1)
    assert accept(c, run, bad, "a-badrev").status_code == 409
    other = new_run(c, apartment_id="APT_1")
    resp = c.post(f"/api/v1/proposals/{r2['proposal_id']}/decision", headers=c.mgr, json={
        "run_id": other, "expected_revision": r2["revision"], "decision": "ACCEPT", "option_id": "o1", "request_id": "wr"})
    assert resp.status_code == 409
    from backend import db
    with db.LOCK:
        db.ex("UPDATE proposals SET expires_at='2000-01-01T00:00:00Z' WHERE proposal_id=?", r2["proposal_id"])
    assert accept(c, run, r2, "a-exp").status_code == 409
    assert state(c, run)["active_commitment"] is None


def test_impossible_requirement_shows_shortfall(api):
    c = api
    run = new_run(c)
    p = c.post("/api/v1/requirements", headers=c.mgr, json={"run_id": run, "request_id": "q",
               "ev_sessions": [{"ev_id": "EV_1", "requested_model_kwh": 500}]}).json()["proposal"]
    assert p["options"][0]["ev_shortfall_model_kwh"]["EV_1"] > 0
    assert any(x["kind"] == "EV_ENERGY" for x in p["infeasibilities"])


def test_pump_power_without_water_is_deviation(api):
    c = api
    run = new_run(c, source_outage_intervals=list(range(96)), tank_init_l=3100)
    p = c.post("/api/v1/requirements", headers=c.mgr, json={"run_id": run, "request_id": "q", "ev_sessions": []}).json()["proposal"]
    # planner does not know the (unannounced) outage, so it plans pumping
    assert accept(c, run, p, "a").status_code == 200
    acts = state(c, run)["active_commitment"]["option"]["actions"]
    k = next(a["interval_index"] for a in acts if a["pump"] == "ON")
    for j in range(k):
        step(c, run, f"s{j}", actual_switches={"pump": "OFF", "ev": "OFF"})
    out = step(c, run, "sk", actual_switches={"pump": "ON", "ev": "OFF"})
    assert "PUMP_POWER_WITHOUT_WATER_DELIVERY" in out["execution"]["reason"]


def test_stale_observation_is_not_zero(api):
    c = api
    run = new_run(c)
    step(c, run, "s0")
    out = step(c, run, "s1", drop_observation=True)
    s = out["state"]
    assert s["observation"]["quality"] == "STALE" and s["observation"]["aggregate_model_kw"] is None
    assert s["apartment"]["pump_state"] == "UNKNOWN"
    assert any("STALE" in w for w in s["warnings"])


def test_telemetry_duplicate_order_reboot(api):
    c = api
    run = new_run(c)
    base = {"run_id": run, "apartment_id": "APT_1", "device_id": "bench-1", "source_kind": "hardware",
            "voltage_v": 12.0, "pump_power_w": None}
    post = lambda **kw: c.post("/api/v1/telemetry", headers=c.dev, json={**base, **kw}).json()["status"]
    assert post(device_session_id="b1", seq_num=5) == "ACCEPTED"
    assert post(device_session_id="b1", seq_num=5) == "DUPLICATE"
    assert post(device_session_id="b1", seq_num=3) == "OUT_OF_ORDER"
    assert post(device_session_id="b2", seq_num=0) == "NEW_DEVICE_SESSION"
    assert c.post("/api/v1/telemetry", headers=c.mgr, json=base).status_code == 403
    raw = state(c, run)
    assert raw["observation"] is None  # telemetry alone does not fabricate a model observation


# ---------- pure components ----------
def test_plant_mass_balance_and_bounds():
    p = plant.make_params({"tank_init_l": 9900})
    t = plant.initial_truth(p)
    total_in = total_out = 0
    for i in range(96):
        t, rec = plant.step(t, p, i, pump_on=i % 3 == 0, ev_on=True)
        assert 0 <= rec["tank_l"] <= p["tank_max_l"]
        total_in += rec["inflow_l"]
        total_out += rec["withdrawal_l"]
    assert abs(9900 + total_in - t["overflow_l"] - (total_out - t["unmet_water_l"]) - t["tank_l"]) < 1e-6
    assert t["ev_delivered_model_kwh"]["EV_1"] <= 10 + 1e-9


def test_ev_stops_at_departure():
    p = plant.make_params({"ev_sessions": [{"ev_id": "E", "arrival_interval": 0, "departure_interval": 2, "requested_model_kwh": 50}]})
    t = plant.initial_truth(p)
    for i in range(5):
        t, _ = plant.step(t, p, i, False, True)
    assert abs(t["ev_delivered_model_kwh"]["E"] - 2 * 3.3 * 0.25) < 1e-9


def test_scheduler_respects_allowance_and_reserve():
    p = plant.make_params()
    cons = {k: p[k] for k in ("horizon_intervals", "model_dt_minutes", "tank_max_l", "tank_min_l", "pump_model_kw",
                              "ev_charger_model_kw", "pump_inflow_lph", "allowance_model_kw")}
    cons["expected_withdrawal_l"] = p["withdrawal_profile_l"]
    out = rules.plan({"interval_index": 0, "tank_l": 4500, "pump_on": False},
                     {"peak_intervals": list(range(40, 52))}, {"ev_sessions": [{**p["ev_sessions"][0], "remaining_model_kwh": 10}]}, cons)
    o = out["options"][0]
    assert o["predicted_peak_model_kw"] <= p["allowance_model_kw"] + 1e-9
    assert o["water_shortfall"]["intervals_below_reserve"] == 0 and o["ev_shortfall_model_kwh"]["EV_1"] == 0
    assert all(0 <= v <= p["tank_max_l"] for v in o["water_trajectory_model_l"])
    assert o["predicted_peak_window_energy_model_kwh"] == 0  # enough off-peak room here


# ---------- forecasting ----------
@pytest.mark.skipif(not HAS_DATA, reason="run scripts/fetch_kptcl.py")
def test_forecast_uses_no_future_data():
    s, rep = data.load_validated()
    a = evaluate.build_snapshot(s, rep, "ridge_lag_calendar", FS)
    s2 = s.copy()
    s2[s2.index >= pd.Timestamp(FS.replace("Z", "")) - pd.Timedelta(hours=24)] = 99999.0  # poison data after cutoff
    b = evaluate.build_snapshot(s2, rep, "ridge_lag_calendar", FS)
    assert [p["predicted_mw"] for p in a["points"]] == [p["predicted_mw"] for p in b["points"]]
    assert len(a["points"]) == 24 and len(a["peak_windows"]) == 3
    assert "Karnataka" in a["geographic_scope"] and "BESCOM" in a["geographic_scope"]  # explicitly 'Not BESCOM'


@pytest.mark.skipif(not HAS_DATA, reason="run scripts/fetch_kptcl.py")
def test_forecast_replay_api_persists_immutable_snapshot(api):
    c = api
    body = {"request_id": "f1", "dataset_id": "kptcl-load-curve", "model_name": "seasonal_naive", "forecast_start": FS}
    assert c.post("/api/v1/forecasts/replay", headers=c.mgr, json=body).status_code == 403
    f1 = c.post("/api/v1/forecasts/replay", headers=c.op, json=body).json()
    assert f1["model_kind"] == "seasonal_naive" and f1["source_kind"] == "historical_replay"
    assert c.post("/api/v1/forecasts/replay", headers=c.op, json=body).json() == f1  # idempotent
    assert c.get(f"/api/v1/forecasts/{f1['forecast_id']}", headers=c.mgr).json() == f1
    assert c.post("/api/v1/forecasts/replay", headers=c.op, json={**body, "request_id": "f2", "model_name": "lstm"}).status_code == 422
    assert c.post("/api/v1/forecasts/replay", headers=c.op, json={**body, "request_id": "f3",
                  "forecast_start": "2026-08-18T19:00:00Z"}).status_code == 422


def test_top3_tie_breaks_earliest():
    idx, _ = models.top3(np.array([5.0] * 24), pd.Timestamp("2026-01-01 18:30"))
    assert idx == [0, 1, 2]


# ---------- comparison experiment ----------
def test_experiment_fairness_properties():
    from simulation import experiment
    rows, summary, _ = experiment.run(n_seeds=5)
    pm = lambda s, m: summary[s]["paired_measured_minus_ack"][m]
    # perfect truthful execution: measured and acknowledgement replanning tie
    assert all(v["ties"] == v["measured_better_runs"] + v["baseline_better_runs"] + v["ties"]
               for v in summary["perfect"]["paired_measured_minus_ack"].values())
    # pump misses are visible to both through the same tank observations
    assert pm("missed_pump_false_done", "reserve_violation_intervals")["ties"] == 5
    # aggregate-only metering never beats branch metering on EV shortfall (it can only see less)
    assert summary["missed_ev_overlapping_pump"]["paired_branch_minus_aggregate"]["ev_shortfall_model_kwh"]["baseline_better_runs"] == 0
    # false done on EV: acknowledgement never beats measurement on EV shortfall
    assert pm("missed_ev_false_done", "ev_shortfall_model_kwh")["baseline_better_runs"] == 0
    # infeasible request: shortfall visible for every policy, no fake completion
    assert all(r["ev_shortfall_model_kwh"] > 0 for r in rows if r["scenario"] == "infeasible_ev")
    # physical bounds in every run
    assert all(0 <= r["final_tank_l"] <= 10000 for r in rows)


def test_experiment_api(api):
    c = api
    body = {"request_id": "e1", "scenarios": ["perfect", "missed_ev_false_done"], "seeds_per_scenario": 3}
    assert c.post("/api/v1/experiments", headers=c.mgr, json=body).status_code == 403
    r = c.post("/api/v1/experiments", headers=c.op, json=body).json()
    doc = c.get(f"/api/v1/experiments/{r['experiment_id']}", headers=c.op).json()
    assert doc["status"] == "COMPLETED" and doc["source_kind"] == "synthetic_simulation" and len(doc["runs"]) == r["runs"] == 24
    assert c.post("/api/v1/experiments", headers=c.op, json={**body, "request_id": "e2", "policies": ["magic"]}).status_code == 422


# ---------- sensing scope and freshness (SMART_METER_EVIDENCE cases A-D) ----------
def accepted_run(c, **params):
    run = new_run(c, **params)
    p = c.post("/api/v1/requirements", headers=c.mgr, json={"run_id": run, "request_id": f"q-{run}", "ev_sessions": []}).json()["proposal"]
    assert accept(c, run, p, f"a-{run}").status_code == 200
    return run, state(c, run)["active_commitment"]["option"]["actions"]


def test_aggregate_only_is_ambiguous_and_gives_no_ev_credit(api):
    c = api
    run, acts = accepted_run(c, observation_scope="aggregate")
    a0 = acts[0]
    assert a0["ev"] != "OFF"  # default EV is present from interval 0
    out = step(c, run, "s0", actual_switches={"pump": a0["pump"], "ev": "ON"})
    assert out["execution"]["observation_status"] == "AMBIGUOUS"
    s = out["state"]
    assert s["observation"]["branch_attribution"] == "AMBIGUOUS" and s["observation"]["ev_model_kw"] is None
    assert s["readiness"]["verified_ev_delivered_model_kwh"] is None
    assert s["readiness"]["verified_ev_unavailable_reason"].startswith("AGGREGATE_ONLY")
    assert s["readiness"]["charging_status"] == "UNVERIFIED"
    assert not s["pending_proposals"]  # ambiguity is not treated as a deviation
    # zero aggregate while something is instructed is a supported deviation
    out = step(c, run, "s1", actual_switches={"pump": "OFF", "ev": "OFF"})
    if acts[1]["pump"] == "ON" or acts[1]["ev"] != "OFF":
        assert out["execution"]["reason"] == "NO_PARTICIPATING_LOAD_OBSERVED"


def test_aggregate_pump_without_water_uses_tank_sensor(api):
    c = api
    run, acts = accepted_run(c, observation_scope="aggregate", source_outage_intervals=list(range(96)), tank_init_l=3100,
                             ev_sessions=[])
    k = next(a["interval_index"] for a in acts if a["pump"] == "ON")
    for j in range(k):
        step(c, run, f"s{j}", actual_switches={"pump": "OFF", "ev": "OFF"})
    out = step(c, run, "sk", actual_switches={"pump": "ON", "ev": "OFF"})
    assert out["execution"]["observation_status"] == "OBSERVED_DEVIATION"
    assert out["execution"]["reason"] == "PUMP_WATER_DELIVERY_NOT_OBSERVED"


def test_late_reading_keeps_gap_then_arrives_marked_late(api):
    c = api
    run, acts = accepted_run(c)
    out = step(c, run, "s0", delay_observation=True, actual_switches={"pump": "OFF", "ev": "OFF"})
    assert out["execution"]["observation_status"] == "STALE"
    assert out["state"]["observation"]["quality"] == "STALE" and out["state"]["observation"]["aggregate_model_kw"] is None
    out = step(c, run, "s1")
    late = out["late_execution"]
    assert late["interval_index"] == 0 and "(late reading)" in late["reason"]
    from backend import db
    o0 = json.loads(db.one("SELECT body FROM observations WHERE run_id=? AND interval_index=0", run)["body"])
    assert o0["quality"] == "LATE" and o0["received_at_interval"] == 1 and o0["interval_index"] == 0
    assert c.post(f"/api/v1/runs/{run}/step", headers=c.op,
                  json={"request_id": "bad", "drop_observation": True, "delay_observation": True}).status_code == 422
