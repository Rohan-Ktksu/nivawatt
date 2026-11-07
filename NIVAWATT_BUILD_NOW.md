# NivaWatt: build-now execution plan

Revision 0.2, 7 November 2026. Repository: https://github.com/oxydevelopers/nivawatt

This is a plan, not implementation evidence. It restores forecasting to the earlier apartment-only planning pack. No application build, device connection, experiment result, price or live BESCOM integration is established by this document. No presentation is requested or created here.

## 1. Frozen project

NivaWatt: Forecast-Informed Apartment Demand Response with Measured Execution Feedback.

Use a historical regional-demand time series to forecast likely peak hours. An operator approves a peak advisory. An apartment coordinator proposes pump and charging-emulator schedules, receives the manager's acceptance, observes execution and proposes revisions when needed. Measure participating flexible loads and service outcomes.

Initial scope: one operator, one apartment manager, one pump/tank, one EV-emulator branch, one local application, one historical forecasting replay and an independent comparison simulator. The second apartment is a stretch simulation. Equipment switching remains manual. No BESS, FDIA classifier, transformer-health predictor, paid model API, WhatsApp integration, new model downloads, automatic mains control or production utility connection.

The candidate contribution is the measured-execution feedback and its evaluation. Forecasting, meters and scheduling are existing methods. Do not claim first-ever status or patentability.

## 2. Ownership and collaboration

| Person | Branch | Owned work |
|---|---|---|
| Rohan, Claude Code | feature/rohan-core | data ingestion, forecasting/, backend/, scheduler/, simulation/, firmware/, scripts/, tests/core/, dependencies, shared contracts and integration |
| Sonia, Claude Code | feature/sonia-ui | web/, tests/ui/, COORDINATION_SONIA.md |
| Third teammate, basic Gemini | feature/hardware-validation | hardware/, validation/, scenarios/ under the agreed schema, presentation evidence, COORDINATION_TEAMMATE3.md |

Do not infer the third teammate's name. Each person uses their own authenticated Git identity. Each human starts/resumes their own assistant. Gemini chat does not have assumed repository, terminal or device access.

Use a separate clone of nivawatt. The existing CampusResolve repository is unrelated. Inspect existing nivawatt code before scaffolding; source may have changed since the original documentation upload. Keep a working stack if one exists. For an empty implementation, use one local Python/FastAPI service, SQLite and plain JavaScript/CSS pages under web/. No additional frontend service is necessary.

Read AGENTS.md, this document, CONTRACT.md and the relevant role prompt. This document supersedes the older apartment-only scope. CONTRACT.md v0.2 contains the proposed additive target; Rohan confirms its implementation details and Sonia acknowledges the exact version and commit before relying on changed fields. Existing accepted fields must not be silently renamed.

At each integration gate, record branch/commit, actual commands/results, working routes, limitations and the next action in the owner's coordination file. Stage only owned files. Push and open small PRs. Rohan reviews and merges ready work. Assistants do not force-push or automatically merge main. Fetch at handoff boundaries, not in background polling loops.

## 3. Architecture and folder boundaries

data/ contains an ignored/local source cache and a small distributable fixture only when licensing allows it. forecasting/ consumes regional data and writes immutable forecast snapshots. backend/ owns API, authorization, persistence and event history. scheduler/ is a pure planning function. simulation/ owns independent policy runs, plants and evaluation truth. firmware/ reads bench sensors. web/ renders authoritative API state. hardware/ and validation/ contain measured evidence and inventory.

One origin serves /operator and /manager. One API client handles browser requests. Browser scores and sample JSON must never replace server computation. No cloud is necessary for the local demonstration. The operator interface says DEMONSTRATION. Manager writes are apartment-scoped, operator events are operator-scoped and device telemetry uses a local provisioned credential. Keep credentials outside Git. Local demo identity is not production authentication.

## 4. Gate A: establish the forecast-to-advisory handoff

### Data decision

Candidate source: the public archive at https://github.com/Vonter/kptcl-load-curve and its DATA.md. The documented load series is hourly Karnataka grid load in MW, not BESCOM feeder load. Its README links the original KPTCL reports and states attribution/licensing conditions. The official portal was inaccessible during a planning check, so do not require venue internet or a live scraper.

