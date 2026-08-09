# AgriTwin — Serial Bridge

Owns the Arduino's serial port so a wedged connection never takes the FastAPI backend
down with it (docs/Implementation_Plan.md §2's "Serial ownership" decision). Reads
telemetry, forwards it to `/api/v1/ingest`, and pushes the operator's fan setpoint
back down to the Arduino.

```
protocol.py       pure parsing/formatting for the T:/F:/H:/S:/W: line protocol
config.py         env/config (port, backend URL, timing)
serial_bridge.py  the process: open port, read+ingest, poll+push, reconnect on drop
```

## Setup

```
pip install -e .[dev]      # from this directory
```

| Var | Default | Purpose |
|---|---|---|
| `AGRITWIN_SERIAL_PORT` | *(auto-detect)* | Set explicitly if there's more than one serial adapter plugged in |
| `AGRITWIN_SERIAL_BAUD` | `9600` | Must match `Serial.begin(...)` in `AgriTwinCore.cpp` |
| `AGRITWIN_BACKEND_URL` | `http://localhost:8000` | |
| `AGRITWIN_API_KEY` | `dev-only-key-change-me` | Must match the backend's |
| `AGRITWIN_CONTROL_PUSH_INTERVAL_S` | `1.0` | How often the fan setpoint is resent — also the bridge's "still connected" heartbeat, must stay well under the firmware's 5s host-timeout |

## Running it

```
python serial_bridge.py
```

Run this as a plain script from this directory (or by absolute path) — the sibling
`import config` / `import protocol` only resolve correctly that way.

Auto-detect looks for a port whose description contains "Arduino" or whose hwid
matches the official Arduino, arduino.org, or CH340-clone vendor IDs. If nothing
matches (or several real devices are plugged in and it guesses wrong), set
`AGRITWIN_SERIAL_PORT` explicitly — the error message lists what was found.

## What it deliberately does NOT do

- **Never sends `H:` (heater) commands.** Heater control is excluded from every
  software layer above the firmware by design — there's no desired-heater-state
  endpoint on the backend for this to even poll. See
  `docs/Implementation_Plan.md` §1.4.
- **Never ingests a sensor-disconnected reading.** The firmware sends `-127.0` as a
  sentinel `temp_c` when the DS18B20 read fails (always paired with `W:1`). Rather
  than storing a nonsensical -127°C data point, the bridge skips it and lets the
  reading age into staleness — `sensor_online` on `/api/v1/state` flips false on its
  own within `AGRITWIN_STALE_AFTER_S`.

## Open question for Irfan, not fixed here

`AgriTwinCore.cpp` only ever sets `desiredHeaterOn` from an incoming `H:` command —
there's no autonomous on-device thermostat (unlike `firmware/web_sim/app.js`'s JS
reimplementation, which does have one for demo purposes). Since no host process is
supposed to send `H:` at all, as currently written the real hardware's heater has no
path to ever turn on. Worth confirming intent before hardware bring-up: either the
firmware needs its own thermostat logic, or heating is genuinely out of scope for
this prototype and only the safety cutoff (forcing it off) gets demoed.

## Tests

```
pytest
```

Covers protocol parsing/formatting, port auto-detection, and the ingest/control-push
decision logic against `httpx.MockTransport` and a fake serial object — no real
hardware needed. The reconnect-with-backoff loop itself is intentionally not
unit-tested; it's a thin wrapper best verified the way the plan already calls for
(Phase 2 AM: unplug the USB cable mid-run, confirm the backend keeps serving and a
replug recovers).
