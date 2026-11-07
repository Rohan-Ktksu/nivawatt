# Sonia: Claude Code interface prompt v0.2

You own web/, tests/ui/ and COORDINATION_SONIA.md in oxydevelopers/nivawatt on feature/sonia-ui. Read README.md, AGENTS.md, NIVAWATT_BUILD_NOW.md, CONTRACT.md and the four example JSON files. Inspect existing source/status. Rohan owns forecasting/core/firmware/shared contract.

## Work order

1. Start both pages immediately against visibly synthetic fixtures. Keep one API client. For a fresh app use plain JavaScript/CSS under Rohan's same-origin service. Preserve a working inherited frontend stack instead of rewriting it.
2. Operator page: show regional data source/scope, forecast time and hourly peak windows, then an explicit approve-advisory action. Show participating apartment summaries and stale/unknown evidence. A demonstration operator is not a live BESCOM integration.
3. Apartment manager page: show advisory hours, tank reserve, requested/remaining charging energy/deadline, participating-load allowance, next recommended action/reason, current commitment and pending proposal. Keep accept/decline and done-claim controls distinct.
4. Integrate real backend requests at the first API checkpoint. Read Rohan's committed v0.2 contract and coordination note once at handoff. Record ACK or exact field incompatibilities; do not edit the backend or canonical contract. No continuous fetch polling.
5. Handle loading, empty/error/unauthorized states, stale/expired proposal conflicts, exact run/revision/option and idempotency IDs. Refresh authoritative state; never show a tap as measured completion.
6. Complete forecast/advisory -> acceptance -> contradictory observation -> revised proposal -> observed outcome before comparison polish.
7. Add comparison/timeline only from computed backend results. One run/scenario/policy selection controls all charts and headings. Distinguish hardware W/Wh, scaled model kW/kWh and synthetic/simulated outcomes.
8. Test narrow-screen readability and actual phone access with Rohan. Record actual checks/screenshots and open a focused PR without automatic main merge.

No browser-calculated final schedules/metrics, constant winning percentages, invented forecast accuracy, billing/recharge/chatbot pages, paid assets or copied BESCOM branding. Unknown is not zero. Electrical delivery is not battery SoC. A regional forecast does not establish local transformer capacity. No-data screens must preserve that distinction.

The API/fixtures describe targets, not implemented features. Record current branch/commit, contract response, working API routes and remaining gaps in COORDINATION_SONIA.md. Implement the first connected screens now.
