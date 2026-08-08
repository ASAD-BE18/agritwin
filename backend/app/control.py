"""
Ventilation control: range rejection, staleness check, JSONL audit trail.

This is the backend-layer safety check only (§1.4 layer 2 of 3). RBAC (who's allowed
to call this at all) is enforced one layer up, at the MCP server (Step 0.6) — this
module just guarantees that whatever reaches the Arduino is valid and auditable.
Heater control is deliberately not here: heater is read-only everywhere above the
firmware.

Out-of-range fan_pct is rejected (422), not silently clamped — VentilationCommand's
`Field(ge=0, le=100)` enforces that before this function is ever called, matching
§1.4's "reject commands outside 0-100" rather than §3's looser "clamp" wording.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.models import VentilationCommand, VentilationResponse
from app.store import ReadingStore


def apply_ventilation_command(cmd: VentilationCommand, store: ReadingStore) -> VentilationResponse:
    fan_pct = cmd.fan_pct  # already validated in-range (0-100) by VentilationCommand

    age = store.data_age_s()
    stale = age is not None and age >= config.STALE_AFTER_S
    no_data = age is None

    if stale or no_data:
        response = VentilationResponse(
            fan_pct=store.desired_fan_pct(),
            allowed=False,
            reason="no_data" if no_data else "stale_reading",
        )
        _audit(cmd, response)
        return response

    store.set_desired_fan_pct(fan_pct)
    response = VentilationResponse(fan_pct=fan_pct, allowed=True)
    _audit(cmd, response)
    return response


def _audit(cmd: VentilationCommand, response: VentilationResponse) -> None:
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": cmd.actor,
        "role": cmd.role,
        "tool": "set_ventilation_level",
        "args": {"fan_pct": cmd.fan_pct},
        "allowed": response.allowed,
        "resulting_state": {"fan_pct": response.fan_pct},
    }
    with Path(config.AUDIT_LOG_PATH).open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
