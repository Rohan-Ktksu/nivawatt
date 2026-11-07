"""Chronological backtest of seasonal_naive vs ridge_lag_calendar and forecast snapshot builder.

Run: python -m forecasting.evaluate   -> writes results/forecast_evaluation.json
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from forecasting import data, models

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "forecast_evaluation.json"
# Predeclared split over the most recent complete IST days: 8 weeks train, 2 validation, 2 test.
TRAIN_D, VAL_D, TEST_D = 56, 14, 14
ALPHAS = (0.1, 1.0, 10.0, 100.0)
HISTORY_DAYS = 15  # longest lag (336 h) plus margin


def usable_days(s):
    """Complete days whose own targets and all lagged inputs exist."""
    out = []
    for d in data.complete_days(s):
        need = [models.target_hours(d) - lag * models.H for lag in models.LAGS_H]
        if all(s.reindex(n).notna().all() for n in need):
            out.append(d)
    return out


def split(s):
    days = usable_days(s)
    n = TRAIN_D + VAL_D + TEST_D
    if len(days) < n:
        raise ValueError(f"only {len(days)} usable days; need {n}")
    days = days[-n:]
    return days[:TRAIN_D], days[TRAIN_D:TRAIN_D + VAL_D], days[TRAIN_D + VAL_D:]


def score(s, days, predict):
    maes, overlaps = [], []
    for d in days:
        actual = s.reindex(models.target_hours(d)).to_numpy()
        pred = predict(d)
        maes.append(float(np.mean(np.abs(pred - actual))))
        a_idx, _ = models.top3(actual, d)
        p_idx, _ = models.top3(pred, d)
        overlaps.append(len(set(a_idx) & set(p_idx)) / 3)
    return {"days": len(days), "mae_mw": round(float(np.mean(maes)), 1),
            "top3_peak_hour_overlap": round(float(np.mean(overlaps)), 3)}


def run():
    s, rep = data.load_validated()
    rep["complete_ist_days"] = len(data.complete_days(s))
    train, val, test = split(s)
    naive = lambda d: models.seasonal_naive(s, d)
    val_scores = {}
    for a in ALPHAS:
        m, _ = models.fit_ridge(s, train, a)
        val_scores[a] = score(s, val, lambda d: m.predict(models.features(s, models.target_hours(d))))
    alpha = min(ALPHAS, key=lambda a: val_scores[a]["mae_mw"])
    final, ndays = models.fit_ridge(s, train + val, alpha)
    ridge = lambda d: final.predict(models.features(s, models.target_hours(d)))
    span = lambda ds: {"first_day_start_utc": models.iso(ds[0]), "last_day_end_utc": models.iso(ds[-1] + 24 * models.H)}
    result = {
        "generated_at": now(),
        "kind": "historical timestamp-split backtest (publication lag unvalidated)",
        "data_validation": rep,
        "split": {"train": span(train), "validation": span(val), "test": span(test),
                  "rule": f"most recent usable complete IST days: {TRAIN_D} train / {VAL_D} validation / {TEST_D} test"},
        "input_availability": "inputs use lags >= 48 h; training targets end before D-1",
        "ridge": {"alpha_candidates": list(ALPHAS), "validation": {str(a): v for a, v in val_scores.items()},
                  "selected_alpha": alpha, "refit_on": "train+validation", "training_days": ndays,
                  "features": "load lags 48/168/336 h, IST hour-of-day and day-of-week dummies"},
        "test": {"seasonal_naive": score(s, test, naive), "ridge_lag_calendar": score(s, test, ridge)},
        "demo_date_rule": "forecast_start = start of the final test day (predeclared, not chosen for performance)",
        "demo_forecast_start": models.iso(test[-1]),
        "note": "Peak-hour overlap uses top-3 hours per day, ties broken by earliest start.",
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    return result


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_snapshot(s, rep, model_name, forecast_start, evaluation_reference=None):
    """Forecast for one IST day using only data available at issue. Returns the snapshot dict (no id)."""
    if model_name not in models.MODELS:
        raise ValueError(f"unknown model {model_name}")
    fs = pd.Timestamp(forecast_start).tz_localize(None) if pd.Timestamp(forecast_start).tzinfo else pd.Timestamp(forecast_start)
    if (fs + pd.Timedelta(hours=5, minutes=30)) != (fs + pd.Timedelta(hours=5, minutes=30)).normalize():
        raise ValueError("forecast_start must be 00:00 IST (18:30 UTC)")
    cutoff = fs - models.AVAILABLE_UNTIL
    hist = s[s.index < cutoff]  # nothing at/after cutoff reaches the model
    if model_name == "seasonal_naive":
        pred = models.seasonal_naive(hist, fs)
        training_end = None
    else:
        days = [d for d in usable_days(hist) if d + 24 * models.H <= cutoff][-(TRAIN_D + VAL_D):]
        alpha = 10.0
        if OUT.exists():
            alpha = json.loads(OUT.read_text())["ridge"]["selected_alpha"]
        m, _ = models.fit_ridge(hist, days, alpha)
        pred = m.predict(models.features(hist, models.target_hours(fs)))
        training_end = models.iso(days[-1] + 24 * models.H)
    if np.isnan(pred).any():
        raise ValueError("insufficient history before forecast_start")
    hours = models.target_hours(fs)
    _, windows = models.top3(pred, fs)
    return {
        "schema_version": "0.2",
        "source_kind": "historical_replay",
        "source_name": rep["source_name"], "source_url": rep["source_url"],
        "geographic_scope": rep["geographic_scope"], "resolution_minutes": 60, "demand_unit": "MW",
        "model_name": model_name, "model_kind": models.MODELS[model_name],
        "dataset_fingerprint": rep["dataset_fingerprint_sha256"], "training_end": training_end,
        "last_observation_time": models.iso(hist.dropna().index.max()),
        "issued_at": now(),
        "availability_assumptions": "Historical replay. Assumes reports through D-2 were published by 00:00 IST of D; "
                                    "publication lag not validated. Not a live KPTCL/BESCOM connection.",
        "forecast_start": models.iso(fs), "forecast_end": models.iso(fs + 24 * models.H),
        "points": [{"start": models.iso(t), "end": models.iso(t + models.H), "predicted_mw": round(float(p), 1)}
                   for t, p in zip(hours, pred)],
        "peak_windows": windows,
        "evaluation_reference": evaluation_reference,
    }


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("split", "test", "demo_forecast_start")}, indent=2))
    print("ridge alpha:", r["ridge"]["selected_alpha"])
