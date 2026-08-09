"""
MCP server exposing twin_tools.py over stdio for Claude Desktop / Claude Code. Thin
wrappers only — no business logic lives here, see docs/Implementation_Plan.md Step 0.6.

Uses `mcp.server.mcpserver.MCPServer` (the installed SDK's high-level decorator API,
`pip install "mcp[cli]"`, v2.x). Older docs/tutorials referencing
`mcp.server.fastmcp.FastMCP` describe a pre-v2 layout that no longer exists in this
SDK version — `MCPServer` is its direct successor (same `@tool()` decorator, same
`.run()` defaulting to stdio).

Run this as a script (`python mcp_server.py` from this directory, or with an absolute
path from a Claude Desktop config) — never as `python -m mcp.mcp_server` and never via
`from mcp import twin_tools`. This directory is named `mcp`, the same as the
third-party SDK imported above; the bare `import twin_tools` / `import config` below
are sibling-file imports that only resolve correctly because running as a plain script
puts *this directory* at sys.path[0], not the repo root. Do NOT add an `__init__.py`
here — that would make this directory a real importable package named `mcp` and risk
shadowing the SDK for anything that puts the repo root on sys.path.

Owner: Asad.
"""

import twin_tools
from mcp.server.mcpserver import MCPServer

server = MCPServer("agritwin")


@server.tool()
async def get_current_conditions() -> dict:
    """Call this whenever the user asks about the current temperature, fan speed, or
    heater state. Never state a current value without calling this first. Always check
    `data_age_s` in the result before answering — if it's stale (more than a few
    seconds old), say so rather than presenting the number as current."""
    return await twin_tools.get_current_conditions()


@server.tool()
async def get_historical_range(
    start: str | None = None, end: str | None = None, max_points: int = 500
) -> dict:
    """Call this for any question about past temperature (e.g. "what was the peak in
    the last hour", "was it colder this morning"). `start`/`end` are ISO-8601
    timestamps (e.g. "2026-08-09T11:00:00Z"); omit either to leave that side of the
    window open. Use the returned `summary` block (min/max/avg/count) for aggregate
    questions — don't compute your own min/max/avg over `readings`, they're
    downsampled and may not include every raw point."""
    return await twin_tools.get_historical_range(start=start, end=end, max_points=max_points)


@server.tool()
async def predict_crop_stress() -> dict:
    """Call this whenever the user asks if conditions are safe or stressful for the
    crop, or asks for a recommendation (e.g. "should I increase ventilation"). Returns
    `risk_score` (0-100), `risk_label` (ok/caution/stress), and `factors` — quote
    `factors` directly rather than restating the reasoning in your own words."""
    return await twin_tools.predict_crop_stress()


@server.tool()
async def get_system_health() -> dict:
    """Call this whenever the user asks if the sensor or system is working, or before
    trusting a reading that looks suspicious. Reports `sensor_online` and
    `last_reading_age_s` — a sensor can be reported online yet still a few seconds
    stale, so check the age field rather than only the boolean."""
    return await twin_tools.get_system_health()


@server.tool()
async def set_ventilation_level(fan_pct: int) -> dict:
    """Set the fan speed, 0-100. This is the ONLY actuator you can control — heater
    control is deliberately not exposed as a tool; it is read-only via
    get_current_conditions and enforced independently by a firmware thermal cutoff
    that no software layer, including you, can override. Every call is RBAC-gated and
    audited server-side regardless of outcome. If the result's `allowed` field is
    false, tell the user why (see `reason`) — do not claim the change was made."""
    return await twin_tools.set_ventilation_level(fan_pct=fan_pct)


if __name__ == "__main__":
    server.run()