Before modelling, Rohan inspects the downloaded file, columns, date coverage, nulls, units, duplicates, timezone assumptions and source attribution. Report-hour 24 and hour 0 require correct handling. Count and record all removals/imputations. Do not call the file validated merely because its README exists. Keep source and derived values distinguishable. Do not redistribute restricted source data blindly.

Choose one recent sufficiently complete span after inspecting coverage. Use at least several complete weekly cycles for a weekly baseline. A practical initial choice is roughly 8-12 usable weeks with an earlier training block, a later validation block and a final untouched test block, if the source supports it. Record exact dates and dataset fingerprint. Use longer history only if easy and justified. Daily peak-only records cannot train an hourly intraday peak forecast.

Evaluate a same-hour-previous-week baseline and one small regression model using available lagged demand and calendar inputs. Do not add weather until an aligned, available-at-issue-time source exists. Do not random-split a time series. Compute features, imputation, model selection and thresholds without test leakage. Do not use actual earlier hours of the forecast day for a day-ahead forecast. If publication availability is unknown, call the evaluation a historical timestamp-split backtest and disclose that operational publication lag has not been validated.

Forecast the next 24 hourly values. For the initial demo, select the three highest forecast hours with deterministic tie handling. This is a prototype peak-selection rule, not a utility limit. Keep disjoint hours disjoint. Compare demand MAE in MW and top-three peak-hour overlap on held-out days. Select any demo date by a predeclared rule rather than choosing only a favourable day.

No model is guaranteed to beat the baseline. Report both. A saved historical replay is sufficient for the prototype. If no usable source can be validated promptly, use a visibly synthetic signal to unblock integration and leave the real-data forecasting gate explicitly incomplete.

### Immutable forecast record

Minimum fields: forecast_id, source_name, source_url, geographic_scope, resolution_minutes, demand_unit, model_name, model_kind, dataset_fingerprint, training_end, last_observation_time, issued_at, availability_assumptions, forecast_start, forecast_end, points[{start,end,predicted_mw}], peak_windows and evaluation_reference.

Snapshots never change when the UI reloads. Observed future values used for evaluation are not policy inputs. A model label is trained_regression only after actual fitting; seasonal_naive and rules remain separately labelled. A residual-derived uncertainty range may be added after validation, never fabricated as model confidence.

### Operator advisory record

Minimum fields: advisory_id, forecast_id, issued_at, approved_by_demo_operator, geographic_scope, valid_from, valid_until, peak_windows, target_apartments and source_kind. An advisory can include a separately configured participating-flexible-load allowance.

A regional forecast does not establish a local transformer rating. Do not automatically convert MW into an apartment kW cap. A participating-load allowance is distinct from a whole-building cap. Unmetered background load remains unknown unless explicitly measured or modelled.

## 5. Gate B: connect one software apartment

Rohan supplies the v0.1 endpoints needed for one run, state retrieval, operator events, requirements, proposal decisions, execution claims, telemetry, simulation stepping and reports. Proposed additive v0.2 endpoints are POST /api/v1/forecasts/replay and GET /api/v1/forecasts/{id}. Operator-only replay creation returns a forecast snapshot identifier. Reuse POST /api/v1/events with kind=peak_advisory and forecast_id rather than adding another event service. GET operator/manager state includes current forecast/advisory references. These additions are specified in CONTRACT.md v0.2 and remain unimplemented until the team supplies code and verification.

Agree one JSON example before parallel implementation. A synthetic fixture has source_kind=synthetic and a conspicuous UI label. Sonia begins with it immediately, then switches the single API client to real endpoints at the first handoff. There must be one consistent run_id, apartment_id and revision across all views.

Apartment inputs: tank capacity/current volume/reserve, source-water availability, pump flow and electrical power model, EV arrival/departure, requested/remaining electrical energy, available peak advisory and any known outage. Record how parameters were measured or assumed.

Use an explicit model interval, initially 15 minutes. Forecast values remain hourly; the mapping to model intervals repeats the hourly advisory and never invents 15-minute source measurements. Bench time and model time remain separate.

Start with a deterministic deadline-aware scheduler. Schedule enough pumping before water becomes insufficient and allocate eligible charging before departure while preferring non-peak periods and respecting the configured participating-load allowance. Preserve actual pump state/start history. If feasible scheduling fails, show an explicit shortfall rather than inventing feasibility. Optimizer upgrades follow only when their benefit is measurable and integration is stable.

