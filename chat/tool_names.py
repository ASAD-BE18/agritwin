"""
Reference copy of the 5 real MCP tool names, per docs/Implementation_Plan.md
section 2/Step 0.6 and the team brief's 5 test questions.

Once mcp/mcp_server.py exists, the REAL tool list comes dynamically from
`await mcp.list_tools()` (see chat_app.py's call_agent_real) — this file only
matters for the stub agent and the test suite's expected-tool assertions.
If team changes a tool's name, update it here AND nowhere else in this repo.
"""

GET_CURRENT_CONDITIONS = "get_current_conditions"
GET_HISTORICAL_RANGE = "get_historical_range"
PREDICT_CROP_STRESS = "predict_crop_stress"
SET_VENTILATION_LEVEL = "set_ventilation_level"
GET_SYSTEM_HEALTH = "get_system_health"

ALL_TOOL_NAMES = [
    GET_CURRENT_CONDITIONS,
    GET_HISTORICAL_RANGE,
    PREDICT_CROP_STRESS,
    SET_VENTILATION_LEVEL,
    GET_SYSTEM_HEALTH,
]

# Grounding system prompt — verbatim from Implementation_Plan.md Step 0.8.
# The real agent (call_agent_real) uses this exact prompt; keep it in sync
# if the team refines it.
GROUNDING_SYSTEM_PROMPT = (
    "You answer questions about a live greenhouse. Never state a temperature, "
    "timestamp, fan speed, or risk assessment that did not come from a tool "
    "result in this conversation. If data_age_s exceeds 10, say the data is "
    "stale before answering. If a tool fails, say so — do not estimate."
)
