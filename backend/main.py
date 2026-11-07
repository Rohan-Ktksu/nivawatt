"""NivaWatt local API (contract v0.2). Advisory mode only: nothing here operates equipment."""
import contextlib
import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import db
from scheduler import rules
from simulation import plant

SCHEMA_VERSION = "0.2"
ROOT = db.ROOT
WEB = ROOT / "web"
PROPOSAL_TTL_S = int(os.environ.get("NIVAWATT_PROPOSAL_TTL_S", "900"))
EV_ON_KW = 1e-6

app = FastAPI(title="NivaWatt", version=SCHEMA_VERSION)


# ---------- errors, time, transactions ----------
class ApiError(Exception):
    def __init__(self, status, code, message, revision=None):
        self.status, self.code, self.message, self.revision = status, code, message, revision


@app.exception_handler(ApiError)
def _api_error(_, e: ApiError):
    return JSONResponse({"error": {"code": e.code, "message": e.message}, "revision": e.revision}, status_code=e.status)


@app.exception_handler(HTTPException)
def _http_error(_, e: HTTPException):
    return JSONResponse({"error": {"code": "HTTP_" + str(e.status_code), "message": str(e.detail)}, "revision": None},
                        status_code=e.status_code)


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s, field):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        raise ApiError(422, "INVALID_TIMESTAMP", f"{field} must be ISO-8601 UTC")


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@contextlib.contextmanager
def tx():
    with db.LOCK:
        db.ex("BEGIN IMMEDIATE")
        try:
            yield
            db.ex("COMMIT")
        except BaseException:
            db.ex("ROLLBACK")
            raise


def idempotent(scope, request_id, body, fn):
    """Same request_id + same body -> stored response. Same id, different body -> 409."""
    if not request_id or not isinstance(request_id, str):
        raise ApiError(400, "MISSING_REQUEST_ID", "request_id is required")
    h = hashlib.sha256(db.dumps(body).encode()).hexdigest()
    with tx():
        row = db.one("SELECT * FROM idempotency WHERE request_id=?", request_id)
        if row:
            if row["scope"] != scope or row["body_hash"] != h:
                raise ApiError(409, "REQUEST_ID_REUSED", "request_id already used for a different command")
            return json.loads(row["response"])
        result = fn()
        db.ex("INSERT INTO idempotency VALUES(?,?,?,?,?)", request_id, scope, h, 200, db.dumps(result))
        return result


# ---------- local demo sessions ----------
def codes():
    path = Path(os.environ.get("NIVAWATT_CODES", ROOT / "config" / "local.json"))
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "operator_code": secrets.token_urlsafe(6),
            "manager_codes": {"APT_1": secrets.token_urlsafe(6)},
            "device_tokens": {"bench-1": secrets.token_urlsafe(12)},
            "_note": "Local demonstration codes only; not production identity. Do not commit."}, indent=2))
        print(f"[nivawatt] generated demo access codes in {path}")
    return json.loads(path.read_text())


def session(authorization: str = Header(default="")):
    tok = authorization.removeprefix("Bearer ").strip()
    row = db.one("SELECT * FROM sessions WHERE token=?", tok) if tok else None
    if row:
        return dict(row)
    dev = {v: k for k, v in codes().get("device_tokens", {}).items()}
    if tok in dev:
        return {"role": "device", "device_id": dev[tok], "apartment_id": None}
    raise ApiError(401, "UNAUTHENTICATED", "missing or invalid demo session")


def require(sess, role, apartment_id=None):
    if sess["role"] != role:
        raise ApiError(403, "FORBIDDEN_ROLE", f"{role} role required")
    if apartment_id is not None and role == "manager" and sess["apartment_id"] != apartment_id:
        raise ApiError(403, "FORBIDDEN_APARTMENT", "session is scoped to another apartment")


async def body(request: Request):
    try:
        b = await request.json()
    except Exception:
        raise ApiError(400, "MALFORMED_JSON", "request body must be JSON")
    if not isinstance(b, dict):
        raise ApiError(400, "MALFORMED_JSON", "request body must be an object")
    return b


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "schema_version": SCHEMA_VERSION, "mode": "advisory",
            "hardware_connected": False, "note": "No hardware connection is claimed; telemetry is accepted if posted."}


@app.post("/api/v1/demo/session")
def demo_session(b: dict = Depends(body)):
    c, role = codes(), b.get("role")
    if role == "operator":
        ok, apt = secrets.compare_digest(str(b.get("access_code", "")), c["operator_code"]), None
    elif role == "manager":
        apt = b.get("apartment_id")
        expected = c.get("manager_codes", {}).get(apt)
        ok = expected is not None and secrets.compare_digest(str(b.get("access_code", "")), expected)
    else:
        raise ApiError(422, "INVALID_ROLE", "role must be operator or manager")
    if not ok:
        raise ApiError(401, "INVALID_ACCESS_CODE", "access code rejected")
    tok = secrets.token_urlsafe(24)
    with tx():
        db.ex("INSERT INTO sessions VALUES(?,?,?,?,?)", tok, role, apt, None, iso(now()))
    return {"token": tok, "role": role, "apartment_id": apt,
            "note": "Local demonstration session; not production authentication."}


# ---------- forecasts ----------
_series = {}


def dataset():
    if "s" not in _series:
        from forecasting import data
        try:
            _series["s"], _series["rep"] = data.load_validated()
        except FileNotFoundError as e:
            raise ApiError(503, "DATASET_UNAVAILABLE", str(e))
    return _series["s"], _series["rep"]


def get_forecast(fid):
    row = db.one("SELECT body FROM forecasts WHERE forecast_id=?", fid)
    if not row:
        raise ApiError(404, "UNKNOWN_FORECAST", f"forecast {fid} not found")
    return json.loads(row["body"])


@app.post("/api/v1/forecasts/replay")
def forecast_replay(b: dict = Depends(body), sess=Depends(session)):
    require(sess, "operator")
    from forecasting import evaluate
    if b.get("dataset_id") != "kptcl-load-curve":
        raise ApiError(422, "UNKNOWN_DATASET", "registered datasets: kptcl-load-curve")

    def make():
        s, rep = dataset()
        try:
            snap = evaluate.build_snapshot(s, rep, b.get("model_name"), b.get("forecast_start"),
                                           "results/forecast_evaluation.json" if evaluate.OUT.exists() else None)
        except ValueError as e:
            raise ApiError(422, "INVALID_FORECAST_REQUEST", str(e))
        snap = {"forecast_id": new_id("fc"), **snap}
        db.ex("INSERT INTO forecasts VALUES(?,?,?)", snap["forecast_id"], db.dumps(snap), snap["issued_at"])
        return snap
    return idempotent("forecast_replay", b.get("request_id"), b, make)


