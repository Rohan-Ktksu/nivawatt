"""Regenerate the evidence pack in results/evidence/ from data, code and exported results.

python scripts/build_evidence.py   (needs data/raw/kptcl.parquet, results/forecast_evaluation.json,
                                     results/experiments/exp-default/summary.json)
Every number in the pack is computed here; nothing is typed by hand.
"""
import json
import os
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "evidence"
IST = 5.5


def commit():
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def ist_label(iso):
    import pandas as pd
    return (pd.Timestamp(iso) + pd.Timedelta(hours=IST)).strftime("%Y-%m-%d %H:%M IST")


# ---------- 1. dataset record ----------
def dataset_record(ev):
    d, sp = ev["data_validation"], ev["split"]
    return f"""# Dataset record

| Field | Value |
|---|---|
| Source | {d['source_name']} |
| Archive | {d['source_url']} |
| Original reports | {d['original_reports']} |
| Licence | {d['license']} |
| Geographic scope | **{d['geographic_scope']}** |
| Unit / resolution | {d['demand_unit']}, {d['resolution_minutes']} min |
| Timezone | {d['timezone_assumption']} |
| File fingerprint (SHA-256) | `{d['dataset_fingerprint_sha256']}` |
| Coverage | {d['first_observation_utc']} to {d['last_observation_utc']} |
| Raw rows | {d['raw_rows']:,} |
| Null / implausible loads removed | {d['null_load_rows_removed']} / {d['implausible_load_rows_removed']} |
| Duplicate timestamps | {d['duplicate_timestamps']:,} ({d['duplicate_timestamps_with_differing_values']} with differing values). Rule: {d['duplicate_rule']} |
| Missing hours | {d['missing_hours']:,} of {d['expected_hours']:,} expected. {d['imputation']} |
| Complete IST days | {d['complete_ist_days']:,} |
| Publication lag | {d['publication_lag']} |

## Split used for the forecast evaluation

| Block | From (UTC) | To (UTC) |
|---|---|---|
| Train | {sp['train']['first_day_start_utc']} | {sp['train']['last_day_end_utc']} |
| Validation | {sp['validation']['first_day_start_utc']} | {sp['validation']['last_day_end_utc']} |
| Test | {sp['test']['first_day_start_utc']} | {sp['test']['last_day_end_utc']} |

Rule: {sp['rule']}. Calendar spans exceed the day counts where days with missing hours were skipped.
Inputs: {ev['input_availability']}.

The raw file is not redistributed (ODbL share-alike; some contents copyright KPTCL). `scripts/fetch_kptcl.py` downloads and verifies it.
OpenCity BESCOM resources were reviewed and are not intraday load series: see `data/OPENCITY_BESCOM_REVIEW.md`.
"""