Physical tank volume remains between zero and capacity. Track unmet water separately. Source-empty, overflow and device protections do not depend on the planner. Reserve compliance and charging completion are service outcomes, not consequences of matching electrical power. Electrical charging delivery is not battery SoC. A manager cannot approve a utility allowance increase through a proposal acceptance.

Proposal lifecycle and execution lifecycle remain separate. Acceptance applies to an exact version and effective time, expires server-side and does not switch equipment. A done tap records a claim. Sensors can later confirm, contradict or leave that claim unresolved. New proposals require acceptance. Stale/ambiguous observations produce UNKNOWN or STALE, not fabricated zero or confirmation. Store events and preserve history through restart.

Success condition: an operator-issued advisory produces an apartment proposal, the manager accepts it, a false done claim is contradicted by independent synthetic observations and the system issues a revised proposal. No hardware or comparison chart is needed to pass this first software gate.

## 6. Gate C: physical bench integration

The third teammate first records exact available models, quantities, ratings, interfaces, missing parts and lab supervision needs. Do not buy or assume substitutions. Proposed functional parts: ESP32, suitable small low-voltage DC pump, source/storage containers, tank-level sensor, independently measurable pump and charging-emulator branches, appropriate DC load, manual switches, rated supply and suitable protection/driver hardware. Rohan reviews pinout and firmware for the actual components. No mains equipment is necessary.

Calibrate tank level with measured volumes. Record pump delivery at the actual height using collected volume and elapsed time. Record voltage/current/power for branches off, pump only, charging emulator only and both. Test sensor noise/repeatability and timestamp alignment. These observations determine tolerances, not a guessed universal percentage.

For initial connectivity, use either an already working USB serial bridge or local Wi-Fi HTTP telemetry. Pick one. Wi-Fi firmware needs reconnection and queued/explicitly lost samples; USB still needs device-session IDs and sequencing. Do not build both adapters before one works. A phone on the local network accesses the same application with local demo authorization. Record actual working startup and connection instructions.

Telemetry includes device_id, boot/session_id, sequence, monotonic time, capture/receive timestamps, raw electrical values, tank measurement, quality flags and source_kind=hardware. Reject/deduplicate old samples and handle reboot counter resets. Preserve raw sensor observations and calibration identifiers.

Integrate bench energy from actual elapsed seconds: Wh=sum(W*delta_seconds)/3600. Simulation uses kW*model_hours. Any scaling has explicit power/time/volume factors and source_kind=scaled_hardware. Never report scaled values as field measurements. A missing branch measurement is null, not zero. A combined meter cannot establish per-EV energy when attribution is ambiguous.

Success condition: real readings update the application and an independently observed missed physical action drives a new proposal. The pump power plus tank response support pumping evidence. Emulator energy supports only electrical-load evidence. Local low-voltage safeguards and manual OFF remain available.

## 7. Gate D: evaluate the contribution

Policies: uncoordinated operation for context, a simple demand-cap rule, acknowledgement-based replanning and measured-execution replanning. A fixed schedule can be added if it adds understanding. Use the same scheduler for the acknowledgement and measured variants. Both receive the same available tank measurements; do not weaken the acknowledgement baseline to manufacture an advantage. The controlled distinction is electrical execution/progress evidence.

Each simulated policy has its own evolving plant. Share initial conditions, forecast, advisory, disturbance-generation rules, action authority, service requirements and human-response model. Express compliance as delays/missed actions relative to each issued action rather than forcing identical completed actions across different schedules. Keep evaluator truth out of policy inputs. Demand-cap baselines should receive sensible service priorities. These are our experimental baselines, not reproductions of specific papers.

Required cases: perfect execution, delayed/missed pump action, false done claim, stale/missing telemetry and infeasible service demand. Add wrong peak forecasts and outage/restart after the main comparison works. For stochastic runs, begin with 20 fixed seeds per stochastic scenario, report the number of runs, paired summaries and variability. This is an initial experiment set, not proof of statistical significance or field effectiveness.