@app.get("/api/v1/forecasts/evaluation")
def forecast_evaluation(sess=Depends(session)):
    from forecasting import evaluate
    if not evaluate.OUT.exists():
        raise ApiError(404, "NO_EVALUATION", "run: python -m forecasting.evaluate")
    return json.loads(evaluate.OUT.read_text())


@app.get("/api/v1/forecasts/{fid}")
def forecast_get(fid: str, sess=Depends(session)):
    return get_forecast(fid)


@app.get("/api/v1/forecasts/{fid}/actuals")
def forecast_actuals(fid: str, sess=Depends(session)):
    """Evaluator view: historical actuals for the forecast day. Never a planning input."""
    import pandas as pd
    f = get_forecast(fid)
    if f["source_kind"] != "historical_replay":
        raise ApiError(422, "NO_ACTUALS", "synthetic forecasts have no actuals")
    s, _ = dataset()
    pts = []
    for p in f["points"]:
        v = s.get(pd.Timestamp(p["start"]).tz_localize(None))
        pts.append({"start": p["start"], "end": p["end"], "predicted_mw": p["predicted_mw"],
                    "actual_mw": None if v is None or pd.isna(v) else float(v)})
    errs = [abs(p["predicted_mw"] - p["actual_mw"]) for p in pts if p["actual_mw"] is not None]
    return {"forecast_id": fid, "use": "evaluation_only_not_a_planning_input", "points": pts,
            "mae_mw": round(sum(errs) / len(errs), 1) if errs else None}


# ---------- runs ----------
def load_run(run_id):
    row = db.one("SELECT * FROM runs WHERE run_id=?", run_id)
    if not row:
        raise ApiError(404, "UNKNOWN_RUN", f"run {run_id} not found")
    r = dict(row)
    r["params"], r["truth"] = json.loads(r["params"]), json.loads(r["truth"])
    return r


def save_run(r):
    db.ex("UPDATE runs SET params=?, truth=?, interval_index=?, revision=?, active_advisory_id=? WHERE run_id=?",
          db.dumps(r["params"]), db.dumps(r["truth"]), r["interval_index"], r["revision"],
          r["active_advisory_id"], r["run_id"])


def interval_time(r, i):
    return parse_ts(r["clock_start_utc"], "clock_start_utc") + timedelta(minutes=i * r["params"]["model_dt_minutes"])


@app.post("/api/v1/runs")
def create_run(b: dict = Depends(body), sess=Depends(session)):
    require(sess, "operator")

    def make():
        overrides = b.get("apartment_params") or {}
        forbidden = {"source_kind"} & set(overrides)
        if forbidden:
            raise ApiError(422, "INVALID_FIELDS", f"cannot override {sorted(forbidden)}")
        try:
            p = plant.make_params(overrides)
        except (ValueError, KeyError, TypeError) as e:
            raise ApiError(422, "INVALID_APARTMENT_PARAMS", str(e))
        start = b.get("clock_start_utc")
        if not start:
            raise ApiError(422, "MISSING_CLOCK_START", "clock_start_utc required (e.g. a forecast_start)")
        parse_ts(start, "clock_start_utc")
        rid = new_id("run")
        db.ex("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)", rid, db.dumps(p), db.dumps(plant.initial_truth(p)),
              0, 0, start, None, iso(now()))
        return {"run_id": rid, "scenario": b.get("scenario", "synthetic_single_apartment"), "source_kind": "synthetic",
                "model_dt_minutes": p["model_dt_minutes"], "horizon_intervals": p["horizon_intervals"]}
    return idempotent("create_run", b.get("request_id"), b, make)


# ---------- observation-derived planning state (never truth) ----------
def observed(r):
    rows = db.q("SELECT body FROM observations WHERE run_id=? ORDER BY interval_index", r["run_id"])
    return [json.loads(x["body"]) for x in rows]


def planning_state(r):
    p, obs = r["params"], observed(r)
    valid = [o for o in obs if o["quality"] in USABLE]
    last = valid[-1] if valid else None
    delivered = {s["ev_id"]: 0.0 for s in p["ev_sessions"]}
    dt_h = p["model_dt_minutes"] / 60
    starts, prev = 0, False
    for o in valid:
        if o.get("ev_id"):
            delivered[o["ev_id"]] = delivered.get(o["ev_id"], 0) + o["ev_model_kw"] * dt_h
        if o["pump_model_kw"] is not None:  # unknown under aggregate-only metering
            on = o["pump_model_kw"] > 0
            starts += on and not prev
            prev = on
    agg = p["observation_scope"] == "aggregate"
    return {
        "interval_index": r["interval_index"],
        "tank_l": last["tank_l"] if last else p["tank_init_l"],
        "tank_source": "observation" if last else "initial_parameter",
        "stale": bool(obs) and obs[-1]["quality"] not in USABLE,
        "aggregate_only": agg,
        "pump_on": None if agg else bool(last and last["pump_model_kw"] > 0),
        "pump_starts_history": None if agg else starts,
        "ev_delivered_observed_model_kwh": {k: round(v, 4) for k, v in delivered.items()},
    }


def active_advisory(r):
    if not r["active_advisory_id"]:
        return None
    row = db.one("SELECT body FROM events WHERE event_id=?", r["active_advisory_id"])
    return json.loads(row["body"]) if row else None


def known_events(r):
    p, adv = r["params"], active_advisory(r)
    peaks = []
    if adv:
        wins = [(parse_ts(w["start"], "w"), parse_ts(w["end"], "w")) for w in adv["peak_windows"]]
        for i in range(p["horizon_intervals"]):
            t = interval_time(r, i)
            if any(a <= t < b for a, b in wins):
                peaks.append(i)
    src = {i: False for i in p.get("known_outage_intervals", [])}
    return {"peak_intervals": peaks, "source_water_available": src}


