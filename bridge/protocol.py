"""
Pure parsing/formatting for the Arduino<->host serial protocol shared with
firmware/common/AgriTwinCore.cpp. No I/O here — see serial_bridge.py for the process
that actually owns the port. Kept separate so the protocol logic is testable without
a real (or fake) serial port at all.

Protocol (agreed with Irfan — see docs/team-briefs/IRFAN.md; changes to this format
must be agreed with him first, the firmware parses/emits exactly this):
  Arduino -> host:  T:<temp_c>,F:<fan_pct>,H:<0|1>,S:<seq>,W:<0|1>\n   every 500ms
  host -> Arduino:  F:<0-100>\n   H:<0|1>\n   PING\n
  9600 baud

Firmware sends -127.0 as a sentinel temp_c when the DS18B20 read fails (see
AgriTwinCore.cpp's `sensorOk` check) — always paired with W:1, since a failed read
hits the same safety branch as an over-temperature trip. parse_telemetry_line surfaces
this as `sensor_ok: False` rather than silently treating -127.0 as a real reading;
serial_bridge.py uses that to skip ingesting it (see its module docstring for why).

Only F: is ever formatted here — heater control (H:) is deliberately never sent by
the bridge. Heater control is excluded from every software layer above the firmware
by design (docs/Implementation_Plan.md §1.4); the backend has no desired-heater-state
endpoint to poll in the first place.
"""

import re

_TELEMETRY_RE = re.compile(
    r"^T:(?P<temp>-?\d+(?:\.\d+)?),F:(?P<fan>\d+),H:(?P<heater>[01]),"
    r"S:(?P<seq>\d+),W:(?P<watchdog>[01])$"
)

SENSOR_DISCONNECTED_SENTINEL_C = -127.0


def parse_telemetry_line(line: str) -> dict | None:
    """Parses one telemetry line into an ingest-ready payload dict (plus a
    `sensor_ok` flag not part of the ingest contract), or None if the line doesn't
    match — malformed/noise lines are logged and skipped by the caller, never fatal,
    matching the firmware's own handling of garbage input on its side."""
    match = _TELEMETRY_RE.match(line.strip())
    if match is None:
        return None

    temp_c = float(match["temp"])
    return {
        "temp_c": temp_c,
        "fan_pct": int(match["fan"]),
        "heater_on": match["heater"] == "1",
        "seq": int(match["seq"]),
        "source": "device",
        "watchdog_tripped": match["watchdog"] == "1",
        "sensor_ok": temp_c != SENSOR_DISCONNECTED_SENTINEL_C,
    }


def format_fan_command(fan_pct: int) -> str:
    return f"F:{fan_pct}\n"