Metrics: held-out forecast MAE and peak-hour overlap; participating-load peak kW; allowance exceedance kWh; energy shifted out of the same advisory windows; water-reserve violation time and unmet withdrawal; per-EV unmet electrical energy at departure; deviation-detection delay; manager actions/revisions; observation coverage. Acknowledge misses and ambiguity.

Use a horizon that includes deferred work and deadlines. Pair peak reduction with service shortfalls, total delivered energy and final tank state. Load shedding or unfinished work cannot masquerade as successful shifting. Exclude forced outage zeros from reduction credit. Report simulator results separately from bench results. Physical policy comparisons need independent repeated measured trials; simulated shadows remain simulations.

Success condition: export per-run CSV/JSON, parameters, seeds, software commit, metric definitions and a summary computed from those runs. No hard-coded winning percentages. Perfect execution should not require a claimed large advantage from execution feedback.

## 8. Sonia's screens

Operator: source/scope/time of forecast, actual-versus-predicted evaluation view, forecast peak hours, approval of an advisory, participating-load summaries and data-quality warnings. No live BESCOM branding/integration claim.

Manager: current water reserve, remaining requested charging energy/deadline, advisory times, applicable allowance, next action and reason, accept/decline, done claim, independent observation status, revised proposal and unmet-service warning. Plain language and phone-sized controls. Never label a claim as measured completion.

Comparison: server-generated metric table and one consistent timeline keyed to selected run, scenario and policy. Display source_kind on charts. Show errors and unavailable features honestly. UI fixture values disappear from the connected demonstration.

## 9. Timeline and stopping rules

These are targets for a focused sprint, not completion guarantees. Confirm the preliminary submission deadline separately; it is not supplied in this plan.

| Elapsed target | Rohan | Sonia | Third teammate |
|---|---|---|---|
| 0-30 minutes | Inspect source, agree additive schema, publish runnable foundation | Read fixture and start both page shells | Exact inventory, measurement checklist |
| 30-120 minutes | Data validation and baseline forecast, saved snapshot, advisory API | Forecast/advisory and apartment proposal screens | Bench preparation with lab support, record ratings |
| 2-4 hours | Software apartment, acceptance, claims, observation/replanning loop | Connect real API, revision/error/status handling | Independently test false done and invalid/stale actions |
| 4-6 hours | Candidate forecast model if data ready; device adapter if bench ready | Live telemetry, water/energy status and source labels | Calibration and actual telemetry tests |
| 6-8 hours | Repair integration, implement comparison pair before extra baselines | Computed comparison display and phone checks | Repeat demo and record evidence/costs |
| Following focused session | Broaden scenarios, validate forecasts/results, fix observed failures | Final usability fixes and reproducible views | Repeated trials, evidence and judge-question rehearsal |

At two hours, if data work is blocking the apartment loop, use an explicitly synthetic advisory while the real-data task remains open. At four hours, if the software loop is broken, stop new model/UI features and fix it. If the bench is unavailable, finish a clearly labelled simulation and report physical integration incomplete. If evaluation is missing, show implementation evidence without benefit percentages. Add a second apartment only after the core and evaluation gates.

## 10. Meaningful acceptance checks

1. Data report correctly identifies state scope, units, gaps and timezone. No historical future data leaks into a forecast or policy.
2. Forecast/advisory identifiers persist. Operator approval issues the advisory; a manager cannot change it or the operator allowance.
3. Accept an exact proposal, then resend it. Duplicates are idempotent. Expired/obsolete/wrong-run acceptance fails clearly.
4. Tap done with the pump off. Claim persists while observations contradict it. Replanning does not silently activate a proposal.
5. Pump ON without rising water does not count as successful tank filling.
6. Drop telemetry or reset device sequence. Display stale/unknown and preserve history. Do not infer consumption is zero.
7. Tank mass balance, energy units, departure cutoff, overflow and source-empty handling remain valid.
8. An impossible requirement produces visible shortfall, not a successful-completion badge.
9. All views and reports use the same selected run/revision. Restart preserves accepted plan and measured history.
10. Comparison policies share fair assumptions. Raw exports reproduce displayed metrics, including losses and service failures.
11. Run the complete phone flow on the intended local network. Test the actual offline replay, not a promise of venue connectivity.

## 11. Preliminary-round evidence and costs

