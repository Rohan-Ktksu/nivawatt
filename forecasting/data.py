"""Load and validate the KPTCL-derived hourly Karnataka grid-load archive.

Scope: Karnataka STATE grid load (MW). This is not BESCOM feeder, transformer or apartment demand.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "kptcl.parquet"
SOURCE = {
    "dataset_id": "kptcl-load-curve",
    "source_name": "KPTCL daily load-curve reports, parsed by Vonter/kptcl-load-curve",
    "source_url": "https://github.com/Vonter/kptcl-load-curve",
    "original_reports": "https://loadcurve.kptcl.net/LoadCurveUpload/lcdownloadview.asp",
    "license": "Open Database License (ODbL) 1.0; some contents copyright KPTCL. Raw file is not redistributed here.",
    "geographic_scope": "Karnataka state grid (KPTCL). Not BESCOM feeder, transformer or apartment demand.",
    "demand_unit": "MW",
    "resolution_minutes": 60,
    "timezone_assumption": "Report clock times assumed to be IST (UTC+05:30); converted to UTC by subtracting 5h30m.",
}
IST = pd.Timedelta(hours=5, minutes=30)


def fingerprint(path=RAW):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_validated(path=RAW):
    """Return (hourly UTC series indexed by hour start, validation report dict)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run: python scripts/fetch_kptcl.py")
    raw = pd.read_parquet(path)
    required = {"report_date", "observed_at", "report_hour", "grid_load_mw"}
    missing_cols = required - set(raw.columns)
    if missing_cols:
        raise ValueError(f"dataset missing columns {sorted(missing_cols)}")

    rep = {**SOURCE, "dataset_fingerprint_sha256": fingerprint(path), "raw_rows": int(len(raw))}
    df = raw[list(required)].copy()
    df["observed_at"] = pd.to_datetime(df["observed_at"])
    if df["observed_at"].dt.tz is not None:
        raise ValueError("unexpected tz-aware observed_at; timezone handling must be re-checked")

    rep["null_load_rows_removed"] = int(df["grid_load_mw"].isna().sum())
    df = df.dropna(subset=["grid_load_mw"])
    bad = (df["grid_load_mw"] <= 0) | (df["grid_load_mw"] > 30000)
    rep["implausible_load_rows_removed"] = int(bad.sum())
    df = df[~bad]

    # Hour 24 of report D and hour 0 of report D+1 are the same instant: keep the hour-0 row.
    dup = df.duplicated("observed_at", keep=False)
    grp = df[dup].groupby("observed_at")["grid_load_mw"]
    rep["duplicate_timestamps"] = int(grp.ngroups)
    rep["duplicate_timestamps_with_differing_values"] = int((grp.nunique() > 1).sum())
    df = df.sort_values(["observed_at", "report_hour"]).drop_duplicates("observed_at", keep="first")
    rep["duplicate_rule"] = "When report hour 24 (day D) and hour 0 (day D+1) coincide, keep the hour-0 row."

    s = df.set_index("observed_at")["grid_load_mw"].sort_index()
    s.index = s.index - IST  # IST -> UTC (naive UTC)
    full = pd.date_range(s.index.min(), s.index.max(), freq="h")
    rep["first_observation_utc"] = s.index.min().isoformat() + "Z"
    rep["last_observation_utc"] = s.index.max().isoformat() + "Z"
    rep["expected_hours"] = int(len(full))
    rep["present_hours"] = int(len(s))
    rep["missing_hours"] = int(len(full) - len(s))
    rep["imputation"] = "none; days with any missing hour are excluded from training/evaluation targets"
    rep["publication_lag"] = "UNVALIDATED. Evaluation is a historical timestamp-split backtest."
    s = s.reindex(full)
    return s, rep


def complete_days(s):
    """IST calendar days (as UTC 18:30 starts) with all 24 hours present."""
    local = s.copy()
    local.index = local.index + IST
    counts = local.groupby(local.index.normalize()).count()
    return [d - IST for d in counts[counts == 24].index]


if __name__ == "__main__":
    series, report = load_validated()
    days = complete_days(series)
    report["complete_ist_days"] = len(days)
    print(json.dumps(report, indent=2))
