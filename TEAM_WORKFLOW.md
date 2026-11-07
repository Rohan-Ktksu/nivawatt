# Three-person accelerated workflow

## Target and allocation

Workload is deliberately unequal: roughly Rohan 50%, Sonia 35%, teammate 3 15% of software work. Teammate 3 also owns practical bench preparation and independent testing; that work is critical. These percentages are allocation guidance, not measured effort.

Aim for a usable software demo in 6–8 focused hours. Hardware integration follows as components and calibration allow. Do not wait for all hardware before connecting the phone to real backend state.

## First 20 minutes: shared foundation

Rohan: inspect the new repository and any accessible OutageReady source, confirm own Git identity, adopt CONTRACT.md v0.1, and commit the smallest runnable skeleton. Reuse functioning Python logic where appropriate rather than rewriting everything. Pick one Python server and one local SQLite file. With no inherited stack, use FastAPI and plain HTML/JavaScript served from web/ by the same server. Avoid introducing a second frontend dev server, Node build or database service solely for this sprint. If a working existing stack is reused, retain it and document actual run commands.

Sonia: clone, branch, read the example JSON and build the Manager page layout against that fixture. Create one API-client module immediately so replacing fixture loading with live requests is one change. Fixtures must be visibly labelled MOCK and never be used as final performance results.

Teammate 3: clone or download the repository, open GEMINI.md in their existing Gemini chat, list actual components and prepare validation notes. A terminal is not required for inventory/testing. Do not purchase parts or assume substitutes are equivalent.

## Work and handoff schedule

| Elapsed target | Rohan | Sonia | Teammate 3 | Gate |
|---|---|---|---|---|
| 0–20 min | Source inspection, skeleton, schema | Mock-based manager layout | Inventory, laptop/phone connectivity check | Contract version and ownership recorded |
| 20–90 min | Single-apartment plant, scheduler, proposal/claim API, SQLite | Manager acceptance/done states; operator event form | Record pump/load ratings and measurement plan; prepare scenario steps | Phone can display a proposal from the actual API |
| 90–150 min | Revision/expiry/stale-version guards; basic core tests | Wire real API, pending/expired/error views | Run false-done and stale-click checks, report exact steps | Accept -> done claim -> telemetry mismatch -> revision works in simulation |
| 150–240 min | Telemetry adapter + firmware review if bench ready; acknowledgement/measured policy pair | Raw-vs-model labels, execution timeline, readiness views | Assemble/calibrate with competent lab support, record actual readings | Physical readings reach backend OR simulation-only limitation explicitly recorded |
| 240–360 min | Add simple-cap/open-loop comparisons; repeated scenario runner; second software apartment if core stable | Comparison view from actual report JSON; responsive polish | Repeat checklist on phone, capture genuine evidence and limits | Matched comparison results export; no hard-coded wins |
| 360–480 min | Integration fixes, reproducible startup, known-good commit | Final UI fixes, offline demo | Judge rehearsal and short presentation | Stable demonstration and documented fallback |

These are checkpoints, not promises that unmeasured hardware or a solver will work by a fixed time. If integration fails, stop new features and repair the first loop.

## Scope ladder

P0: one apartment, one pump, one EV-emulator load, one feasible proposal, explicit acceptance/claim, timestamped observations, deviation + revised proposal, tank/EV shortfall display, local phone UI, persisted event history.

P1 after P0: acknowledgement-vs-measured comparison, simple-cap/open-loop baselines, additional option when feasible, one second simulated apartment, operator summary and CSV/JSON export.

P2 only after stable P1: extra disturbances and polish. Drop BESS, model training, WhatsApp integration, distributed optimization, utility API work, sophisticated accounts and decorative reports from this sprint.

Do not force MILP adoption if it blocks integration. A bounded look-ahead scheduler or clearly labelled deterministic heuristic is acceptable. It must respect hard constraints, show infeasibility and be compared to a simpler rule. If functioning optimization exists already, reuse it and test it. No guaranteed optimality or runtime claim.

## Git workflow: each computer

After cloning the real repository, use your own branch:

```powershell
# Rohan only
git switch -c feature/rohan-core
# Sonia only
git switch -c feature/sonia-ui
# Teammate 3 only, if using Git locally
git switch -c feature/hardware-validation
```

Run only the command for your role. If that branch already exists, switch to it rather than creating another.

Before a handoff:

```powershell
git status --short
git diff --check
# Add explicit owned paths, not an unreviewed git add .
git add <your-owned-paths>
git commit -m "Describe the completed change"
git push -u origin <your-branch>
```

Open a PR against main with what works, exact checks run and remaining limitations. A draft PR is useful for early visibility, not evidence of completion. Never commit .env, credentials, runtime databases, Python environments or node_modules. Rohan establishes .gitignore before implementation commits.

At a natural boundary, read a peer's committed work without replacing their files:

```powershell
git fetch origin
git show origin/feature/rohan-core:CONTRACT.md
git show origin/feature/rohan-core:COORDINATION_ROHAN.md
git show origin/feature/sonia-ui:COORDINATION_SONIA.md
```

Rohan reviews/merges the smallest working core, then UI, then validation changes. After those merges, teammates bring main into their clean feature branches with git fetch origin and git merge origin/main. Resolve conflicts only in owned files; shared-contract conflicts go to Rohan. Never force-push another person's work. Do not cherry-pick an entire peer directory over current code.

If teammate 3 uses only GitHub's web editor, edit files under hardware/, validation/ or presentation/, create a new branch and PR, and record the PR link. Gemini provides suggestions; the human commits them. No GitHub identity sharing is needed.

## Coordination notes

Each person updates their own COORDINATION file with: branch + commit, working output, exact checks and results, blockers, requested peer action and next task. Do this at the first real API integration, before PR and after a failure affecting peers. No hourly status bureaucracy or continuous polling.

## Physical/demo fallback

- If hardware is unavailable: finish an interactive, explicitly simulated workflow; report hardware integration as incomplete.
- If branch attribution is ambiguous: show aggregate measured compliance and UNKNOWN branch execution; do not credit per-EV delivery from ambiguous data.
- If Wi-Fi fails: use the laptop interface/USB telemetry where implemented. Keep local files and startup instructions available; no venue internet dependency.
- If a proposed change is not accepted or acted on: preserve applicable commitment history, show actual state and unresolved service risks. Do not claim the schedule physically controls demand.
