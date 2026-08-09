"""
AgriTwin — Mock Data Source
============================
Owned by: Tayyaba (per README: bridge/ is Asad/Tayyaba).

Two jobs, both in this one file:

1. GENERATE a deterministic 30-minute greenhouse profile (ambient drift,
   heater ramp, fan cooldown, one guaranteed >30C spike) and cache it as CSV.
2. REPLAY that CSV by POSTing each row to the backend's real ingest contract:

       POST /api/v1/ingest
       header: X-API-Key: <value from env AGRITWIN_API_KEY>
       body:   Reading-shaped JSON — ts, temp_c, fan_pct, heater_on, seq, source

   matching backend/app/models.py's Reading model exactly, per docs/API.md.

Uses httpx rather than requests — httpx is already the shared HTTP client
across bridge/serial_bridge.py and mcp/twin_tools.py (and is what's declared
in bridge/pyproject.toml), so this keeps the stack to one HTTP library
instead of two.

Run standalone:
    MODE=mock python mock_source.py
Env vars:
    AGRITWIN_BACKEND_URL   default: http://127.0.0.1:8000
    AGRITWIN_API_KEY       required for /ingest — ask Asad for the dev key
    MOCK_SPEEDUP           default: 1 (real-time). Set e.g. 60 to replay the
                            30-minute log in ~30 seconds during development.
"""

import csv
import math
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------
# Determinism knobs — fixed on purpose. Do not seed from wall-clock.
# ---------------------------------------------------------------
SEED = 42
DURATION_MINUTES = 30
INTERVAL_SECONDS = 10  # matches this profile's resolution -> 181 rows
BASE_TEMP_C = 24.0
FIXED_START_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)

HEATER_START_MIN = 8
HEATER_PEAK_MIN = 13
FAN_START_MIN = 13
FAN_END_MIN = 22

CSV_PATH = Path(__file__).parent / "data" / "mock_greenhouse_log.csv"


def generate_profile():
    """Pure function — no I/O, easy to unit test on its own."""
    random.seed(SEED)
    rows = []
    n_steps = int((DURATION_MINUTES * 60) / INTERVAL_SECONDS)

    for i in range(n_steps + 1):
        t_offset_s = i * INTERVAL_SECONDS
        t_min = t_offset_s / 60.0

        drift = 0.6 * math.sin(t_min / 6.0) + random.uniform(-0.15, 0.15)
        temp = BASE_TEMP_C + drift
        heater_on = False
        fan_pct = 0

        if HEATER_START_MIN <= t_min < HEATER_PEAK_MIN:
            heater_on = True
            progress = (t_min - HEATER_START_MIN) / (HEATER_PEAK_MIN - HEATER_START_MIN)
            temp += progress * 7.5
        elif HEATER_PEAK_MIN <= t_min < HEATER_PEAK_MIN + 1:
            heater_on = True
            temp += 7.5 + 0.8  # guarantees the required >30C spike
        elif FAN_START_MIN <= t_min < FAN_END_MIN:
            fan_pct = 80
            progress = (t_min - FAN_START_MIN) / (FAN_END_MIN - FAN_START_MIN)
            temp += max(0.0, 8.0 * (1 - progress)) - 0.3

        temp = round(temp, 2)
        ts = FIXED_START_TS + timedelta(seconds=t_offset_s)

        rows.append({
            "seq": i + 1,
            "ts": ts.isoformat(),
            "temp_c": temp,
            "fan_pct": fan_pct,
            "heater_on": heater_on,
        })

    return rows


def write_csv(rows, path=CSV_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["seq", "ts", "temp_c", "fan_pct", "heater_on"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_or_generate_csv(path=CSV_PATH):
    # NOTE: this only regenerates the CSV if it doesn't already exist on
    # disk. If you change generate_profile()'s logic later (different
    # phase timings, a new spike, etc.), delete the cached file yourself —
    # `bridge/data/mock_greenhouse_log.csv` — or this will keep silently
    # replaying the OLD profile and your change will look like it did
    # nothing. (The file is gitignored, so this is a local-only gotcha,
    # not something that ships stale to anyone else.)
    if path.exists():
        rows = []
        with open(path) as f:
            for r in csv.DictReader(f):
                r["seq"] = int(r["seq"])
                r["temp_c"] = float(r["temp_c"])
                r["fan_pct"] = int(r["fan_pct"])
                r["heater_on"] = r["heater_on"] in ("True", "true", "1")
                rows.append(r)
        return rows
    rows = generate_profile()
    write_csv(rows, path)
    return rows


def replay(backend_url, api_key, speedup=1.0):
    """Replays the CSV in real (or sped-up) time, POSTing each row to
    /api/v1/ingest with the exact Reading shape the backend expects."""
    rows = load_or_generate_csv()
    ingest_url = backend_url.rstrip("/") + "/api/v1/ingest"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print(f"Replaying {len(rows)} rows to {ingest_url} (speedup={speedup}x)")

    with httpx.Client(timeout=3) as client:
        prev_offset_s = 0
        for i, row in enumerate(rows):
            offset_s = i * INTERVAL_SECONDS
            wait_s = max(0.0, (offset_s - prev_offset_s) / speedup)
            if i > 0:
                time.sleep(wait_s)
            prev_offset_s = offset_s

            payload = {
                "ts": datetime.now(timezone.utc).isoformat(),  # "arrives" now
                "temp_c": row["temp_c"],
                "fan_pct": row["fan_pct"],
                "heater_on": row["heater_on"],
                "seq": row["seq"],
                "source": "mock",
            }

            try:
                resp = client.post(ingest_url, json=payload, headers=headers)
                status = resp.status_code
            except httpx.HTTPError as e:
                status = f"ERROR: {e}"

            print(f"[{i+1}/{len(rows)}] temp_c={row['temp_c']:>5} fan_pct={row['fan_pct']:>3} "
                  f"heater_on={row['heater_on']!s:<5} -> {status}")


def main():
    mode = os.environ.get("MODE", "mock")
    if mode != "mock":
        print(f"MODE={mode!r} — this script only runs in mock mode, exiting.")
        return

    backend_url = os.environ.get("AGRITWIN_BACKEND_URL", "http://127.0.0.1:8000")
    api_key = os.environ.get("AGRITWIN_API_KEY")
    speedup = float(os.environ.get("MOCK_SPEEDUP", "1"))

    if not api_key:
        print("WARNING: AGRITWIN_API_KEY not set — ask Asad for the dev ingest key. "
              "Generating/validating the CSV only, skipping replay.")
        rows = load_or_generate_csv()
        max_temp = max(r["temp_c"] for r in rows)
        spikes = [r for r in rows if r["temp_c"] > 30.0]
        print(f"CSV ready at {CSV_PATH} — {len(rows)} rows, max {max_temp}C, "
              f"{len(spikes)} rows above 30C.")
        return

    replay(backend_url, api_key, speedup)


if __name__ == "__main__":
    main()
