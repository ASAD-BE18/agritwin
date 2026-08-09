## What changed
Built the backend core: all 7 API endpoints from `docs/API.md` (state, history, health,
ingest, stress, and ventilation control), plus the crop-stress scorer that flags when
conditions are risky for the crop.

## Why it matters
This is the foundation everything else plugs into — Unity polls it for the digital twin,
and the chat AI will call it (via the MCP server, coming next) to answer questions with
real numbers instead of guessing. It also enforces the safety rule from the plan: bad fan
commands (out of 0–100 range, or sent when sensor data is stale) get rejected, not silently
adjusted, and every command is logged to an audit trail.
