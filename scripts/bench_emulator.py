"""Emulated bench device: posts synthetic telemetry to a running NivaWatt service and closes each interval.

Examples (service running with `python app.py`):
  python scripts/bench_emulator.py --new-run --accept --follow-plan --intervals 6 --fast
  python scripts/bench_emulator.py --new-run --accept --follow-plan --claim --miss 1 --fast   # false done
  python scripts/bench_emulator.py --run-id run-xxxx --interactive                           # you work the switches

It plays the device and, optionally, the person at the switches (--follow-plan / --miss / --interactive).
--accept and --claim act as the manager for unattended demos; in a live demo the manager uses the phone instead.
All readings are source_kind=synthetic and must never be presented as bench or field measurements.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from simulation.device_emulator import DeviceEmulator, load_profile  # noqa: E402


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/") + "/api/v1"
        self.n = 0

    def call(self, method, path, body=None, token=None, ok=(200,)):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": "Bearer " + token} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            out = json.loads(e.read() or b"{}")
            if e.code not in ok:
                raise SystemExit(f"{method} {path} -> {e.code} {out}")
            return e.code, out

    def rid(self, tag):
        self.n += 1
        return f"emu-{tag}-{time.time_ns()}-{self.n}"


def ints(s):
    return {int(x) for x in s.split(",") if x.strip()} if s else set()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8780")
    ap.add_argument("--profile", default="apartment_reference")
    ap.add_argument("--run-id")
    ap.add_argument("--new-run", action="store_true", help="create a telemetry run matching the profile")
    ap.add_argument("--intervals", type=int, default=6)
    ap.add_argument("--fast", action="store_true", help="do not wait in real time (device clock still advances)")
    ap.add_argument("--follow-plan", action="store_true", help="the person sets switches to the accepted plan")
    ap.add_argument("--miss", default="", help="intervals where the person leaves everything OFF, e.g. 1,3")
    ap.add_argument("--dry", default="", help="intervals with no source water (pump runs dry)")
    ap.add_argument("--drop", default="", help="intervals where no readings reach the server")
    ap.add_argument("--reboot", default="", help="intervals that start with a device reboot")
    ap.add_argument("--duplicate", action="store_true", help="resend each interval's last reading (must be ignored)")
    ap.add_argument("--accept", action="store_true", help="demo harness: accept any pending proposal as the manager")
    ap.add_argument("--claim", action="store_true", help="demo harness: report done for every instructed action")
    ap.add_argument("--interactive", action="store_true", help="type switch commands before each interval")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    codes = json.loads((ROOT / "config" / "local.json").read_text())
    api = Api(a.base)
    dev_id, dev_tok = next(iter(codes["device_tokens"].items()))
    op = api.call("POST", "/demo/session", {"role": "operator", "access_code": codes["operator_code"]})[1]["token"]
    pf = load_profile(a.profile)
    apt = "APT_1"
    mg = None
    if a.accept or a.claim:
        mg = api.call("POST", "/demo/session", {"role": "manager", "apartment_id": apt,
                                                "access_code": codes["manager_codes"][apt]})[1]["token"]
    run = a.run_id
    if a.new_run:
        start = api.call("GET", "/forecasts/evaluation", token=op)[1]["demo_forecast_start"]
        params = {"observation_source": "telemetry", "tank_max_l": pf["tank"]["capacity_l"],
                  "tank_min_l": pf["tank"]["reserve_l"], "tank_init_l": pf["tank"]["initial_l"],
                  "pump_model_kw": pf["pump"]["rated_kw"], "pump_inflow_lph": pf["pump"]["flow_lpm"] * 60,
                  "ev_charger_model_kw": pf["ev_charger"]["rated_kw"]}
        run = api.call("POST", "/runs", {"request_id": api.rid("run"), "clock_start_utc": start,
                                         "apartment_params": params}, op)[1]["run_id"]
        if mg:
            api.call("POST", "/requirements", {"run_id": run, "request_id": api.rid("req"), "ev_sessions": []}, mg)
        print(f"created telemetry run {run} (profile {pf['profile_id']}, synthetic)")
    if not run:
        raise SystemExit("give --run-id or --new-run")

    emu = DeviceEmulator(pf, run, apt, dev_id, a.seed)
    st = api.call("GET", f"/state?run_id={run}&apartment_id={apt}", token=op)[1]
    emu.ev_requested_kwh = sum(s["requested_model_kwh"] for s in st["apartment"]["ev_sessions"])
    misses, dry, drop, reboot = ints(a.miss), ints(a.dry), ints(a.drop), ints(a.reboot)
    secs = pf["emulator"]["seconds_per_model_interval"]

    for _ in range(a.intervals):
        st = api.call("GET", f"/state?run_id={run}&apartment_id={apt}", token=op)[1]
        i = st["clock"]["interval_index"]
        if i >= st["clock"]["horizon_intervals"]:
            break
        if a.accept and st["pending_proposals"]:
            p = st["pending_proposals"][-1]
            st = api.call("POST", f"/proposals/{p['proposal_id']}/decision",
                          {"run_id": run, "expected_revision": p["revision"], "decision": "ACCEPT",
                           "option_id": p["options"][0]["option_id"], "request_id": api.rid("acc")}, mg)[1]
        com = st["active_commitment"]
        act = next((x for x in com["option"]["actions"] if x["interval_index"] == i), None) if com else None
        if a.follow_plan and act:
            emu.pump_on, emu.ev_on = act["pump"] == "ON", act["ev"] != "OFF"
        if i in misses:
            emu.pump_on = emu.ev_on = False
        if a.interactive:
            cmd = input(f"[interval {i}] plan={act} switches pump={'ON' if emu.pump_on else 'OFF'} "
                        f"ev={'ON' if emu.ev_on else 'OFF'} > ").strip().lower()
            for part in cmd.split(","):
                w = part.split()
                if w[:1] == ["pump"] and len(w) == 2:
                    emu.pump_on = w[1] == "on"
                elif w[:1] == ["ev"] and len(w) == 2:
                    emu.ev_on = w[1] == "on"
                elif w == ["dry"]:
                    dry.add(i)
                elif w == ["drop"]:
                    drop.add(i)
                elif w == ["reboot"]:
                    reboot.add(i)
        if a.claim and act and com:
            for kind, on in (("pump", act["pump"] == "ON"), ("ev", act["ev"] != "OFF")):
                if on:
                    api.call("POST", "/execution/claims", {"run_id": run, "commitment_id": com["commitment_id"],
                                                           "interval_index": i, "action_id": f"{com['commitment_id']}:{i}:{kind}",
                                                           "request_id": api.rid("claim")}, mg)
        if i in reboot:
            emu.reboot()
        emu.dry = i in dry
        samples = emu.interval_samples(i)
        statuses = {}
        if i not in drop:
            for s in samples:
                code, out = api.call("POST", "/telemetry", s, dev_tok)
                statuses[out["status"]] = statuses.get(out["status"], 0) + 1
                if not a.fast:
                    time.sleep(emu.period_s)
            if a.duplicate:
                out = api.call("POST", "/telemetry", samples[-1], dev_tok)[1]
                statuses[out["status"]] = statuses.get(out["status"], 0) + 1
        elif not a.fast:
            time.sleep(secs)
        res = api.call("POST", f"/runs/{run}/step", {"request_id": api.rid("step")}, op)[1]
        ex = res["execution"] or {}
        obs = res["state"]["observation"] or {}
        print(f"interval {i:>2} | switches pump={'ON ' if emu.pump_on else 'OFF'} ev={'ON ' if emu.ev_on else 'OFF'}"
              f"{' DRY' if emu.dry else ''}{' DROPPED' if i in drop else ''} | sent {statuses or 0}"
              f" | tank {obs.get('tank_l')} L, pump {obs.get('pump_model_kw')} kW, ev {obs.get('ev_model_kw')} kW"
              f" | {ex.get('observation_status', 'no commitment')} {ex.get('reason', '')}"
              f" | pending {[pp['reason'] for pp in res['state']['pending_proposals']]}")
    print(f"done. report: GET /api/v1/runs/{run}/report  (all values synthetic)")


if __name__ == "__main__":
    main()