# ---------- 2. held-out forecast ----------
def heldout(ev):
    import numpy as np
    from forecasting import data, evaluate, models
    s, _ = data.load_validated()
    train, val, test = evaluate.split(s)
    alpha = ev["ridge"]["selected_alpha"]
    ridge, _ = models.fit_ridge(s, train + val, alpha)
    rows, demo = [], None
    for d in test:
        hrs = models.target_hours(d)
        act = s.reindex(hrs).to_numpy()
        nv = models.seasonal_naive(s, d)
        rg = ridge.predict(models.features(s, hrs))
        a3, _ = models.top3(act, d)
        rows.append({"day": ist_label(models.iso(d))[:10], "naive_mae": float(np.mean(np.abs(nv - act))),
                     "ridge_mae": float(np.mean(np.abs(rg - act))),
                     "naive_overlap": len(set(a3) & set(models.top3(nv, d)[0])),
                     "ridge_overlap": len(set(a3) & set(models.top3(rg, d)[0]))})
        demo = (d, act, nv, rg, a3)
    t = ev["test"]
    lines = ["# Held-out forecast evaluation", "",
             f"Chronological backtest on the {len(rows)} most recent usable days (never seen in training or model selection). "
             f"{ev['kind']}.", "",
             "| Model | Mean absolute error (MW) | Top-3 peak hours matched (of 3, mean) |", "|---|---|---|",
             f"| Seasonal naive (same hour last week) | {t['seasonal_naive']['mae_mw']} | {t['seasonal_naive']['top3_peak_hour_overlap'] * 3:.2f} |",
             f"| Ridge regression (lags 48/168/336 h + calendar, alpha {alpha}) | {t['ridge_lag_calendar']['mae_mw']} | {t['ridge_lag_calendar']['top3_peak_hour_overlap'] * 3:.2f} |",
             "", f"Ridge wins MAE on {sum(r['ridge_mae'] < r['naive_mae'] for r in rows)} of {len(rows)} days; "
                 f"seasonal naive wins on {sum(r['naive_mae'] < r['ridge_mae'] for r in rows)}. "
                 "Fourteen days is a small test set; this does not establish general superiority.", "",
             "## Per day", "", "| Day (IST) | Naive MAE | Ridge MAE | Naive peak hours matched | Ridge peak hours matched |",
             "|---|---|---|---|---|"]
    lines += [f"| {r['day']} | {r['naive_mae']:.0f} | {r['ridge_mae']:.0f} | {r['naive_overlap']}/3 | {r['ridge_overlap']}/3 |" for r in rows]
    d, act, nv, rg, a3 = demo
    lines += ["", f"## Demo day: {ist_label(models.iso(d))[:10]} (final test day, chosen by a predeclared rule)", "",
              "![Actual vs forecast load](forecast_demo_day.svg)", "",
              "| Hour (IST) | Actual MW | Seasonal naive MW | Ridge MW | Actual top-3 |", "|---|---|---|---|---|"]
    for h in range(24):
        lines.append(f"| {h:02d}:00 | {act[h]:.0f} | {nv[h]:.0f} | {rg[h]:.0f} | {'yes' if h in a3 else ''} |")
    lines += ["", "Karnataka state load. Not BESCOM feeder, transformer or apartment demand."]
    return "\n".join(lines) + "\n", svg_chart(act, nv, rg, a3, ist_label(models.iso(d))[:10])


