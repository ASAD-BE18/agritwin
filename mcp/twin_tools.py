"""
Shared async tool functions (get_current_conditions, get_historical_range,
predict_crop_stress, set_ventilation_level, get_system_health) — imported by both
mcp_server.py and, later, chat_app.py. Pure HTTP client over the backend's frozen
contract (docs/API.md); no business logic lives here beyond shaping/merging responses
for a tool-calling LLM.

Heater control is intentionally NOT exposed here as a settable tool — read-only in
get_current_conditions.

Every function raises on a backend/network failure (httpx's raise_for_status) rather
than swallowing it into a fake result — per the grounding system prompt (Implementation
Plan Step 0.8): "if a tool fails, say so — do not estimate." The MCP server surfaces
that as a tool error to the LLM instead of a fabricated answer.

Owner: Asad.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import config
import httpx

# Overridable by tests to inject an httpx.MockTransport instead of hitting a real
# backend over the network.
_TRANSPORT: httpx.BaseTransport | None = None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.BACKEND_URL, timeout=config.REQUEST_TIMEOUT_S, transport=_TRANSPORT
    )


def _age_from_ts(ts: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()


async def get_current_conditions() -> dict:
    """GET /api/v1/state — current temp/fan/heater snapshot. Already carries
    `data_age_s` and `mode`."""
    async with _client() as client:
        resp = await client.get("/api/v1/state")
        resp.raise_for_status()
    return resp.json()


async def get_historical_range(
    start: str | None = None, end: str | None = None, max_points: int = 500
) -> dict:
    """GET /api/v1/history — downsampled readings + {min,max,avg,count} summary for a
    time window. `start`/`end` are ISO-8601 timestamps; omit either to leave that side
    of the window open. Adds `data_age_s` computed from the newest returned reading, so
    a caller can tell a fresh window from a query that only turned up old data."""
    params: dict[str, str | int] = {"max_points": max_points}
    if start is not None:
        params["start"] = start
    if end is not None:
        params["end"] = end

    async with _client() as client:
        resp = await client.get("/api/v1/history", params=params)
        resp.raise_for_status()

    data = resp.json()
    readings = data.get("readings") or []
    data["data_age_s"] = _age_from_ts(readings[-1]["ts"]) if readings else None
    return data


async def predict_crop_stress() -> dict:
    """GET /api/v1/stress — {risk_score, risk_label, factors[]}. Merges in
    `data_age_s` from /state so a caller can flag a stale score rather than presenting
    it as current."""
    async with _client() as client:
        stress_resp = await client.get("/api/v1/stress")
        stress_resp.raise_for_status()
        state_resp = await client.get("/api/v1/state")
        state_resp.raise_for_status()

    result = stress_resp.json()
    result["data_age_s"] = state_resp.json().get("data_age_s")
    return result


async def get_system_health() -> dict:
    """GET /api/v1/health — {sensor_online, last_reading_age_s, buffer_size, mode,
    uptime_s}."""
    async with _client() as client:
        resp = await client.get("/api/v1/health")
        resp.raise_for_status()
    return resp.json()


async def set_ventilation_level(fan_pct: int, actor: str = "mcp-server") -> dict:
    """POST /api/v1/control/ventilation — the only settable actuator exposed at this
    layer (heater control is deliberately absent). RBAC-gated on this server instance's
    configured role (`config.ROLE`); every call is audited locally whether allowed or
    denied, independent of the backend's own audit trail (§1.4 layer 2), since a
    denial here never reaches the backend at all."""
    role = config.ROLE
    if role != "operator":
        result = {"fan_pct": None, "allowed": False, "reason": f"rbac_denied_role_{role}"}
        _audit(actor=actor, role=role, fan_pct=fan_pct, result=result)
        return result

    async with _client() as client:
        resp = await client.post(
            "/api/v1/control/ventilation",
            json={"fan_pct": fan_pct, "actor": actor, "role": role},
            headers={"X-API-Key": config.BACKEND_API_KEY},
        )
        resp.raise_for_status()

    result = resp.json()
    _audit(actor=actor, role=role, fan_pct=fan_pct, result=result)
    return result


def _audit(actor: str, role: str, fan_pct: int, result: dict) -> None:
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "role": role,
        "tool": "set_ventilation_level",
        "args": {"fan_pct": fan_pct},
        "allowed": result.get("allowed", False),
        "resulting_state": {"fan_pct": result.get("fan_pct")},
    }
    with Path(config.AUDIT_LOG_PATH).open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
