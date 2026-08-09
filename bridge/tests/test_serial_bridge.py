"""
Tests the bridge's decision logic (port selection, line handling, control push)
against fakes/mocks — no real or virtual serial port and no live backend needed.
The reconnect loop in serial_bridge.run() itself isn't covered here: it's a thin,
inherently-manual-test surface (unplug a real cable and watch the backoff/log lines),
matching the plan's own verification story for this piece
(docs/Implementation_Plan.md Phase 2 AM: "unplug the USB cable mid-run...").
"""

import json

import config
import httpx
import serial_bridge


class FakePortInfo:
    def __init__(self, device, description="", hwid=""):
        self.device = device
        self.description = description
        self.hwid = hwid


class FakeSerial:
    def __init__(self):
        self.written: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.written.append(data)


def test_resolve_port_prefers_explicit_override():
    ports = [FakePortInfo("COM3", description="Arduino Uno")]
    assert serial_bridge.resolve_port("COM9", ports) == "COM9"


def test_resolve_port_matches_arduino_description():
    ports = [
        FakePortInfo("COM3", description="USB Serial Port"),
        FakePortInfo("COM5", description="Arduino Uno"),
    ]
    assert serial_bridge.resolve_port(None, ports) == "COM5"


def test_resolve_port_matches_ch340_clone_by_hwid():
    ports = [FakePortInfo("COM4", description="USB-SERIAL CH340", hwid="USB VID:PID=1A86:7523")]
    assert serial_bridge.resolve_port(None, ports) == "COM4"


def test_resolve_port_returns_none_when_nothing_matches():
    ports = [FakePortInfo("COM1", description="Bluetooth Link")]
    assert serial_bridge.resolve_port(None, ports) is None


def test_handle_line_posts_valid_reading():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["api_key"] = request.headers["x-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    serial_bridge._handle_line("T:23.44,F:60,H:1,S:1234,W:0", client)

    assert seen["path"] == "/api/v1/ingest"
    assert seen["api_key"] == config.BACKEND_API_KEY
    assert seen["body"] == {
        "temp_c": 23.44,
        "fan_pct": 60,
        "heater_on": True,
        "seq": 1234,
        "source": "device",
        "watchdog_tripped": False,
    }


def test_handle_line_skips_malformed_line_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the backend for a malformed line")

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    serial_bridge._handle_line("not a telemetry line", client)  # must not raise


def test_handle_line_skips_sensor_disconnected_reading():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not ingest a disconnected-sensor sentinel reading")

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    serial_bridge._handle_line("T:-127.00,F:100,H:0,S:5,W:1", client)  # must not raise


def test_handle_line_does_not_raise_when_backend_rejects():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    serial_bridge._handle_line("T:23.0,F:0,H:0,S:1,W:0", client)  # logs, must not raise


def test_push_desired_fan_writes_command_from_backend():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/control/desired"
        return httpx.Response(200, json={"fan_pct": 42})

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    ser = FakeSerial()
    serial_bridge._push_desired_fan(ser, client)
    assert ser.written == [b"F:42\n"]


def test_push_desired_fan_does_not_raise_or_write_when_backend_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    ser = FakeSerial()
    serial_bridge._push_desired_fan(ser, client)  # must not raise
    assert ser.written == []


def test_push_desired_fan_does_not_raise_on_malformed_200_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})  # no fan_pct key

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    ser = FakeSerial()
    serial_bridge._push_desired_fan(ser, client)  # must not raise KeyError
    assert ser.written == []


def test_push_desired_fan_does_not_raise_on_invalid_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = httpx.Client(base_url="http://backend.test", transport=httpx.MockTransport(handler))
    ser = FakeSerial()
    serial_bridge._push_desired_fan(ser, client)  # must not raise a JSON decode error
    assert ser.written == []
