"""
Unit tests for twin_tools.py against a fake backend (httpx.MockTransport) — no live
FastAPI process required. Async functions are driven with asyncio.run() rather than
pulling in pytest-asyncio, since that's the only place in this test file that needs it.
"""

import asyncio
import json

import config
import httpx
import twin_tools


def run(coro):
    return asyncio.run(coro)


def mock_backend(handler, monkeypatch):
    monkeypatch.setattr(twin_tools, "_TRANSPORT", httpx.MockTransport(handler))


def test_get_current_conditions_passes_through_state(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/state"
        return httpx.Response(200, json={"temp_c": 24.0, "data_age_s": 0.5, "mode": "mock"})

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.get_current_conditions())
    assert result == {"temp_c": 24.0, "data_age_s": 0.5, "mode": "mock"}


def test_get_historical_range_adds_data_age_from_newest_reading(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/history"
        return httpx.Response(
            200,
            json={
                "readings": [
                    {"ts": "2020-01-01T00:00:00+00:00", "temp_c": 20.0},
                    {"ts": "2020-01-01T00:01:00+00:00", "temp_c": 21.0},
                ],
                "summary": {"min": 20.0, "max": 21.0, "avg": 20.5, "count": 2},
            },
        )

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.get_historical_range())
    assert result["summary"]["count"] == 2
    # newest reading is decades old -- data_age_s should reflect that, not be tiny/zero
    assert result["data_age_s"] > 60 * 60 * 24 * 365


def test_get_historical_range_data_age_is_none_when_empty(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"readings": [], "summary": None})

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.get_historical_range())
    assert result["data_age_s"] is None


def test_get_historical_range_forwards_start_end_params(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"readings": [], "summary": None})

    mock_backend(handler, monkeypatch)
    run(twin_tools.get_historical_range(start="2026-01-01T00:00:00Z", end="2026-01-01T01:00:00Z"))
    assert seen["start"] == "2026-01-01T00:00:00Z"
    assert seen["end"] == "2026-01-01T01:00:00Z"


def test_predict_crop_stress_merges_data_age_from_state(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/stress":
            return httpx.Response(
                200, json={"risk_score": 80, "risk_label": "stress", "factors": ["too hot"]}
            )
        assert request.url.path == "/api/v1/state"
        return httpx.Response(200, json={"data_age_s": 1.5})

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.predict_crop_stress())
    assert result["risk_label"] == "stress"
    assert result["data_age_s"] == 1.5


def test_get_system_health_passes_through(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/health"
        return httpx.Response(200, json={"sensor_online": True, "last_reading_age_s": 0.2})

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.get_system_health())
    assert result["sensor_online"] is True


def test_set_ventilation_level_denies_locally_for_non_operator_role(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROLE", "viewer")
    monkeypatch.setattr(config, "AUDIT_LOG_PATH", str(tmp_path / "mcp_audit.jsonl"))

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("viewer role must never reach the backend")

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.set_ventilation_level(80))

    assert result == {"fan_pct": None, "allowed": False, "reason": "rbac_denied_role_viewer"}

    lines = (tmp_path / "mcp_audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["allowed"] is False
    assert entry["role"] == "viewer"
    assert entry["args"] == {"fan_pct": 80}


def test_set_ventilation_level_forwards_to_backend_for_operator_role(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROLE", "operator")
    monkeypatch.setattr(config, "AUDIT_LOG_PATH", str(tmp_path / "mcp_audit.jsonl"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/control/ventilation"
        assert request.headers["x-api-key"] == config.BACKEND_API_KEY
        body = json.loads(request.content)
        assert body == {"fan_pct": 80, "actor": "mcp-server", "role": "operator"}
        return httpx.Response(200, json={"fan_pct": 80, "allowed": True, "reason": None})

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.set_ventilation_level(80))

    assert result == {"fan_pct": 80, "allowed": True, "reason": None}
    entry = json.loads((tmp_path / "mcp_audit.jsonl").read_text(encoding="utf-8").strip())
    assert entry["allowed"] is True
    assert entry["resulting_state"] == {"fan_pct": 80}


def test_set_ventilation_level_audits_even_when_backend_denies(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROLE", "operator")
    monkeypatch.setattr(config, "AUDIT_LOG_PATH", str(tmp_path / "mcp_audit.jsonl"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"fan_pct": 0, "allowed": False, "reason": "stale_reading"})

    mock_backend(handler, monkeypatch)
    result = run(twin_tools.set_ventilation_level(80))

    assert result["allowed"] is False
    entry = json.loads((tmp_path / "mcp_audit.jsonl").read_text(encoding="utf-8").strip())
    assert entry["allowed"] is False
