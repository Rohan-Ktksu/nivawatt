# Smart-meter evidence and execution update

Planning addendum, 7 November 2026. Read with NIVAWATT_BUILD_NOW.md. This changes integration assumptions and evaluation scope, not existing implemented API behaviour.

## Evidence boundary

CESC Mysore's published app listing confirms consumption viewing, account information, payment history and complaints. It does not establish public interval-data API/export access, appliance identification, or pump/EV scheduling with measured-response verification. The government smart-meter page could not be retrieved during review. CESC Mysore and BESCOM are different utilities. Absence of confirmation in reviewed sources is an evidence gap, not proof a capability is absent anywhere and not patent/novelty clearance.

Sources reviewed:
- https://play.google.com/store/apps/details?hl=en_US&id=consumerapp.bsmart.bcits.DEMOCESCcis
- https://cescmysore.karnataka.gov.in/235/smart-meters/en (not retrieved)
- https://lizahomes.in/blog/bescom-connection-smart-meter-guide-bengaluru-2026/ (secondary guide; specific accuracy, meter-model, AI and rollout claims not independently verified)

The OpenCity energy-requirement resource's indexed schema is an FY2015-16 comparison, not hourly demand. Monthly bills do not establish pump/EV execution or time-of-day demand. Do not publish private bills, account IDs, addresses or unredacted screenshots to this public repository.

## Immediate decisions

1. Continue the existing forecast/advisory/apartment loop. Do not rewrite the core or wait for utility access. Preserve current working source and startup evidence.
2. Keep a regional historical replay for forecasting, accurately labelled Karnataka state demand. Keep independently measured pump and charging-emulator branches plus tank level as the hardware target.
3. Treat utility smart-meter access as an optional future input. Do not implement an undocumented endpoint, scrape authenticated customer sessions, bypass access controls or claim a live connection.
4. Create a short capability/inventory record: connection and meter association, utility, device model, documented export format, interval, capture time, received time, latency, units, quality, permission/access basis and scope (aggregate/branch). Unknown fields remain unknown. A flat's sanctioned load is not automatically the common-pump allowance.
5. Separate regional demand, connection aggregate readings and branch readings. An aggregate reading cannot silently replace branch execution evidence. Pump power alone cannot prove water delivery. Charger electrical delivery cannot establish battery SoC.
6. Retain the two-mode design: independent local branch sensing now; an import adapter for a genuinely available, authorized smart-meter export later. Do not expand the sprint to a production AMI integration or load-disaggregation model.

## Small implementation tasks

Rohan: document adapter capability expectations in your owned notes. Reuse existing provenance/quality structures. If actual authorized interval data is obtained, propose the smallest additive contract change with Sonia before implementing it. For now identify source, scope and age from current fields and test stale/aggregate inputs without new utility APIs.

Sonia: display measurement source, participating scope and freshness using agreed existing fields. For a future utility source show Not connected until verified. Distinguish aggregate consumption visibility from verified pump/EV execution. Do not build a large integration/settings portal or change the canonical contract yourself.

Third teammate: inventory the physical meters/branches and record measured calibration evidence. Maintain a source/claim register with Supported, Unverified and Not tested states. Do not interpret a missing feature in an app description as proof of industry-wide absence.

## Additional evaluation cases

A. Aggregate-only observation: combined power can be consistent with multiple branch states. Output ambiguous/unknown attribution; do not credit an individual EV with exact energy.
B. Fresh branch observations: establish only the execution/outcome supported by calibration and tank evidence.
C. Delayed/stale/missing readings: retain capture/receive times and explicit gaps; never interpret missing as zero or label late data live.
D. Pump draws power but water does not rise: distinguish electrical operation from water delivery.

Use matched scenarios and the same control authority. Compare aggregate-only and branch-observed variants as an observability experiment, with assumptions stated. This is not a claim that a particular BESCOM meter has a measured delay or lacks load-disaggregation capability. Existing acknowledgement-versus-measurement comparisons still apply. Measure additional sensor cost alongside service outcomes and response delay; do not assume branch sensing always wins.

## Pitch and claim wording

Use: Reviewed sources confirm consumption monitoring but do not establish the complete flexible-load coordination workflow. Our prototype tests forecast-informed scheduling with independently measured execution and service constraints.

Avoid: BESCOM does not do demand response; smart meters cannot detect appliances; our system is first in India; meters guarantee real-time API access; energy shifting guarantees bill or carbon savings.

Implementation is complete only when the team records actual code, checks and evidence. This addendum itself supplies no new hardware or experimental results.