Capture one dataset/validation record, held-out forecast chart with baseline, own bench photograph, own connected UI screenshots, false-done execution trace, matched result export and a bill of materials. Existing screenshots from another utility app are context, not our prototype evidence. Earlier AI-generated chart numbers are not our results.

Inventory/BOM columns: item, exact model, quantity, source/dated quote, unit cost, total replacement cost, college-provided quantity, additional cash required, measured/estimated status. College provision can reduce cash needed while equipment still has a replacement cost. Do not invent a total before inventory/prices are checked. A bench BOM does not establish the cost of compliant mains installation or a real apartment deployment.

The pitch can establish grid relevance through peak advisories and measured participating-load response. It cannot demonstrate prevented grid outages, transformer protection, bill savings, reduced emissions or city-scale MW benefits without additional evidence. SDG 7 and 9 are relevance mappings, not measured impact.

## 12. Five-minute demonstration sequence

Show the historical dataset source and a saved forecast, approve one peak advisory, open the apartment page, accept one proposal, claim done while leaving the pump off, display observation mismatch and revised proposal, perform the revised action and show physical readings. Finish with the matched comparison and actual limitations. Keep an offline saved replay and recorded evidence if the live bench fails. Label any recording or fallback.

## 13. Copy-paste starts

### Rohan's Claude Code

You are implementing NivaWatt in oxydevelopers/nivawatt on feature/rohan-core. Read AGENTS.md, NIVAWATT_BUILD_NOW.md, CONTRACT.md and COORDINATION_ROHAN.md. Inspect current source/Git status before editing. Restore the forecasting-to-advisory layer described in the build-now plan. Keep one local service and preserve any working stack. First publish the agreed JSON fixture and additive contract revision, then deliver one saved forecast/advisory and one apartment acceptance/claim/observation/replanning loop. Use synthetic inputs only with explicit provenance while real-data validation remains incomplete. Do not block Sonia on model sophistication or hardware. Own forecasting/core/simulation/firmware/shared integration paths only. Test meaningful failures and document actual commands/results. No paid services, secrets, unsupported claims, automatic mains control, force-push or automatic main merge. Implement the first gate now rather than generating another plan.

### Sonia's Claude Code

You own NivaWatt's web/ and tests/ui/ on feature/sonia-ui. Read AGENTS.md, NIVAWATT_BUILD_NOW.md, CONTRACT.md and COORDINATION_SONIA.md. Inspect existing code. Build the operator and apartment-manager views against one agreed visibly synthetic fixture and one API client. Add forecast provenance/advisory approval, requirements/proposal acceptance, done claims and separate observed-execution status. Integrate the real API at the first handoff. Read Rohan's committed contract revision and record acknowledgement or exact field problems. Never invent metrics or equate done with measured completion. Keep source/time/run/revision labels consistent. Record actual phone checks and open your task PR. No backend/shared-contract edits or automatic main merge. Implement the first connected screens now.

### Third teammate's Gemini

We are building NivaWatt: regional peak-demand forecasting, an operator-approved advisory, and apartment pump/EV-emulator scheduling with measured execution feedback. My role is hardware inventory, calibration, independent testing and evidence. Rohan owns core/firmware review and Sonia owns the interfaces. I have basic Gemini chat, so do not assume you can operate my terminal, repository or devices. Start by helping me make a table of the exact college-provided components, ratings and missing items. Use a low-voltage bench and have the actual wiring reviewed by the lab/Rohan. Then prepare volume/flow/electrical calibration records and manual test steps for false done, delayed action, missing telemetry and infeasible requirements. Record observed values and PASS/FAIL/NOT RUN honestly. Do not invent costs, experimental results, AI accuracy or real BESCOM access. Help me understand the whole system and prepare concise judge answers after evidence exists.

## 14. Source references

- KPTCL-derived archive and licensing: https://github.com/Vonter/kptcl-load-curve
- Dataset scope/schema/caveats: https://github.com/Vonter/kptcl-load-curve/blob/main/DATA.md
- Existing human-in-the-loop control background, not a novelty clearance: https://arxiv.org/abs/1809.02770
- UN goals: https://sdgs.un.org/goals

This revision accompanies the reconciled README, AGENTS, role prompts and proposed contract v0.2. Read the current branch and coordination acknowledgements; publication of these documents does not establish implemented endpoints or Sonia's acceptance.