def replan(r, reason):
    """Compute a new pending proposal from observations. Supersedes older pending proposals."""
    p, ps = r["params"], planning_state(r)
    if r["interval_index"] >= p["horizon_intervals"]:
        return None
    reqs = {"ev_sessions": [{**s, "remaining_model_kwh": max(0.0, s["requested_model_kwh"]
                             - ps["ev_delivered_observed_model_kwh"].get(s["ev_id"], 0))} for s in p["ev_sessions"]]}
    cons = {k: p[k] for k in ("horizon_intervals", "model_dt_minutes", "tank_max_l", "tank_min_l",
                              "pump_model_kw", "ev_charger_model_kw", "pump_inflow_lph", "allowance_model_kw")}
    cons["expected_withdrawal_l"] = p["withdrawal_profile_l"]
    try:
        out = rules.plan(ps, known_events(r), reqs, cons)
    except Exception as e:  # keep current commitment; report failure instead of inventing a plan
        r.setdefault("_warnings", []).append(f"PLANNER_FAILED: {e}")
        return None
    db.ex("UPDATE proposals SET status='SUPERSEDED' WHERE run_id=? AND status IN ('PROPOSED','DELIVERED')", r["run_id"])
    r["revision"] += 1
    pid, adv = new_id("p"), active_advisory(r)
    prop = {"proposal_id": pid, "run_id": r["run_id"], "apartment_id": p["apartment_id"], "revision": r["revision"],
            "status": "PROPOSED", "reason": reason, "source": out["source"], "computation_ms": out["computation_ms"],
            "created_at": iso(now()), "expires_at": iso(now() + timedelta(seconds=PROPOSAL_TTL_S)),
            "advisory_id": adv["advisory_id"] if adv else None, "forecast_id": adv["forecast_id"] if adv else None,
            "planning_inputs": ps, "options": out["options"], "infeasibilities": out["infeasibilities"]}
    db.ex("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?)", pid, r["run_id"], p["apartment_id"], r["revision"],
          "PROPOSED", reason, prop["created_at"], prop["expires_at"], db.dumps(prop))
    return prop


def expire_proposals(run_id):
    db.ex("UPDATE proposals SET status='EXPIRED' WHERE run_id=? AND status IN ('PROPOSED','DELIVERED') AND expires_at<?",
          run_id, iso(now()))


def pending(run_id):
    expire_proposals(run_id)
    rows = db.q("SELECT body, status FROM proposals WHERE run_id=? AND status IN ('PROPOSED','DELIVERED') ORDER BY revision",
                run_id)
    return [{**json.loads(x["body"]), "status": x["status"]} for x in rows]


def active_commitment(run_id):
    row = db.one("SELECT * FROM commitments WHERE run_id=? AND status='ACCEPTED'", run_id)
    if not row:
        return None
    c = dict(row)
    c["body"] = json.loads(c["body"])
    return c


# ---------- events (operator) ----------
@app.post("/api/v1/events")
def post_event(b: dict = Depends(body), sess=Depends(session)):
    require(sess, "operator")

    def make():
        r = load_run(b.get("run_id"))
        kfi = b.get("known_from_interval")
        if not isinstance(kfi, int) or kfi < r["interval_index"]:
            raise ApiError(422, "INVALID_KNOWN_FROM", "known_from_interval must be an int >= current interval (no retroactive events)")
        kind = b.get("kind")
        eid = new_id("ev")
        if kind == "peak_advisory":
            rec = advisory_record(r, b, eid)
        elif kind == "allowance":
            kw = b.get("allowance_model_kw")
            if not isinstance(kw, (int, float)) or kw < 0:
                raise ApiError(422, "INVALID_ALLOWANCE", "allowance_model_kw must be >= 0")
            rec = {"event_id": eid, "kind": kind, "run_id": r["run_id"], "allowance_model_kw": kw,
                   "scope": "participating flexible loads only", "known_from_interval": kfi}
        elif kind == "outage":
            iv = b.get("intervals")
            if not isinstance(iv, list) or not all(isinstance(i, int) and kfi <= i < r["params"]["horizon_intervals"] for i in iv):
                raise ApiError(422, "INVALID_OUTAGE", "intervals must be ints in [known_from_interval, horizon)")
            rec = {"event_id": eid, "kind": kind, "run_id": r["run_id"], "intervals": iv, "announced": True,
                   "known_from_interval": kfi}
        else:
            raise ApiError(422, "INVALID_EVENT_KIND", "kind must be peak_advisory, allowance or outage")
        rec["issued_at"] = iso(now())
        db.ex("INSERT INTO events VALUES(?,?,?,?,?,?,?)", eid, r["run_id"], kind, kfi, 0, db.dumps(rec), rec["issued_at"])
        apply_due_events(r)
        save_run(r)
        return rec
    return idempotent("event", b.get("request_id"), b, make)


def advisory_record(r, b, eid):
    f = get_forecast(b.get("forecast_id"))
    if r["params"]["apartment_id"] not in (b.get("target_apartments") or []):
        raise ApiError(422, "INVALID_TARGETS", "target_apartments must include this run's apartment")
    vf, vu = parse_ts(b.get("valid_from"), "valid_from"), parse_ts(b.get("valid_until"), "valid_until")
    if vf >= vu:
        raise ApiError(422, "INVALID_VALIDITY", "valid_from must precede valid_until")
    fs, fe = parse_ts(f["forecast_start"], "fs"), parse_ts(f["forecast_end"], "fe")
    hours = {(p["start"], p["end"]) for p in f["points"]}
    wins = b.get("peak_windows")
    if not isinstance(wins, list) or not wins:
        raise ApiError(422, "INVALID_WINDOWS", "peak_windows required")
    norm = []
    for w in wins:
        ws, we = parse_ts(w.get("start"), "start"), parse_ts(w.get("end"), "end")
        if (iso(ws), iso(we)) not in hours or not (vf <= ws and we <= vu and fs <= ws and we <= fe):
            raise ApiError(422, "WINDOW_NOT_CONTAINED", "each window must be a forecast hour inside validity and forecast range")
        norm.append({"start": iso(ws), "end": iso(we)})
    return {"advisory_id": eid, "event_id": eid, "kind": "peak_advisory", "run_id": r["run_id"],
            "forecast_id": f["forecast_id"], "approved_by_demo_operator": "demo-operator",
            "geographic_scope": f["geographic_scope"], "valid_from": iso(vf), "valid_until": iso(vu),
            "peak_windows": sorted(norm, key=lambda w: w["start"]), "target_apartments": b["target_apartments"],
            "source_kind": f["source_kind"], "known_from_interval": b["known_from_interval"],
            "_note": "Prototype peak advisory from a regional forecast. Not a BESCOM instruction or a capacity limit."}


