import json
from pathlib import Path

from app import config


def test_control_rejected_with_no_data_yet(client, api_key_headers):
    resp = client.post(
        "/api/v1/control/ventilation",
        headers=api_key_headers,
        json={"fan_pct": 70},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert body["reason"] == "no_data"


def test_control_accepted_within_range(client, api_key_headers):
    client.post(
        "/api/v1/ingest",
        headers=api_key_headers,
        json={"temp_c": 24.0, "fan_pct": 40, "heater_on": False, "seq": 1},
    )
    resp = client.post(
        "/api/v1/control/ventilation",
        headers=api_key_headers,
        json={"fan_pct": 80},
    )
    body = resp.json()
    assert body["allowed"] is True
    assert body["fan_pct"] == 80


def test_control_rejects_out_of_range_high(client, api_key_headers):
    resp = client.post(
        "/api/v1/control/ventilation",
        headers=api_key_headers,
        json={"fan_pct": 150},
    )
    assert resp.status_code == 422


def test_control_rejects_out_of_range_low(client, api_key_headers):
    resp = client.post(
        "/api/v1/control/ventilation",
        headers=api_key_headers,
        json={"fan_pct": -20},
    )
    assert resp.status_code == 422


def test_control_requires_api_key(client):
    resp = client.post("/api/v1/control/ventilation", json={"fan_pct": 50})
    assert resp.status_code == 401


def test_desired_reflects_last_accepted_command(client, api_key_headers):
    client.post(
        "/api/v1/ingest",
        headers=api_key_headers,
        json={"temp_c": 24.0, "fan_pct": 40, "heater_on": False, "seq": 1},
    )
    client.post(
        "/api/v1/control/ventilation",
        headers=api_key_headers,
        json={"fan_pct": 65},
    )
    resp = client.get("/api/v1/control/desired", headers=api_key_headers)
    assert resp.json()["fan_pct"] == 65


def test_every_control_call_is_audited(client, api_key_headers):
    client.post(
        "/api/v1/ingest",
        headers=api_key_headers,
        json={"temp_c": 24.0, "fan_pct": 40, "heater_on": False, "seq": 1},
    )
    client.post(
        "/api/v1/control/ventilation",
        headers=api_key_headers,
        json={"fan_pct": 55, "actor": "test-operator", "role": "operator"},
    )

    audit_lines = Path(config.AUDIT_LOG_PATH).read_text(encoding="utf-8").strip().splitlines()
    assert len(audit_lines) == 1

    entry = json.loads(audit_lines[0])
    assert entry["tool"] == "set_ventilation_level"
    assert entry["actor"] == "test-operator"
    assert entry["allowed"] is True
    assert entry["resulting_state"]["fan_pct"] == 55
