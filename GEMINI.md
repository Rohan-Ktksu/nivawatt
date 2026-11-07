# NivaWatt teammate 3: basic Gemini workflow v0.2

You are responsible for hardware preparation, independent testing and evidence. You do not need a terminal coding agent. Your name and GitHub handle have not been assumed; Rohan can fill them in later.

Read NIVAWATT_BUILD_NOW.md first. It is the complete current execution reference, including evidence gates and copy-paste starts.\n\n## Paste this into your existing Gemini chat

Help me carry out the hardware-preparation and validation role for oxydevelopers/nivawatt. I have basic Gemini chat, not a terminal agent. Read the project context below and guide me in small practical steps. Do not claim to have operated my computer, wired hardware, run code or verified measurements.

Our project is NivaWatt: Forecast-Informed Apartment Demand Response with Measured Execution Feedback. Regional demand history supports a forecast and an operator-approved peak advisory. Software then proposes apartment pump/charging schedules; a manager accepts and manually operates equipment; sensors check execution and trigger revised recommendations. This is not FDIA auditing or a BESS project. The operator/BESCOM view is simulated.

Rohan/Claude owns data validation, demand forecasting, core/backend/scheduler/firmware review. Sonia/Claude owns web interfaces. I own hardware/, validation/, scenarios/ under the provided schema, and presentation/. I should not edit their implementation or contract.

My first task: prepare hardware/INVENTORY.md recording exact part markings, quantity, supply ratings, existing condition and what is missing. Available items must be confirmed by me; do not assume catalogue specifications from a photograph or propose paid purchases. Ask only necessary questions.

For the bench we seek an ESP32, a mini low-voltage pump, two stable containers/tubing, tank-level sensing, suitable electrical measurement, manual switches, compatible drivers/protection and a regulated supply. Prefer separate pump/EV-load measurements if available. A single shared meter may not separate loads, and an LED/resistor represents a load rather than a real EV battery.

Help me document, with real measurements where possible:
- Empty/full tank reference marks and sensor repeatability.
- Pump water delivery at the actual lift, noting timing and volume.
- Pump-only, EV-load-only, both-on and both-off electrical readings.
- Supply and signal voltage compatibility based on exact component documentation.
- Any sensor ambiguity, missing reading or unstable wiring.

Do not recommend powering a pump from an ESP32 pin, assume a relay has suitable ratings, or bypass equipment protections. Assembly/wiring should be reviewed by Rohan or a competent college lab person. Never call a guessed calibration a measured one.

Next, help me prepare scenario steps in validation/SCENARIOS.md: normal operation; done-tap without action; physical action without done-tap; delayed acceptance; changed EV deadline; extra water withdrawal; announced outage; unexpected outage; missing readings. Use the same initial conditions and declared rules for comparisons. Scenario files must distinguish events known to the scheduler from hidden future disturbances.

Use TEST_AND_DEMO.md supplied by Rohan as the acceptance reference. For each test record exact steps, expected result, actual result, run ID/commit and screenshot/log filename. Never fabricate a pass or a performance percentage. If I cannot run it yet, mark NOT RUN.

Also prepare an actual BOM with exact model, quantity, dated price/source, replacement cost, college-provided quantity and additional cash required. College provision is not zero replacement cost. Do not invent a total.\n\nFinally help me explain the complete data/forecast/advisory/apartment/measurement loop, measured-vs-acknowledged experiment, actual results and limitations. Forecasting may use an actually fitted local regression, but a fixture is not evidence of training. No first-ever claim, transformer protection, unmeasured financial savings, utility integration or unsupported model accuracy.

Give me concise Markdown files I can save/upload manually. Basic Gemini cannot push commits itself. Do not keep researching broadly; focus on inventory, exact component references, calibration, test execution and evidence.

## Manual GitHub workflow

1. Open https://github.com/oxydevelopers/nivawatt while signed into your own account.
2. If you cannot view or contribute, tell Rohan; do not use another person's credentials.
3. Use Add file -> Create new file for hardware/INVENTORY.md, hardware/CALIBRATION.md or validation/SCENARIOS.md. Paste only material you checked.
4. Choose a new branch/PR, preferably feature/hardware-validation; do not commit to main behind the other developers.
5. Update COORDINATION_TEAMMATE3.md on your branch with hardware status, tests actually run and the PR link. If the web workflow cannot edit several files in one PR, use small named branches and tell Rohan which PRs to review.

Do not upload credentials, personal consumer records or private WhatsApp conversations. Evidence should use synthetic requirements and your own consenting bench setup.

## Inventory template

| Component | Exact marking/model | Quantity | Supply/logic requirements verified from | Available/working | Missing or concern |
|---|---|---:|---|---|---|
| ESP32 | TO CONFIRM | 0 confirmed | NOT CHECKED | NOT CHECKED | |
| Pump and power supply | TO CONFIRM | 0 confirmed | NOT CHECKED | NOT CHECKED | |
| Electrical sensor(s) | TO CONFIRM | 0 confirmed | NOT CHECKED | NOT CHECKED | |
| Tank sensor and containers | TO CONFIRM | 0 confirmed | NOT CHECKED | NOT CHECKED | |

Zero confirmed means nobody has recorded verification yet, not that the college has no parts.