def apply_due_events(r):
    """Events become effective only once the clock reaches known_from_interval (no early information)."""
    due = db.q("SELECT * FROM events WHERE run_id=? AND applied=0 AND known_from_interval<=? ORDER BY created_at",
               r["run_id"], r["interval_index"])
    reasons = []
    for e in due:
        rec = json.loads(e["body"])
        if e["kind"] == "peak_advisory":
            r["active_advisory_id"] = rec["advisory_id"]
            reasons.append("PEAK_ADVISORY_ISSUED")
        elif e["kind"] == "allowance":
            r["params"]["allowance_model_kw"] = rec["allowance_model_kw"]
            reasons.append("ALLOWANCE_CHANGED")
        elif e["kind"] == "outage":
            for k in ("known_outage_intervals", "source_outage_intervals"):
                r["params"][k] = sorted(set(r["params"].get(k, [])) | set(rec["intervals"]))
            reasons.append("OUTAGE_ANNOUNCED")
        db.ex("UPDATE events SET applied=1 WHERE event_id=?", e["event_id"])
    if reasons:
        replan(r, reasons[-1])


# ---------- manager commands ----------
@app.post("/api/v1/requirements")
def post_requirements(b: dict = Depends(body), sess=Depends(session)):
    def make():
        r = load_run(b.get("run_id"))
        require(sess, "manager", r["params"]["apartment_id"])
        allowed = {"run_id", "request_id", "ev_sessions"}
        extra = set(b) - allowed
        if extra:  # e.g. allowance_model_kw: manager cannot change operator allowance
            raise ApiError(403 if "allowance_model_kw" in extra else 422, "FIELD_NOT_ALLOWED",
                           f"manager cannot set {sorted(extra)}")
        sessions = {s["ev_id"]: s for s in r["params"]["ev_sessions"]}
        for u in b.get("ev_sessions") or []:
            s = sessions.get(u.get("ev_id"))
            if not s:
                raise ApiError(404, "UNKNOWN_EV", f"ev {u.get('ev_id')} not in run")
            dep = u.get("departure_interval", s["departure_interval"])
            req = u.get("requested_model_kwh", s["requested_model_kwh"])
            if not isinstance(dep, int) or not r["interval_index"] <= dep <= r["params"]["horizon_intervals"] \
                    or dep <= s["arrival_interval"] or not isinstance(req, (int, float)) or req < 0:
                raise ApiError(422, "INVALID_REQUIREMENT", "departure must be future/within horizon; energy >= 0")
            s["departure_interval"], s["requested_model_kwh"] = dep, req
        prop = replan(r, "REQUIREMENT_CHANGED")
        save_run(r)
        return {"revision": r["revision"], "proposal": prop, "warnings": r.get("_warnings", [])}
    return idempotent("requirements", b.get("request_id"), b, make)


def load_proposal(pid):
    row = db.one("SELECT * FROM proposals WHERE proposal_id=?", pid)
    if not row:
        raise ApiError(404, "UNKNOWN_PROPOSAL", f"proposal {pid} not found")
    return dict(row)


@app.post("/api/v1/proposals/{pid}/delivered")
def proposal_delivered(pid: str, sess=Depends(session)):
    with tx():
        p = load_proposal(pid)
        require(sess, "manager", p["apartment_id"])
        expire_proposals(p["run_id"])
        db.ex("UPDATE proposals SET status='DELIVERED' WHERE proposal_id=? AND status='PROPOSED'", pid)
        return {"proposal_id": pid, "status": load_proposal(pid)["status"], "note": "Rendered only; not accepted or executed."}


@app.post("/api/v1/proposals/{pid}/decision")
def proposal_decision(pid: str, b: dict = Depends(body), sess=Depends(session)):
    def make():
        p = load_proposal(pid)
        require(sess, "manager", p["apartment_id"])
        r = load_run(p["run_id"])
        if b.get("run_id") != p["run_id"]:
            raise ApiError(409, "WRONG_RUN", "proposal belongs to another run", r["revision"])
        expire_proposals(p["run_id"])
        p = load_proposal(pid)
        if p["status"] not in ("PROPOSED", "DELIVERED"):
            raise ApiError(409, "STALE_PROPOSAL", f"proposal is {p['status']}; refresh before deciding", r["revision"])
        if b.get("expected_revision") != p["revision"]:
            raise ApiError(409, "STALE_PROPOSAL", "Refresh before accepting this version.", r["revision"])
        prop = json.loads(p["body"])
        opt = next((o for o in prop["options"] if o["option_id"] == b.get("option_id")), None)
        if not opt:
            raise ApiError(422, "UNKNOWN_OPTION", "option_id not in proposal")
        decision = b.get("decision")
        if decision == "DECLINE":
            db.ex("UPDATE proposals SET status='DECLINED' WHERE proposal_id=?", pid)
        elif decision == "ACCEPT":
            if opt.get("requires_operator_exception"):
                raise ApiError(409, "OPERATOR_EXCEPTION_REQUIRED", "option exceeds allowance; operator must decide")
            eff = max(opt["effective_from_interval"], r["interval_index"])
            db.ex("UPDATE commitments SET status='SUPERSEDED', ended_at_interval=? WHERE run_id=? AND status='ACCEPTED'",
                  eff, r["run_id"])
            cid = new_id("c")
            db.ex("INSERT INTO commitments VALUES(?,?,?,?,?,?,?,?,?,?)", cid, r["run_id"], p["apartment_id"], pid,
                  opt["option_id"], "ACCEPTED", eff, None, iso(now()), db.dumps({"option": opt}))
            db.ex("UPDATE proposals SET status='ACCEPTED' WHERE proposal_id=?", pid)
            r["revision"] += 1
            save_run(r)
        else:
            raise ApiError(400, "INVALID_DECISION", "decision must be ACCEPT or DECLINE")
        return state_doc(r["run_id"])
    return idempotent("decision:" + pid, b.get("request_id"), b, make)


def action_at(commitment, i):
    for a in commitment["body"]["option"]["actions"]:
        if a["interval_index"] == i:
            return a
    return None


