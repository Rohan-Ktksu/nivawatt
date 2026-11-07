# OpenCity BESCOM dataset review (7 Nov 2026)

Source: OpenCity CKAN organization `bangalore-electricity-supply-company-limited`, queried via
`https://data.opencity.in/api/3/action/package_search?fq=organization:bangalore-electricity-supply-company-limited&rows=200`
(10 datasets). All 22 CSV resources downloaded without errors. The files are not committed here: the `bescom-data` licence is unspecified, and the others are marked "Other (Public Domain)". The fingerprints are the first 16 hex digits of each file's SHA-256.

## Decision

**No OpenCity BESCOM resource contains a timestamped intraday load series (MW/kW).** All tabular data is annual or by financial year. None of it can train or evaluate an hourly peak forecast, and annual totals are **not** interpolated into hourly observations. The forecasting input stays the **Karnataka state hourly grid load** (KPTCL-derived, see `forecasting/data.py`). It is still labelled state-level, not BESCOM feeder demand.

## Quantity types (do not mix)

- **Revenue demand (₹):** "Demand (in Rs. Cr)" in the annual file is billed revenue demand in rupees crore. It is **not** electrical demand.
- **Energy (MU, kWh):** consumption, energy input, units sold, EV kWh.
- **Electrical demand (MW, kW):** none in these CSVs. The only power-type figures are substation voltage classes (kV), which are not load.

## Resources inspected

| Dataset / resource | Columns (abridged) | Units | Coverage | Resolution | Use | sha256 (16) |
|---|---|---|---|---|---|---|
| bescom-consumption-data / Annual Consumption and Revenue 2010-11 to 2022-23 | Year, Demand (in Rs. Cr), Collection (in Rs. Cr), Consumers in Lakhs, Consumption by Metered Category in MU, Energy Input in MU | ₹ crore, lakh consumers, MU | FY2010-11 to FY2022-23 (13 rows) | annual | Context only (energy growth, consumer count) | 237fffc355abd7ef |
| bescom-ev-consumption-data / EV Consumption 2020-21 to 2022-23 | LT EV Charging Stations, LT Units in KWH, LT Gross Revenue Deman[d], LT Revenue Collected, HT EV stations / kWh / % / revenue | count, kWh; revenue unit **not stated** (likely ₹) | FY2020-21 to FY2022-23; HT only FY2022-23 | annual | Context only: LT EV kWh rose from 28,820 to 2,295,349 | 94edea747c42e8dd |
| bescom-data / Energy Requirement | Particulars, Approved FY2015-16, Actuals FY2015-16 | MU, % loss | FY2015-16 | annual | Context only | 413762832c922f0d |
| bescom-data / Number Of Units Sold | category, unit, FY-16, FY-15, % change | MU | FY15–FY16 | annual | Context only | 577621486f5fc11f |
| bescom-data / Number of Consumers | category, unit, FY-16, FY-15 | lakh / count | FY15–FY16 | annual | Context only | 9e6fdeb7b163aa29 |
| bescom-data / Sales Realization | category, ₹ cr and ₹/unit, FY-16, FY-15 | ₹ crore, ₹/kWh | FY15–FY16 | annual | Unsuitable (revenue) | 9f29dd9717534778 |
| bescom-data / Sales Revenue | category, ₹ cr and ₹/unit, FY-16, FY-15 | ₹ crore, ₹/kWh | FY15–FY16 | annual | Unsuitable (revenue) | 791d5402edbfacd4 |
| bescom-data / Operating Ratio | cost shares FY14–FY16 | % | FY14–FY16 | annual | Unsuitable | de60dafe0f3d2ae5 |
| bescom-data / Renewable Energy Purchase | source, Energy in MU, Amount in Crs., Rs/unit | MU, ₹ crore | FY2015-16 | annual | Unsuitable | b075a79068ada02d |
| bescom-data / Bengaluru Electrical Substations | Zone, District, Taluk, Name, Voltage Class (kV), Date of commission | kV | 280 rows (244 at 66 kV, 34 at 220 kV, 2 at 400 kV) | static register | No loading or capacity values; unsuitable for demand | cedaebc95f1610cc |
| bescom-high/low-tension-lines-data (12 CSVs) | division, OH/UG/AB added/dismantled/total | km | FY2018-19 to FY2023-24 | annual asset register | Unsuitable (network length, not load) | — |

The remaining resources were not parsed as data. They are PDFs (tariff orders, ARR/truing-up filings, the firefighting-equipment notice, a 2016 brief) and KML boundary maps. They are reports and maps, not machine-readable timestamped load series. A PDF may include load tables, but extracting tables from PDFs is out of scope for this gate.

## How annual figures may be used

Use them only as attributed background, for example: "BESCOM LT EV charging energy grew from 28,820 kWh (FY2020-21) to 2,295,349 kWh (FY2022-23), source: OpenCity / BESCOM". They give no hourly shape, peak MW or feeder capacity. They do not set any apartment allowance.
