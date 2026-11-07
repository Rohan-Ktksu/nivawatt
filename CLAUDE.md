# NivaWatt Claude Code entry point

Read AGENTS.md, NIVAWATT_BUILD_NOW.md, TEAM_WORKFLOW.md and CONTRACT.md first. Revision v0.2 restores the regional-demand forecasting and operator-advisory layer.

Rohan: execute PROMPT_ROHAN.md on feature/rohan-core.
Sonia: execute PROMPT_SONIA.md on feature/sonia-ui.
If the human role is unclear, clarify before editing role-owned files.

The third teammate uses GEMINI.md manually. Do not start remote assistants, background model bridges or multiple agents automatically. Push useful checkpoints; peers consume committed files after fetching at natural handoffs.

First produce one saved forecast/advisory and the apartment acceptance, claim, observation and revision loop. Use a seasonal baseline, then an actually fitted small local regression if justified. Rules scheduling is labelled rules. No application LLM API, paid services, model downloads or automatic main merge. Source and actual coordination evidence take precedence over old project claims.