@app.post("/api/v1/execution/claims")
def post_claim(b: dict = Depends(body), sess=Depends(session)):
    def make():
        r = load_run(b.get("run_id"))
        require(sess, "manager", r["params"]["apartment_id"])
        row = db.one("SELECT * FROM commitments WHERE commitment_id=? AND run_id=?", b.get("commitment_id"), r["run_id"])
        if not row:
            raise ApiError(404, "UNKNOWN_COMMITMENT", "commitment not found for this run")
        c = {**dict(row), "body": json.loads(row["body"])}
        i = b.get("interval_index")
        end = c["ended_at_interval"] if c["ended_at_interval"] is not None else r["params"]["horizon_intervals"]
        if not isinstance(i, int) or not c["effective_from_interval"] <= i < end or i > r["interval_index"]:
            raise ApiError(409, "CLAIM_OUT_OF_RANGE", "interval must be inside the commitment and not in the future", r["revision"])
        a = action_at(c, i)
        valid_ids = {f"{c['commitment_id']}:{i}:pump", f"{c['commitment_id']}:{i}:ev"}
        if b.get("action_id") not in valid_ids:
            raise ApiError(422, "UNKNOWN_ACTION", f"action_id must be one of {sorted(valid_ids)}")
        cid = new_id("cl")
        db.ex("INSERT INTO claims VALUES(?,?,?,?,?,?)", cid, r["run_id"], c["commitment_id"], i, b["action_id"], iso(now()))
        # If this interval was already observed as a deviation, the claim is contradicted now.
        ex_row = db.one("SELECT observation_status FROM executions WHERE run_id=? AND commitment_id=? AND interval_index=?",
                        r["run_id"], c["commitment_id"], i)
        if ex_row and ex_row["observation_status"] == "OBSERVED_DEVIATION" and not pending(r["run_id"]):
            replan(r, "CLAIM_WITHOUT_OBSERVED_EXECUTION")
            save_run(r)
        return {"claim_id": cid, "commitment_id": c["commitment_id"], "interval_index": i, "action_id": b["action_id"],
                "planned_action": a, "status": "CLAIMED_EXECUTED",
                "note": "Claim recorded only. Completion requires independent observation."}
    return idempotent("claim", b.get("request_id"), b, make)


# ---------- simulation step (operator) ----------
USABLE = ("VALID", "LATE")  # LATE = real reading that arrived after its interval; never shown as live


def judge(r, c, i, obs, prev_tank):
    """Compare one interval's observation with the committed action. Returns (status, reason)."""
    if obs["quality"] not in USABLE:
        return "STALE", "No valid observation for this interval."
    a = action_at(c, i) or {"pump": "OFF", "ev": "OFF"}
    p, problems = r["params"], []
    late = " (late reading)" if obs["quality"] == "LATE" else ""
    water_ok = obs["tank_l"] - prev_tank + p["withdrawal_profile_l"][i] >= 0.5 * p["pump_inflow_lph"] * p["model_dt_minutes"] / 60 \
        or obs["tank_l"] >= p["tank_max_l"] - 1
    if obs.get("measurement_scope") == "aggregate":
        # One meter on the participating circuits: zero proves all off; non-zero cannot be attributed to a branch.
        want_any = a["pump"] == "ON" or a["ev"] != "OFF"
        if obs["aggregate_model_kw"] <= EV_ON_KW:
            return ("OBSERVED_DEVIATION", "NO_PARTICIPATING_LOAD_OBSERVED" + late) if want_any else ("OBSERVED_MATCH", late.strip())
        if a["pump"] == "ON" and not water_ok:  # the independent tank sensor still applies
            return "OBSERVED_DEVIATION", "PUMP_WATER_DELIVERY_NOT_OBSERVED" + late
        return "AMBIGUOUS", "AGGREGATE_ONLY_BRANCH_UNATTRIBUTED" + late
    pump_obs = obs["pump_model_kw"] > 0
    if a["pump"] == "ON":
        if not pump_obs:
            problems.append("PUMP_NOT_OBSERVED_ON")
        elif not water_ok:
            problems.append("PUMP_POWER_WITHOUT_WATER_DELIVERY")
    elif pump_obs:
        problems.append("PUMP_ON_NOT_PLANNED")
    ev_obs = obs["ev_model_kw"] > EV_ON_KW
    if a["ev"] != "OFF" and not ev_obs:
        problems.append("EV_CHARGING_NOT_OBSERVED")
    if a["ev"] == "OFF" and ev_obs:
        problems.append("EV_CHARGING_NOT_PLANNED")
    return ("OBSERVED_DEVIATION", ",".join(problems) + late) if problems else ("OBSERVED_MATCH", late.strip())


def make_observation(p, rec, received_interval, quality):
    base = {"interval_index": rec["interval_index"], "received_at_interval": received_interval, "quality": quality,
            "source_kind": p["source_kind"], "measurement_scope": p["observation_scope"], "tank_l": rec["tank_l"],
            "aggregate_model_kw": rec["aggregate_model_kw"], "received_at": iso(now())}
    if p["observation_scope"] == "aggregate":
        return {**base, "pump_model_kw": None, "ev_model_kw": None, "ev_id": None,
                "branch_attribution": "AMBIGUOUS" if rec["aggregate_model_kw"] > EV_ON_KW else "AGGREGATE_ZERO"}
    return {**base, "pump_model_kw": rec["pump_model_kw"], "ev_model_kw": rec["ev_model_kw"], "ev_id": rec["ev_id"],
            "branch_attribution": "SYNTHETIC_KNOWN"}


def commitment_at(run_id, i):
    row = db.one("SELECT * FROM commitments WHERE run_id=? AND effective_from_interval<=? AND status IN ('ACCEPTED','SUPERSEDED') "
                 "AND (ended_at_interval IS NULL OR ended_at_interval>?) ORDER BY accepted_at DESC LIMIT 1", run_id, i, i)
    return {**dict(row), "body": json.loads(row["body"])} if row else None


def tank_before(r, i):
    rows = [o for o in observed(r) if o["quality"] in USABLE and o["interval_index"] < i]
    return rows[-1]["tank_l"] if rows else r["params"]["tank_init_l"]


def record_observation(r, obs):
    """Store an observation and judge it against the commitment that covered its interval."""
    run_id, i = r["run_id"], obs["interval_index"]
    db.ex("INSERT OR REPLACE INTO observations VALUES(?,?,?)", run_id, i, db.dumps(obs))
    c = commitment_at(run_id, i)
    if not c:
        return None
    status, reason = judge(r, c, i, obs, tank_before(r, i))
    db.ex("INSERT OR REPLACE INTO executions VALUES(?,?,?,?,?)", run_id, c["commitment_id"], i, status, reason)
    return {"commitment_id": c["commitment_id"], "interval_index": i, "observation_status": status, "reason": reason}


