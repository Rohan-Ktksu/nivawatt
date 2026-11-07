# NivaWatt

**Forecast-Informed Apartment Demand Response with Measured Execution Feedback**

**Latest planning revision: v0.2, 7 November 2026.** Start with [NIVAWATT_BUILD_NOW.md](NIVAWATT_BUILD_NOW.md), the complete execution plan and copy-paste role prompts. This replaces the earlier apartment-only scope.

Historical regional demand informs a forecast. A demonstration operator approves a peak advisory. An apartment coordinator schedules pump and charging-emulator activity, records human acceptance and claims, measures execution and proposes revisions when needed.

## Current status

Core software checkpoint (feature/rohan-core): one local FastAPI service with SQLite. It provides historical-replay forecasting on Karnataka state hourly load, operator-approved peak advisories, and one **synthetic** apartment with a proposal, acceptance, claim, observation and revision loop. There is no connected hardware, no measured benefit results and no live BESCOM integration. See COORDINATION_ROHAN.md for actual test results.

## Run it (Windows, Python 3.12; commands as tested)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\fetch_kptcl.py      # ODbL dataset -> data/raw (not committed)
.venv\Scripts\python -m forecasting.evaluate       # chronological backtest -> results/forecast_evaluation.json
.venv\Scripts\python -m pytest                     # tests/core
.venv\Scripts\python app.py                        # http://127.0.0.1:8780 ; --host 0.0.0.0 for phones on the LAN
.venv\Scripts\python scripts\demo_flow.py          # replays the P0 loop via the API, writes handoff/*.json
```

Demo access codes are generated in `config/local.json` on first start. That file is ignored by Git and is not production authentication.

## Team starts

| Person | First instructions | Owned work |
|---|---|---|
| Rohan, Claude Code | [PROMPT_ROHAN.md](PROMPT_ROHAN.md) | Forecasting, core/API, scheduler, simulation, firmware review and integration |
| Sonia, Claude Code | [PROMPT_SONIA.md](PROMPT_SONIA.md) | Operator and apartment interfaces, API client and UI checks |
| Third teammate, basic Gemini | [GEMINI.md](GEMINI.md) | Component inventory, calibration, independent testing, costs and evidence |

Read [AGENTS.md](AGENTS.md), [TEAM_WORKFLOW.md](TEAM_WORKFLOW.md), [CONTRACT.md](CONTRACT.md) and [TEST_AND_DEMO.md](TEST_AND_DEMO.md). Contract v0.2 is a proposed build target; no peer acceptance or test completion is implied.

## Build gates

1. Validate an attributed dataset and save a forecast snapshot. Approve a peak advisory.
2. Connect that advisory to one software apartment and complete proposal, acceptance, claim, observation and revision.
3. Connect calibrated physical pump/tank and charging-emulator measurements.
4. Compare acknowledgement-based and measured-execution replanning against a sensible demand-cap rule and report service outcomes.
5. Export evidence, costs and limitations before preparing the presentation.

Target a first connected software demonstration in a focused session. The 6-8-hour target is conditional; physical calibration and defensible evaluation may require a further session. Do not delay UI integration for elaborate forecasting or a solver.

## Data and demonstration boundaries

The candidate KPTCL-derived archive documents hourly Karnataka grid demand, not BESCOM feeder or apartment demand. Validate the actual file and preserve attribution/licensing conditions before use: https://github.com/Vonter/kptcl-load-curve

A regional forecast identifies peak hours. It does not establish local transformer capacity or automatically determine an apartment kW limit. A configured allowance applies to participating flexible loads unless broader measurement explicitly establishes otherwise.

One low-voltage bench represents a pump/tank and EV charging load. A resistor/other load emulates electrical consumption, not an actual EV battery. Keep hardware W/Wh separate from model kW/kWh. Label synthetic data and simulated comparisons.

## Fixtures

[STATE_EXAMPLE.json](STATE_EXAMPLE.json) and [TELEMETRY_EXAMPLE.json](TELEMETRY_EXAMPLE.json) describe apartment/telemetry shapes. [FORECAST_EXAMPLE.json](FORECAST_EXAMPLE.json) and [ADVISORY_EXAMPLE.json](ADVISORY_EXAMPLE.json) add explicitly synthetic forecasting/advisory shapes. Fixture values are not experimental results.

## Start in a separate clone

```powershell
git clone https://github.com/oxydevelopers/nivawatt.git
cd nivawatt
git config user.name
git config user.email
git status --short
```

Read the branch/review instructions before beginning. If the latest plan is still in a PR, use that PR's branch deliberately; a normal clone checks out main. Each person uses their own verified Git identity and role branch. Do not change the remote or source of the unrelated CampusResolve checkout.

Keep credentials, runtime databases and environments outside Git. No paid APIs/services, background model bridges or automatic main merge.

## Contribution and evidence

Our candidate contribution is measured-execution feedback for human-operated apartment response. Test it against acknowledgement-based replanning with fair information and service requirements. Forecasting, meters and scheduling methods are existing technologies. No first-ever, patent, savings, emissions or grid-protection claim is established by this plan.

Existing OutageReady-FlexProof code may be selectively reused only after authorized inspection and provenance review. Record actual commands/results in each owner's coordination file. Do not copy an old repository's instructions or claim its charts as NivaWatt evidence.
