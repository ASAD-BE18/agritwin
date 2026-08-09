"""
Temporary dev helper — NOT the real mock data generator (that's Step 0.7,
still Tayyaba's to build: a realistic 30-min profile with a heater ramp,
cooldown, and one >30C spike, replayed from a CSV).

This just posts a slowly drifting fake temperature to /ingest every 2 seconds,
so anyone running the backend locally has *something* changing to point
Unity/the chat UI at today, without waiting on the polished dataset.

Usage (from backend/, with the venv active and the API running separately):
    python scripts/seed_mock_readings.py
"""

import math
import os
import time

import httpx

BASE_URL = os.environ.get("AGRITWIN_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("AGRITWIN_API_KEY", "dev-only-key-change-me")

seq = 0
start = time.monotonic()

print(f"Seeding {BASE_URL}/api/v1/ingest every 2s — Ctrl+C to stop")

while True:
    elapsed = time.monotonic() - start
    temp_c = 23.0 + 4.0 * math.sin(elapsed / 30.0)  # slow drift between ~19-27C
    fan_pct = 50 if temp_c < 25 else 80
    heater_on = temp_c < 21

    resp = httpx.post(
        f"{BASE_URL}/api/v1/ingest",
        headers={"X-API-Key": API_KEY},
        json={
            "temp_c": round(temp_c, 2),
            "fan_pct": fan_pct,
            "heater_on": heater_on,
            "seq": seq,
            "source": "mock",
        },
        timeout=5.0,
    )
    print(f"seq={seq} temp_c={temp_c:.1f} -> {resp.status_code}")
    seq += 1
    time.sleep(2)