@app.post("/api/v1/runs/{run_id}/step")
def step_run(run_id: str, b: dict = Depends(body), sess=Depends(session)):
    require(sess, "operator")

    def make():
        r = load_run(run_id)
        p = r["params"]
        i = r["interval_index"]
        if i >= p["horizon_intervals"]:
            raise ApiError(409, "RUN_FINISHED", "horizon reached", r["revision"])
        if b.get("drop_observation") and b.get("delay_observation"):
            raise ApiError(422, "INVALID_STEP", "choose drop_observation or delay_observation, not both")
        sw = b.get("actual_switches") or {}
        for k in sw:
            if k not in ("pump", "ev") or sw[k] not in ("ON", "OFF"):
                raise ApiError(422, "INVALID_SWITCH", "actual_switches: {pump|ev: ON|OFF}")
        verdicts = []
        held = r["truth"].pop("held_reading", None)  # a reading in transit from an earlier interval
        if held:
            verdicts.append(record_observation(r, make_observation(p, held, i, "LATE")))
        pump_on = sw.get("pump", "ON" if r["truth"]["pump_on"] else "OFF") == "ON"
        ev_on = sw.get("ev", "ON" if r["truth"]["ev_on"] else "OFF") == "ON"
        r["truth"], rec = plant.step(r["truth"], p, i, pump_on, ev_on)
        rec["allowance_model_kw"] = p["allowance_model_kw"]
        db.ex("INSERT INTO truth_log VALUES(?,?,?)", run_id, i, db.dumps(rec))
        if b.get("drop_observation") or b.get("delay_observation"):
            if b.get("delay_observation"):
                r["truth"]["held_reading"] = rec  # delivered as LATE at the next step
            gap = {"interval_index": i, "received_at_interval": None, "quality": "STALE", "source_kind": p["source_kind"],
                   "measurement_scope": p["observation_scope"], "tank_l": None, "pump_model_kw": None, "ev_model_kw": None,
                   "ev_id": None, "aggregate_model_kw": None, "branch_attribution": "UNKNOWN", "received_at": None}
            verdicts.append(record_observation(r, gap))
        else:
            verdicts.append(record_observation(r, make_observation(p, rec, i, "VALID")))
        verdicts = [v for v in verdicts if v]
        r["interval_index"] = i + 1
        apply_due_events(r)
        dev = [v for v in verdicts if v["observation_status"] == "OBSERVED_DEVIATION"]
        if dev and not pending(run_id):
            v = dev[-1]
            claimed = db.one("SELECT 1 FROM claims WHERE run_id=? AND commitment_id=? AND interval_index=?",
                             run_id, v["commitment_id"], v["interval_index"])
            replan(r, "CLAIM_WITHOUT_OBSERVED_EXECUTION" if claimed else "OBSERVED_DEVIATION")
        save_run(r)
        cur = next((v for v in verdicts if v["interval_index"] == i), None)
        late = next((v for v in verdicts if v["interval_index"] != i), None)
        return {"stepped_interval": i, "execution": cur, "late_execution": late, "state": state_doc(run_id)}
    return idempotent("step:" + run_id, b.get("request_id"), b, make)


# ---------- telemetry (device) ----------
REQUIRED_TELEMETRY = ("run_id", "apartment_id", "device_id", "device_session_id", "seq_num", "source_kind")


@app.post("/api/v1/telemetry")
def post_telemetry(b: dict = Depends(body), sess=Depends(session)):
    require(sess, "device")
    missing = [k for k in REQUIRED_TELEMETRY if k not in b]
    if missing:
        raise ApiError(422, "INVALID_TELEMETRY", f"missing {missing}")
    if b["device_id"] != sess["device_id"]:
        raise ApiError(403, "DEVICE_MISMATCH", "token belongs to another device")
    if b["source_kind"] not in ("hardware", "synthetic"):
        raise ApiError(422, "INVALID_SOURCE_KIND", "telemetry source_kind must be hardware or synthetic")
    if not isinstance(b["seq_num"], int) or b["seq_num"] < 0:
        raise ApiError(422, "INVALID_SEQ", "seq_num must be a non-negative int")
    with tx():
        load_run(b["run_id"])
        dup = db.one("SELECT id FROM telemetry WHERE device_id=? AND device_session_id=? AND seq_num=?",
                     b["device_id"], b["device_session_id"], b["seq_num"])
        if dup:
            return {"status": "DUPLICATE", "telemetry_id": dup["id"]}
        last = db.one("SELECT device_session_id, MAX(seq_num) m FROM telemetry WHERE device_id=? AND device_session_id=?",
                      b["device_id"], b["device_session_id"])
        known_session = last["m"] is not None
        any_prev = db.one("SELECT 1 FROM telemetry WHERE device_id=?", b["device_id"])
        status = "OUT_OF_ORDER" if known_session and b["seq_num"] < last["m"] else \
                 "NEW_DEVICE_SESSION" if any_prev and not known_session else "ACCEPTED"
        db.ex("INSERT INTO telemetry(run_id, device_id, device_session_id, seq_num, received_at, status, body) VALUES(?,?,?,?,?,?,?)",
              b["run_id"], b["device_id"], b["device_session_id"], b["seq_num"], iso(now()), status, db.dumps(b))
        tid = db.one("SELECT last_insert_rowid() i")["i"]
    return {"status": status, "telemetry_id": tid,
            "note": "Raw bench units stored as received; not converted into model kW/kWh."}


def latest_raw(run_id):
    row = db.one("SELECT received_at, status, body FROM telemetry WHERE run_id=? AND status!='OUT_OF_ORDER' ORDER BY id DESC LIMIT 1",
                 run_id)
    return {**json.loads(row["body"]), "received_at": row["received_at"], "ingest_status": row["status"]} if row else None


