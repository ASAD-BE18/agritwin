"""
Serial <-> /api/v1/ingest bridge process. Runs as a separate process so a wedged
serial port can't take the FastAPI backend down with it (docs/Implementation_Plan.md
§2's "Serial ownership" decision) — a crashed or hung bridge just means the backend
keeps serving its last-known state, aging into staleness on its own.

Responsibilities:
  - Auto-detect (or use AGRITWIN_SERIAL_PORT) and open the Arduino's serial port.
  - Parse telemetry lines (protocol.py) and POST each valid one to /api/v1/ingest.
    A sensor-disconnected sentinel reading (protocol.SENSOR_DISCONNECTED_SENTINEL_C)
    is logged but not ingested — better to let the reading go stale (and
    sensor_online flip false on its own) than store a nonsensical -127°C data point
    that would corrupt history/crop-stress calculations.
  - Poll /api/v1/control/desired and push the fan setpoint back down as F:<pct>\n,
    resent every CONTROL_PUSH_INTERVAL_S regardless of whether it changed — this
    doubles as the "still connected" signal the firmware's host-timeout watchdog
    needs (AgriTwinCore.cpp trips heater-off after 5s of silence).
  - Never send H: commands — heater control is deliberately excluded from every
    software layer above the firmware (docs/Implementation_Plan.md §1.4); there is
    no desired-heater-state endpoint on the backend to poll in the first place.
  - Reconnect with exponential backoff on a dropped port. Backend/network failures
    are logged and skipped per-call; only a serial-port failure triggers a
    reconnect, since those are different failure domains.

Run as a script from this directory (`python serial_bridge.py`) — bare `import
config` / `import protocol` below are sibling-file imports.

Owner: Asad (protocol specifics agreed with Irfan — see docs/team-briefs/IRFAN.md).
"""

import logging
import time

import config
import httpx
import protocol
import serial
import serial.tools.list_ports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agritwin.bridge")

# Official Arduino, arduino.org, and the common CH340 clone adapter used on cheap Uno
# boards/clones — enough to auto-detect the common cases; AGRITWIN_SERIAL_PORT always
# wins over this when set.
_ARDUINO_HWID_MARKERS = ("2341:", "2a03:", "1a86:7523")


def resolve_port(explicit: str | None, ports: list) -> str | None:
    """Picks a serial port: the explicit override if given, else the first port whose
    description or hwid looks like an Arduino. Returns None if nothing matches."""
    if explicit:
        return explicit

    for port in ports:
        description = (port.description or "").lower()
        hwid = (port.hwid or "").lower()
        if "arduino" in description or any(marker in hwid for marker in _ARDUINO_HWID_MARKERS):
            return port.device

    return None


def run() -> None:
    client = httpx.Client(base_url=config.BACKEND_URL, timeout=config.REQUEST_TIMEOUT_S)
    backoff = config.RECONNECT_INITIAL_BACKOFF_S

    while True:
        try:
            ser = _open_port()
            backoff = config.RECONNECT_INITIAL_BACKOFF_S
            log.info("connected to %s", ser.port)
            _serve(ser, client)
        except serial.SerialException as exc:
            log.warning("serial error: %s -- reconnecting in %.1fs", exc, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, config.RECONNECT_MAX_BACKOFF_S)


def _open_port() -> serial.Serial:
    port = resolve_port(config.SERIAL_PORT, list(serial.tools.list_ports.comports()))
    if port is None:
        available = [p.device for p in serial.tools.list_ports.comports()]
        raise serial.SerialException(
            "No Arduino-like serial port found and AGRITWIN_SERIAL_PORT is unset. "
            f"Available ports: {available}"
        )
    return serial.Serial(port, config.SERIAL_BAUD, timeout=0.2)


def _serve(ser: serial.Serial, client: httpx.Client) -> None:
    last_push = 0.0
    while True:
        line = ser.readline().decode("ascii", errors="replace")
        if line:
            _handle_line(line, client)

        now = time.monotonic()
        if now - last_push >= config.CONTROL_PUSH_INTERVAL_S:
            _push_desired_fan(ser, client)
            last_push = now


def _handle_line(line: str, client: httpx.Client) -> None:
    reading = protocol.parse_telemetry_line(line)
    if reading is None:
        log.debug("dropping unparseable line: %r", line)
        return

    sensor_ok = reading.pop("sensor_ok")
    if not sensor_ok:
        log.warning(
            "sensor read failed (disconnected?) -- not ingesting; watchdog_tripped=%s",
            reading["watchdog_tripped"],
        )
        return

    try:
        resp = client.post(
            "/api/v1/ingest", json=reading, headers={"X-API-Key": config.BACKEND_API_KEY}
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("ingest failed: %s", exc)


def _push_desired_fan(ser: serial.Serial, client: httpx.Client) -> None:
    try:
        resp = client.get(
            "/api/v1/control/desired", headers={"X-API-Key": config.BACKEND_API_KEY}
        )
        resp.raise_for_status()
        fan_pct = resp.json()["fan_pct"]
    except httpx.HTTPError as exc:
        log.warning("could not fetch desired fan state: %s", exc)
        return

    ser.write(protocol.format_fan_command(fan_pct).encode("ascii"))


if __name__ == "__main__":
    run()
