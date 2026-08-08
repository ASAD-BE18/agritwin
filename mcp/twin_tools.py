"""
Shared async tool functions (get_current_conditions, get_historical_range, predict_crop_stress,
set_ventilation_level, get_system_health) — imported by both mcp_server.py and chat_app.py.

Heater control is intentionally NOT exposed here as a settable tool — read-only in get_current_conditions.
Owner: Asad.
"""
