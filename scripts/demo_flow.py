"""Drive the P0 loop through the real API (in-process, temp DB) and save responses to handoff/.

python scripts/demo_flow.py   (needs data/raw/kptcl.parquet and results/forecast_evaluation.json)
Outputs are API responses from one synthetic apartment run, not hand-written fixtures.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp())
os.environ["NIVAWATT_DB"] = str(tmp / "demo.db")
(tmp / "codes.json").write_text(json.dumps({"operator_code": "op", "manager_codes": {"APT_1": "m1"}, "device_tokens": {}}))
os.environ["NIVAWATT_CODES"] = str(tmp / "codes.json")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

OUT = ROOT / "handoff"
c = TestClient(app)


def call(method, path, tok=None, **body):
    r = c.request(method, "/api/v1" + path, json=body or None, headers={"Authorization": "Bearer " + tok} if tok else {})
    if r.status_code != 200:
        sys.exit(f"{method} {path} -> {r.status_code} {r.text}")
    return r.json()


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2) + "\n")
    print("wrote handoff/" + name)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    op = call("POST", "/demo/session", role="operator", access_code="op")["token"]
    mg = call("POST", "/demo/session", role="manager", apartment_id="APT_1", access_code="m1")["token"]
    fs = call("GET", "/forecasts/evaluation", op)["demo_forecast_start"]
    f = call("POST", "/forecasts/replay", op, request_id="d-f", dataset_id="kptcl-load-curve",
             model_name="ridge_lag_calendar", forecast_start=fs)
    save("forecast.json", f)
    save("forecast_actuals.json", call("GET", f"/forecasts/{f['forecast_id']}/actuals", op))
    run = call("POST", "/runs", op, request_id="d-r", clock_start_utc=fs)["run_id"]
    adv = call("POST", "/events", op, request_id="d-a", run_id=run, kind="peak_advisory", known_from_interval=0,
               forecast_id=f["forecast_id"], target_apartments=["APT_1"], peak_windows=f["peak_windows"],
               valid_from=f["forecast_start"], valid_until=f["forecast_end"])
    save("advisory.json", adv)
    s = call("GET", f"/state?run_id={run}&apartment_id=APT_1", mg)
    save("state_1_proposed.json", s)
    p = s["pending_proposals"][0]
    call("POST", f"/proposals/{p['proposal_id']}/delivered", mg)
    s = call("POST", f"/proposals/{p['proposal_id']}/decision", mg, run_id=run, expected_revision=p["revision"],
             decision="ACCEPT", option_id=p["options"][0]["option_id"], request_id="d-acc")
    save("state_2_accepted.json", s)
    com = s["active_commitment"]
    acts = com["option"]["actions"]
    k = next(a["interval_index"] for a in acts if a["pump"] == "ON" or a["ev"] != "OFF")
    for j in range(k):
        call("POST", f"/runs/{run}/step", op, request_id=f"d-s{j}")
    kind = "pump" if acts[k]["pump"] == "ON" else "ev"
    call("POST", "/execution/claims", mg, run_id=run, commitment_id=com["commitment_id"], interval_index=k,
         action_id=f"{com['commitment_id']}:{k}:{kind}", request_id="d-cl")
    out = call("POST", f"/runs/{run}/step", op, request_id="d-false", actual_switches={"pump": "OFF", "ev": "OFF"})
    save("state_3_false_done_revised.json", out["state"])
    rev = out["state"]["pending_proposals"][0]
    s = call("POST", f"/proposals/{rev['proposal_id']}/decision", mg, run_id=run, expected_revision=rev["revision"],
             decision="ACCEPT", option_id="o1", request_id="d-acc2")
    i = s["clock"]["interval_index"]
    a = next(x for x in s["active_commitment"]["option"]["actions"] if x["interval_index"] == i)
    out = call("POST", f"/runs/{run}/step", op, request_id="d-good",
               actual_switches={"pump": a["pump"], "ev": "ON" if a["ev"] != "OFF" else "OFF"})
    save("state_4_revision_executed.json", out["state"])
    save("operator_state.json", call("GET", f"/operator/state?run_id={run}", op))
    save("report.json", call("GET", f"/runs/{run}/report", op))
    print("false-done verdict -> revision executed verdict:", out["execution"]["observation_status"])
    # aggregate-only metering example: same loop, one combined meter (tank sensor still separate)
    run2 = call("POST", "/runs", op, request_id="d-r2", clock_start_utc=fs,
                apartment_params={"observation_scope": "aggregate"})["run_id"]
    p2 = call("POST", "/requirements", mg, run_id=run2, request_id="d-q2", ev_sessions=[])["proposal"]
    s2 = call("POST", f"/proposals/{p2['proposal_id']}/decision", mg, run_id=run2, expected_revision=p2["revision"],
              decision="ACCEPT", option_id="o1", request_id="d-acc3")
    a0 = s2["active_commitment"]["option"]["actions"][0]
    out = call("POST", f"/runs/{run2}/step", op, request_id="d-agg",
               actual_switches={"pump": a0["pump"], "ev": "ON" if a0["ev"] != "OFF" else "OFF"})
    save("state_5_aggregate_only_ambiguous.json", out["state"])
    out = call("POST", f"/runs/{run2}/step", op, request_id="d-late", delay_observation=True)
    save("state_6_reading_in_transit.json", out["state"])
    out = call("POST", f"/runs/{run2}/step", op, request_id="d-late2")
    save("step_7_late_reading_arrived.json", {k: out[k] for k in ("stepped_interval", "execution", "late_execution")})
