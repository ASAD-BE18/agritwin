def _ingest_n(client, headers, n, start_temp=20.0):
    for i in range(n):
        client.post(
            "/api/v1/ingest",
            headers=headers,
            json={"temp_c": start_temp + i, "fan_pct": 50, "heater_on": False, "seq": i},
        )


def test_history_empty_before_any_data(client):
    resp = client.get("/api/v1/history")
    body = resp.json()
    assert body["readings"] == []
    assert body["summary"] is None


def test_history_summary_is_correct(client, api_key_headers):
    _ingest_n(client, api_key_headers, 5, start_temp=20.0)  # 20,21,22,23,24
    resp = client.get("/api/v1/history")
    summary = resp.json()["summary"]
    assert summary["count"] == 5
    assert summary["min"] == 20.0
    assert summary["max"] == 24.0
    assert summary["avg"] == 22.0


def test_history_downsamples_to_max_points(client, api_key_headers):
    _ingest_n(client, api_key_headers, 50)
    resp = client.get("/api/v1/history", params={"max_points": 5})
    body = resp.json()
    assert len(body["readings"]) == 5
    assert body["summary"]["count"] == 50  # summary reflects the full range, not the sample


def test_history_never_exceeds_max_points_even_when_under_limit(client, api_key_headers):
    _ingest_n(client, api_key_headers, 3)
    resp = client.get("/api/v1/history", params={"max_points": 500})
    assert len(resp.json()["readings"]) == 3
