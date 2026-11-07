# Dataset record

| Field | Value |
|---|---|
| Source | KPTCL daily load-curve reports, parsed by Vonter/kptcl-load-curve |
| Archive | https://github.com/Vonter/kptcl-load-curve |
| Original reports | https://loadcurve.kptcl.net/LoadCurveUpload/lcdownloadview.asp |
| Licence | Open Database License (ODbL) 1.0; some contents copyright KPTCL. Raw file is not redistributed here. |
| Geographic scope | **Karnataka state grid (KPTCL). Not BESCOM feeder, transformer or apartment demand.** |
| Unit / resolution | MW, 60 min |
| Timezone | Report clock times assumed to be IST (UTC+05:30); converted to UTC by subtracting 5h30m. |
| File fingerprint (SHA-256) | `61538bc849335f960bac29dae1a33e8d25221cfc0e3284f832fda320555331ff` |
| Coverage | 2010-12-31T18:30:00Z to 2026-08-19T18:30:00Z |
| Raw rows | 135,774 |
| Null / implausible loads removed | 0 / 0 |
| Duplicate timestamps | 5,344 (277 with differing values). Rule: When report hour 24 (day D) and hour 0 (day D+1) coincide, keep the hour-0 row. |
| Missing hours | 6,611 of 137,041 expected. none; days with any missing hour are excluded from training/evaluation targets |
| Complete IST days | 5,431 |
| Publication lag | UNVALIDATED. Evaluation is a historical timestamp-split backtest. |

## Split used for the forecast evaluation

| Block | From (UTC) | To (UTC) |
|---|---|---|
| Train | 2026-05-18T18:30:00Z | 2026-07-14T18:30:00Z |
| Validation | 2026-07-14T18:30:00Z | 2026-08-03T18:30:00Z |
| Test | 2026-08-03T18:30:00Z | 2026-08-19T18:30:00Z |

Rule: most recent usable complete IST days: 56 train / 14 validation / 14 test. Calendar spans exceed the day counts where days with missing hours were skipped.
Inputs: inputs use lags >= 48 h; training targets end before D-1.

The raw file is not redistributed (ODbL share-alike; some contents copyright KPTCL). `scripts/fetch_kptcl.py` downloads and verifies it.
OpenCity BESCOM resources were reviewed and are not intraday load series: see `data/OPENCITY_BESCOM_REVIEW.md`.