# ---------- state and report ----------
def state_doc(run_id):
    r = load_run(run_id)
    p, ps = r["params"], planning_state(r)
    obs = observed(r)
    c = active_commitment(run_id)
    adv = active_advisory(r)
    i = r["interval_index"]
    last_obs = obs[-1] if obs else None
    execution = None
    if c:
        ex_row = db.one("SELECT * FROM executions WHERE run_id=? AND commitment_id=? ORDER BY interval_index DESC LIMIT 1",
                        run_id, c["commitment_id"])
        claims = db.q("SELECT interval_index, action_id, claimed_at FROM claims WHERE commitment_id=? ORDER BY claimed_at",
                      c["commitment_id"])
        ex_i = ex_row["interval_index"] if ex_row else None
        execution = {"commitment_id": c["commitment_id"], "interval_index": ex_i,
                     "claim": "CLAIMED_EXECUTED" if any(x["interval_index"] == ex_i for x in claims) else "NO_CLAIM",
                     "observation_status": ex_row["observation_status"] if ex_row else "UNOBSERVED",
                     "reason": ex_row["reason"] if ex_row else "", "claims": [dict(x) for x in claims],
                     "next_action": action_at(c, i)}
    warnings = ["SYNTHETIC apartment simulation. Not a field measurement.",
                "Regional forecast and advisory do not establish local transformer or apartment capacity."]
    if ps["aggregate_only"]:
        warnings.append("Aggregate-only metering: branch execution and per-EV energy are not verified; the tank sensor is separate.")
    if ps["stale"]:
        warnings.append("Latest observation is STALE; planning uses the last valid observation.")
    warnings += r.get("_warnings", [])
    remaining = {s["ev_id"]: round(max(0.0, s["requested_model_kwh"] - ps["ev_delivered_observed_model_kwh"].get(s["ev_id"], 0)), 4)
                 for s in p["ev_sessions"]}
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "revision": r["revision"], "mode": "advisory",
        "clock": {"interval_index": i, "model_dt_minutes": p["model_dt_minutes"], "horizon_intervals": p["horizon_intervals"],
                  "model_time_utc": iso(interval_time(r, i)), "clock_start_utc": r["clock_start_utc"], "source_kind": "synthetic"},
        "apartment": {"apartment_id": p["apartment_id"], "allowance_model_kw": p["allowance_model_kw"],
                      "allowance_scope": "participating flexible loads (pump + EV-charging emulator) only",
                      "model_tank_l": ps["tank_l"], "model_tank_min_l": p["tank_min_l"], "model_tank_max_l": p["tank_max_l"],
                      "source_water_available": i not in p.get("known_outage_intervals", []),
                      "pump_state": "UNKNOWN" if ps["stale"] or ps["pump_on"] is None else ("ON" if ps["pump_on"] else "OFF"),
                      "pump_starts_observed": ps["pump_starts_history"],
                      "ev_sessions": [{**s, "remaining_model_kwh": None if ps["aggregate_only"] else remaining[s["ev_id"]]}
                                      for s in p["ev_sessions"]]},
        "active_commitment": None if not c else {"commitment_id": c["commitment_id"], "proposal_id": c["proposal_id"],
                                                 "option_id": c["option_id"], "status": c["status"],
                                                 "effective_from_interval": c["effective_from_interval"],
                                                 "accepted_at": c["accepted_at"], "option": c["body"]["option"]},
        "pending_proposals": pending(run_id),
        "observation": None if not last_obs else {**last_obs, "model_power_kw": last_obs["aggregate_model_kw"],
                                                  "raw_bench": latest_raw(run_id)},
        "execution": execution,
        "execution_history": execution_history(run_id),
        "readiness": {"water_reserve_status": "UNKNOWN" if ps["stale"] else
                      ("ABOVE_MINIMUM" if ps["tank_l"] >= p["tank_min_l"] else "BELOW_MINIMUM"),
                      # fixture fields keep their v0.1 types; per-EV detail is additive
                      "charging_status": "UNVERIFIED" if ps["aggregate_only"] else
                      ("MET" if all(v <= 1e-9 for v in remaining.values()) else "PENDING"),
                      "charging_status_by_ev": {k: ("UNVERIFIED" if ps["aggregate_only"] else "MET" if v <= 1e-9 else "PENDING")
                                                for k, v in remaining.items()},
                      "verified_ev_delivered_model_kwh": None if ps["aggregate_only"] or not obs else
                      round(sum(ps["ev_delivered_observed_model_kwh"].values()), 4),
                      "verified_ev_delivered_by_ev_model_kwh": None if ps["aggregate_only"] else ps["ev_delivered_observed_model_kwh"],
                      "verified_ev_unavailable_reason": "AGGREGATE_ONLY_METERING: combined reading cannot be attributed to an EV"
                      if ps["aggregate_only"] else None},
        "warnings": warnings,
        "forecast_id": adv["forecast_id"] if adv else None,
        "active_advisory": adv,
    }


def execution_history(run_id):
    """Every judged interval and every claim across all commitments (claims kept even when contradicted)."""
    ex = {(e["commitment_id"], e["interval_index"]): dict(e) for e in
          db.q("SELECT commitment_id, interval_index, observation_status, reason FROM executions WHERE run_id=?", run_id)}
    claims = db.q("SELECT commitment_id, interval_index, action_id, claimed_at FROM claims WHERE run_id=?", run_id)
    out = {k: {**v, "claims": []} for k, v in ex.items()}
    for cl in claims:
        key = (cl["commitment_id"], cl["interval_index"])
        out.setdefault(key, {"commitment_id": key[0], "interval_index": key[1], "observation_status": "UNOBSERVED",
                             "reason": "", "claims": []})["claims"].append({"action_id": cl["action_id"], "claimed_at": cl["claimed_at"]})
    obs = {o["interval_index"]: o for o in (json.loads(x["body"]) for x in
           db.q("SELECT body FROM observations WHERE run_id=?", run_id))}
    for v in out.values():
        o = obs.get(v["interval_index"])
        v["quality"] = o["quality"] if o else None
        v["received_at_interval"] = o.get("received_at_interval") if o else None
    return sorted(out.values(), key=lambda v: (v["interval_index"], v["commitment_id"]))


@app.get("/api/v1/runs")
def list_runs(sess=Depends(session)):
    require(sess, "operator")
    rows = db.q("SELECT run_id, params, interval_index, revision, clock_start_utc, created_at FROM runs ORDER BY created_at DESC")
    return {"runs": [{"run_id": x["run_id"], "apartment_id": json.loads(x["params"])["apartment_id"],
                      "observation_scope": json.loads(x["params"])["observation_scope"], "interval_index": x["interval_index"],
                      "revision": x["revision"], "clock_start_utc": x["clock_start_utc"], "created_at": x["created_at"]}
                     for x in rows]}


