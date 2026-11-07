# AdaptiveFlow — start here

**Adaptive Pump and EV Scheduling for Apartment Peak Demand Reduction**

This repository currently contains a planning and coordination pack. It does not yet contain a verified application, hardware integration, or measured performance results. Prepared 7 November 2026 for a three-person sprint.

## Team and reading order

| Person | Available assistant | Responsibility | First file |
|---|---|---|---|
| Rohan | Claude Code terminal; Codex support | Core logic, API, persistence, simulation, firmware review, integration | [PROMPT_ROHAN.md](PROMPT_ROHAN.md) |
| Sonia | Claude Code terminal | Manager phone interface, operator view, API client, UI checks | [PROMPT_SONIA.md](PROMPT_SONIA.md) |
| Teammate 3 (name not supplied) | Basic Gemini chat | Hardware inventory and measurements, scenario preparation, independent QA, presentation evidence | [GEMINI.md](GEMINI.md) |

Everyone reads [AGENTS.md](AGENTS.md), [TEAM_WORKFLOW.md](TEAM_WORKFLOW.md), and [CONTRACT.md](CONTRACT.md). Run the acceptance checks in [TEST_AND_DEMO.md](TEST_AND_DEMO.md).

**Target:** a usable local software demonstration in one focused 6–8-hour working session, with integration beginning within two hours. This is a target, not a completion guarantee. Physical assembly/calibration can continue afterward; never call simulated measurements hardware results.

## First actions

1. Rohan confirms everyone can clone this repository, freezes contract v0.1 and publishes the initial core skeleton. The current machine's existing CampusResolve repository is unrelated; do not reuse its backend or change its remote.
2. Sonia starts immediately against STATE_EXAMPLE.json and the contract. She does not wait for the solver, rewrite the API, or calculate final metrics in the browser.
3. Teammate 3 inventories actual lab components, prepares the scenarios and follows the manual checklist. They do not need terminal-agent access to be useful.
4. Integrate one proposal -> accept -> claimed done -> missed physical action -> observed deviation -> revised proposal -> measured outcome loop first.
5. Add comparisons and the second simulated apartment only after that loop works.

## Product boundary

This is advisory apartment demand response. Submeters support execution feedback. FDIA auditing, battery dispatch, new ML training, WhatsApp APIs, transformer protection and paid cloud services are outside the initial sprint. The BESCOM/operator interface is a **simulated coordination view**, with no claimed utility connection.

The existing project at https://github.com/Rohan-Ktksu/OutageReady-FlexProof may provide reusable source if a teammate has authorized access. Inspect it before importing selected modules and preserve provenance. Its current features/tests have not been verified for this new repository. Do not copy its entire Git history, configuration, or old assistant instructions blindly.

## Bootstrap commands

Each person runs these on their own computer, using their own identity:

```powershell
git clone https://github.com/oxydevelopers/adaptiveflow.git
cd adaptiveflow
git config user.name
git config user.email
git status --short
```

Do not share passwords/tokens or commit .env files. If GitHub authentication is needed, the human signs in on that computer. A coding-assistant subscription does not provide GitHub authentication or unlimited application inference.

Choose your branch from TEAM_WORKFLOW.md. After core exists, the intended startup is a single local Python service serving the API and web pages; Rohan must replace planned instructions with commands he actually tested. No application startup command is claimed to work in this planning-only commit.

## Status discipline

Update only your own COORDINATION_*.md after a useful handoff: commit SHA, what works, commands actually run, failures and next task. Files become visible to peers only after push/fetch. No background model-to-model messaging, paid runners or polling bots. Each human must start and resume their own assistant.