def svg_chart(act, nv, rg, peaks, day):
    W, H, L, R, T, B = 760, 380, 64, 150, 64, 48
    lo = min(min(act), min(nv), min(rg))
    hi = max(max(act), max(nv), max(rg))
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    x = lambda h: L + h * (W - L - R) / 23
    y = lambda v: T + (hi - v) * (H - T - B) / (hi - lo)
    step = 1000 if hi - lo > 3000 else 500
    ticks = [v for v in range(int(lo // step + 1) * step, int(hi) + 1, step)]
    series = [("Actual", act, "s1", ""), ("Seasonal naive", nv, "s2", ' stroke-dasharray="6 4"'), ("Ridge", rg, "s3", "")]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="Karnataka hourly load on {day}: actual versus two day-ahead forecasts">',
           """<style>
  .bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}.grid{stroke:#e4e3df}.band{fill:#efeeea}
  .s1{stroke:#2a78d6}.s2{stroke:#eb6834}.s3{stroke:#1baf7a}.f1{fill:#2a78d6}.f2{fill:#eb6834}.f3{fill:#1baf7a}
  text{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;font-size:12px}
  @media (prefers-color-scheme: dark){
    .bg{fill:#1a1a19}.t1{fill:#f0efec}.t2{fill:#c3c2b7}.grid{stroke:#353533}.band{fill:#262624}
    .s1{stroke:#3987e5}.s2{stroke:#d95926}.s3{stroke:#199e70}.f1{fill:#3987e5}.f2{fill:#d95926}.f3{fill:#199e70}}
</style>""",
           f'<rect class="bg" width="{W}" height="{H}"/>',
           f'<text class="t1" x="{L}" y="22" font-size="15" font-weight="600">Karnataka state load, {escape(day)} (MW)</text>']
    lx = L
    for name, _, cls, dash in series:  # legend row
        out.append(f'<line class="{cls}" x1="{lx}" y1="42" x2="{lx + 22}" y2="42" stroke-width="2.5"{dash}/>'
                   f'<text class="t2" x="{lx + 28}" y="46">{name}</text>')
        lx += 40 + len(name) * 7
    out.append(f'<rect class="band" x="{lx}" y="36" width="14" height="12"/><text class="t2" x="{lx + 20}" y="46">actual top-3 hours</text>')
    for h in peaks:  # neutral band, not a series colour
        out.append(f'<rect class="band" x="{x(h) - (W - L - R) / 46:.1f}" y="{T}" width="{(W - L - R) / 23:.1f}" height="{H - T - B}"/>')
    for v in ticks:
        out.append(f'<line class="grid" x1="{L}" y1="{y(v):.1f}" x2="{W - R}" y2="{y(v):.1f}"/>'
                   f'<text class="t2" x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v:,}</text>')
    for h in range(0, 24, 3):
        out.append(f'<text class="t2" x="{x(h):.1f}" y="{H - B + 18}" text-anchor="middle">{h:02d}:00</text>')
    out.append(f'<text class="t2" x="{(L + W - R) / 2}" y="{H - 8}" text-anchor="middle">hour (IST)</text>')
    ends = []
    for name, vals, cls, dash in series:
        pts = " ".join(f"{x(h):.1f},{y(v):.1f}" for h, v in enumerate(vals))
        out.append(f'<polyline class="{cls}" fill="none" stroke-width="2" stroke-linejoin="round" points="{pts}"{dash}/>')
        for h, v in enumerate(vals):  # native tooltip per point
            out.append(f'<circle cx="{x(h):.1f}" cy="{y(v):.1f}" r="6" fill="transparent"><title>{name}, {h:02d}:00 IST: {v:,.0f} MW</title></circle>')
        ends.append([y(vals[-1]), name, cls])
    ends.sort()
    for k in range(1, len(ends)):  # keep end labels from colliding
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 15)
    for ly, name, cls in ends:
        n = cls[-1]
        out.append(f'<circle class="f{n}" cx="{W - R + 8}" cy="{ly - 4:.1f}" r="4"/><text class="t1" x="{W - R + 16}" y="{ly:.1f}">{name}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------- 3. false-done trace from the emulator through the real API ----------
def false_done_trace():
    tmp = Path(tempfile.mkdtemp())
    os.environ["NIVAWATT_DB"] = str(tmp / "e.db")
    (tmp / "c.json").write_text(json.dumps({"operator_code": "op", "manager_codes": {"APT_1": "m1"},
                                            "device_tokens": {"bench-1": "dev"}}))
    os.environ["NIVAWATT_CODES"] = str(tmp / "c.json")
    from fastapi.testclient import TestClient
    from backend.main import app
    from simulation.device_emulator import DeviceEmulator, load_profile
    c = TestClient(app)

    def call(m, p, tok, **b):
        r = c.request(m, "/api/v1" + p, json=b or None, headers={"Authorization": "Bearer " + tok})
        assert r.status_code == 200, (p, r.text)
        return r.json()
    op = call("POST", "/demo/session", "", role="operator", access_code="op")["token"]
    mg = call("POST", "/demo/session", "", role="manager", apartment_id="APT_1", access_code="m1")["token"]
    pf = load_profile()
    fs = call("GET", "/forecasts/evaluation", op)["demo_forecast_start"]
    f = call("POST", "/forecasts/replay", op, request_id="ev-f", dataset_id="kptcl-load-curve",
             model_name="ridge_lag_calendar", forecast_start=fs)
    run = call("POST", "/runs", op, request_id="ev-r", clock_start_utc=fs, apartment_params={
        "observation_source": "telemetry", "pump_inflow_lph": pf["pump"]["flow_lpm"] * 60})["run_id"]
    call("POST", "/events", op, request_id="ev-a", run_id=run, kind="peak_advisory", known_from_interval=0,
         forecast_id=f["forecast_id"], target_apartments=["APT_1"], peak_windows=f["peak_windows"],
         valid_from=f["forecast_start"], valid_until=f["forecast_end"])
    emu = DeviceEmulator(pf, run, device_id="bench-1", seed=1)
    rows, events = [], []
    for i in range(4):
        st = call("GET", f"/state?run_id={run}&apartment_id=APT_1", mg)
        for p in st["pending_proposals"]:
            st = call("POST", f"/proposals/{p['proposal_id']}/decision", mg, run_id=run, expected_revision=p["revision"],
                      decision="ACCEPT", option_id=p["options"][0]["option_id"], request_id=f"ev-acc{i}")
            events.append(f"interval {i}: manager accepted proposal ({p['reason']})")
        com = st["active_commitment"]
        a = next(x for x in com["option"]["actions"] if x["interval_index"] == i)
        want = ("pump ON" if a["pump"] == "ON" else "pump OFF") + ", " + ("EV ON" if a["ev"] != "OFF" else "EV OFF")
        claimed = ""
        if i == 1:  # the person reports done but leaves every switch off
            kind = "pump" if a["pump"] == "ON" else "ev"
            call("POST", "/execution/claims", mg, run_id=run, commitment_id=com["commitment_id"], interval_index=i,
                 action_id=f"{com['commitment_id']}:{i}:{kind}", request_id="ev-claim")
            claimed = f"done ({kind})"
            emu.pump_on = emu.ev_on = False
        else:
            emu.pump_on, emu.ev_on = a["pump"] == "ON", a["ev"] != "OFF"
        for s in emu.interval_samples(i):
            call("POST", "/telemetry", "dev", **s)
        out = call("POST", f"/runs/{run}/step", op, request_id=f"ev-s{i}")
        o, ex = out["state"]["observation"], out["execution"]
        rb = o["raw_bench"]
        rows.append(f"| {i} | {want} | {'pump ' + ('ON' if emu.pump_on else 'OFF') + ', EV ' + ('ON' if emu.ev_on else 'OFF')} "
                    f"| {claimed or '-'} | {rb['sample_count']} | {rb['mean_pump_w']:.0f} | {rb['mean_ev_load_w']:.0f} "
                    f"| {o['tank_l']:.0f} | **{ex['observation_status']}** {ex['reason']} "
                    f"| {', '.join(p['reason'] for p in out['state']['pending_proposals']) or '-'} |")
    rep = call("GET", f"/runs/{run}/report", op)
    return f"""# False-done trace (emulated device, real API)

Run `{run}`. A ridge forecast for {ist_label(fs)[:10]} produced an operator-approved advisory, and the apartment plan was accepted.
The device emulator (`simulation/device_emulator.py`, reference profile `{pf['profile_id']}`) posted one reading per second; each step closed a 15-minute model interval.
In interval 1 the manager reported done while every switch was left off.

| Interval | Plan | Actual switches | Manager report | Readings | Mean pump W | Mean EV W | Tank L | Verdict from readings | New proposal |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

{chr(10).join('- ' + e for e in events)}

Report counts: {json.dumps(rep['counts'])}. Observation coverage: {rep['observation_coverage']['valid']} of {rep['observation_coverage']['intervals_elapsed']} intervals.

**All readings are `source_kind=synthetic`** (emulated device, not a physical sensor). Acceptance never switched anything; the manager's report stayed on record after the readings contradicted it, and the revision was not active until accepted.
"""


# ---------- 4. comparison results ----------
def comparison():
    doc = json.loads((ROOT / "results" / "experiments" / "exp-default" / "summary.json").read_text())
    S = doc["summary"]
    P = ["uncoordinated", "demand_cap", "fixed_plan", "ack_replan", "aggregate_replan", "measured_replan"]
    lines = ["# Simulated policy comparison", "",
             f"Source: `results/experiments/exp-default/` (generated at commit `{doc['software_commit'][:7]}`, "
             f"{doc['config']['seeds_per_stochastic_scenario']} seeds per stochastic scenario). **Synthetic simulation, not bench evidence.**", "",
             "Mean per run. EV = energy short at departure (model kWh). Reserve = 15-min intervals below the water reserve. "
             "Peak = participating energy inside advisory hours (model kWh).", "",
             "| Scenario | Metric | " + " | ".join(P) + " |", "|---|---|" + "---|" * len(P)]
    for s, v in S.items():
        for m, label in (("ev_shortfall_model_kwh", "EV"), ("reserve_violation_intervals", "Reserve"),
                         ("peak_window_energy_model_kwh", "Peak")):
            lines.append(f"| {s} | {label} | " + " | ".join(f"{v[p][m]['mean']:g}" for p in P if p in v) + " |")
    lines += ["", "## Paired comparisons (same seed, same human behaviour)", "",
              "| Scenario | Measured vs acknowledgement: EV better / tie / worse | Branch vs aggregate meter: EV better / tie / worse |",
              "|---|---|---|"]
    for s, v in S.items():
        a = v["paired_measured_minus_ack"]["ev_shortfall_model_kwh"]
        b = v["paired_branch_minus_aggregate"]["ev_shortfall_model_kwh"]
        lines.append(f"| {s} | {a['measured_better_runs']} / {a['ties']} / {a['baseline_better_runs']} "
                     f"| {b['measured_better_runs']} / {b['ties']} / {b['baseline_better_runs']} |")
    lines += ["", "## Reading this honestly", "",
              "- With perfect execution every policy ties; the advantage comes only from catching false or missed actions.",
              "- Missed pump actions tie between acknowledgement and measured replanning because both see the same tank level.",
              "- With stale telemetry the fixed plan beats both replanners on water: stale tank readings mislead replanning.",
              "- Automatic policies (uncoordinated, demand_cap) have more control authority and are not subject to human misses; their water results are not a scheduling comparison.",
              "- The demand cap never bound in these runs, so it equals uncoordinated.",
              "- A single aggregate meter checked against claims catches most false EV claims; branch meters add a small gain when loads overlap."]
    return "\n".join(lines) + "\n"


LIMITS = """# Limitations (state these when presenting)

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
"""


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    ev = json.loads((ROOT / "results" / "forecast_evaluation.json").read_text())
    (OUT / "dataset_record.md").write_text(dataset_record(ev), encoding="utf-8")
    md, svg = heldout(ev)
    (OUT / "forecast_heldout.md").write_text(md, encoding="utf-8")
    (OUT / "forecast_demo_day.svg").write_text(svg, encoding="utf-8")
    (OUT / "false_done_trace.md").write_text(false_done_trace(), encoding="utf-8")
    (OUT / "comparison_results.md").write_text(comparison(), encoding="utf-8")
    (OUT / "LIMITATIONS.md").write_text(LIMITS, encoding="utf-8")
    (OUT / "README.md").write_text(f"""# NivaWatt evidence pack

Generated by `python scripts/build_evidence.py` at commit `{commit()}`. Regenerate it rather than editing by hand.

| File | What it shows |
|---|---|
| [dataset_record.md](dataset_record.md) | Data source, scope, licence, fingerprint, gaps, duplicates, train/validation/test split |
| [forecast_heldout.md](forecast_heldout.md) | Held-out accuracy of both models, per-day results, demo-day hourly table and chart |
| [false_done_trace.md](false_done_trace.md) | A false done report caught by device readings, interval by interval |
| [comparison_results.md](comparison_results.md) | Simulated policy comparison with paired win/tie/loss counts |
| [LIMITATIONS.md](LIMITATIONS.md) | What this prototype does not show |

Screenshots of the connected interface: `tests/ui/screenshots/` (UI workstream).
""", encoding="utf-8")
    print("wrote", sorted(p.name for p in OUT.iterdir()))