@app.get("/api/v1/state")
def get_state(run_id: str, apartment_id: str, sess=Depends(session)):
    with tx():
        r = load_run(run_id)
        if r["params"]["apartment_id"] != apartment_id:
            raise ApiError(404, "UNKNOWN_APARTMENT", "apartment not in run")
        if sess["role"] != "operator":
            require(sess, "manager", apartment_id)
        return state_doc(run_id)


@app.get("/api/v1/operator/state")
def get_operator_state(run_id: str, sess=Depends(session)):
    require(sess, "operator")
    with tx():
        s = state_doc(run_id)
        events = [json.loads(e["body"]) | {"applied": bool(e["applied"])} for e in
                  db.q("SELECT body, applied FROM events WHERE run_id=? ORDER BY created_at", run_id)]
        n = s["clock"]["interval_index"]
        valid = db.one("SELECT COUNT(*) n FROM observations WHERE run_id=? AND (body LIKE '%\"quality\":\"VALID\"%' OR body LIKE '%\"quality\":\"LATE\"%')", run_id)["n"]
        return {"schema_version": SCHEMA_VERSION, "run_id": run_id, "revision": s["revision"], "clock": s["clock"],
                "participating_scope": "pump + EV-charging emulator per apartment; background load unmetered (unknown)",
                "apartments": [{"apartment_id": s["apartment"]["apartment_id"], "allowance_model_kw": s["apartment"]["allowance_model_kw"],
                                "latest_aggregate_model_kw": (s["observation"] or {}).get("aggregate_model_kw"),
                                "pending_proposals": len(s["pending_proposals"]),
                                "active_commitment_id": (s["active_commitment"] or {}).get("commitment_id"),
                                "execution": s["execution"]}],
                "events": events, "forecast_id": s["forecast_id"], "active_advisory": s["active_advisory"],
                "observation_coverage": {"intervals_elapsed": n, "valid_observations": valid}, "warnings": s["warnings"]}


@app.get("/api/v1/runs/{run_id}/report")
def report(run_id: str, sess=Depends(session)):
    if sess["role"] not in ("operator", "manager"):
        raise ApiError(403, "FORBIDDEN_ROLE", "operator or manager required")
    from simulation.metrics import run_metrics
    with tx():
        r = load_run(run_id)
        if sess["role"] == "manager":
            require(sess, "manager", r["params"]["apartment_id"])
        truth = [json.loads(x["body"]) for x in db.q("SELECT body FROM truth_log WHERE run_id=? ORDER BY interval_index", run_id)]
        obs = observed(r)
        peaks = set(known_events(r)["peak_intervals"])
        m = run_metrics(r["params"], truth, peaks)
        cnt = lambda sql: db.one(sql, run_id)["n"]
        m["counts"] = {"proposals": cnt("SELECT COUNT(*) n FROM proposals WHERE run_id=?"),
                       "acceptances": cnt("SELECT COUNT(*) n FROM commitments WHERE run_id=?"),
                       "claims": cnt("SELECT COUNT(*) n FROM claims WHERE run_id=?"),
                       "observed_deviations": cnt("SELECT COUNT(*) n FROM executions WHERE run_id=? AND observation_status='OBSERVED_DEVIATION'"),
                       "claims_contradicted": cnt("SELECT COUNT(*) n FROM claims c JOIN executions e ON e.commitment_id=c.commitment_id "
                                                  "AND e.interval_index=c.interval_index WHERE c.run_id=? AND e.observation_status='OBSERVED_DEVIATION'")}
        m["observation_coverage"] = {"intervals_elapsed": len(truth), "valid": sum(o["quality"] in USABLE for o in obs),
                                     "late": sum(o["quality"] == "LATE" for o in obs),
                                     "measurement_scope": r["params"]["observation_scope"]}
        m["provenance"] = {"source_kind": "synthetic", "plant": "simulation.plant (evaluator truth)",
                           "advisory_id": r["active_advisory_id"], "computed_at": iso(now())}
        if sess["role"] == "manager":  # simulator truth is evaluator-only
            return {"counts": m["counts"], "observation_coverage": m["observation_coverage"],
                    "provenance": {**m["provenance"], "plant": None},
                    "scope": "manager: counts and coverage only; truth-based outcomes are operator/evaluator views"}
        return m


# ---------- experiments (simulated policy comparison) ----------
@app.post("/api/v1/experiments")
def post_experiment(b: dict = Depends(body), sess=Depends(session)):
    require(sess, "operator")
    from simulation import experiment

    def make():
        seeds = b.get("seeds_per_scenario", 20)
        if not isinstance(seeds, int) or not 1 <= seeds <= 50:
            raise ApiError(422, "INVALID_SEEDS", "seeds_per_scenario must be 1..50")
        peaks = None
        if b.get("run_id"):  # use that run's active advisory hours
            r = load_run(b["run_id"])
            peaks = known_events(r)["peak_intervals"]
        try:
            rows, summary, cfg = experiment.run(b.get("scenarios"), b.get("policies"), seeds, peaks)
        except ValueError as e:
            raise ApiError(422, "INVALID_EXPERIMENT", str(e))
        eid, d = experiment.export(rows, summary, cfg)
        doc = json.loads((d / "summary.json").read_text())
        doc.update({"status": "COMPLETED", "runs_csv": str(d / "runs.csv"), "runs": rows})
        db.ex("INSERT INTO experiments VALUES(?,?,?)", eid, db.dumps(doc), iso(now()))
        return {"experiment_id": eid, "status": "COMPLETED", "runs": len(rows)}
    return idempotent("experiment", b.get("request_id"), b, make)


@app.get("/api/v1/experiments/{eid}")
def get_experiment(eid: str, sess=Depends(session)):
    row = db.one("SELECT body FROM experiments WHERE experiment_id=?", eid)
    if not row:
        raise ApiError(404, "UNKNOWN_EXPERIMENT", f"experiment {eid} not found")
    return json.loads(row["body"])


# ---------- same-origin web assets (web/ is owned by the UI workstream) ----------
def _page(name):
    f = WEB / f"{name}.html"
    if f.exists():
        return FileResponse(f)
    return JSONResponse({"error": {"code": "UI_NOT_PRESENT", "message": f"web/{name}.html not yet provided"}}, status_code=404)


@app.get("/operator")
def operator_page():
    return _page("operator")


@app.get("/manager")
def manager_page():
    return _page("manager")


if WEB.exists():
    app.mount("/web", StaticFiles(directory=WEB), name="web")
