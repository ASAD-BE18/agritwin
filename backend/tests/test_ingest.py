def test_ingest_requires_api_key(client):
    resp = client.post(
        "/api/v1/ingest",
        json={"temp_c": 24.0, "fan_pct": 50, "heater_on": False, "seq": 1},
    )
    assert resp.status_code == 401


def test_ingest_stores_reading(client, api_key_headers):
    resp = client.post(
        "/api/v1/ingest",
        headers=api_key_headers,
        json={"temp_c": 24.5, "fan_pct": 60, "heater_on": True, "seq": 42, "source": "mock"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["temp_c"] == 24.5
    assert body["fan_pct"] == 60
    assert body["heater_on"] is True
    assert body["seq"] == 42
    assert body["source"] == "mock"
    assert "ts" in body


def test_state_reflects_latest_ingest(client, api_key_headers):
    client.post(
        "/api/v1/ingest",
        headers=api_key_headers,
        json={"temp_c": 22.0, "fan_pct": 10, "heater_on": False, "seq": 1},
    )
    client.post(
        "/api/v1/ingest",
        headers=api_key_headers,
        json={"temp_c": 23.0, "fan_pct": 20, "heater_on": False, "seq": 2},
    )
    resp = client.get("/api/v1/state")
    body = resp.json()
    assert body["temp_c"] == 23.0
    assert body["seq"] == 2
    assert body["sensor_online"] is True


def test_state_before_any_data(client):
    resp = client.get("/api/v1/state")
    body = resp.json()
    assert body["sensor_online"] is False
    assert body["mode"] == "unknown"
    assert body["temp_c"] is None
