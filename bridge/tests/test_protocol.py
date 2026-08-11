import protocol


def test_parse_telemetry_line_valid():
    result = protocol.parse_telemetry_line("T:23.44,F:60,H:1,S:1234,W:0")
    assert result == {
        "temp_c": 23.44,
        "fan_pct": 60,
        "heater_on": True,
        "seq": 1234,
        "source": "device",
        "watchdog_tripped": False,
        "sensor_ok": True,
    }


def test_parse_telemetry_line_strips_crlf_and_trailing_newline():
    assert protocol.parse_telemetry_line("T:20.0,F:0,H:0,S:1,W:0\r\n") is not None
    assert protocol.parse_telemetry_line("T:20.0,F:0,H:0,S:1,W:0\n") is not None


def test_parse_telemetry_line_handles_negative_temperature():
    result = protocol.parse_telemetry_line("T:-5.5,F:0,H:1,S:1,W:0")
    assert result["temp_c"] == -5.5
    assert result["sensor_ok"] is True


def test_parse_telemetry_line_rejects_malformed_or_empty():
    assert protocol.parse_telemetry_line("garbage noise") is None
    assert protocol.parse_telemetry_line("") is None
    assert protocol.parse_telemetry_line("T:23.4,F:60,H:1,S:1234") is None  # missing W


def test_parse_telemetry_line_flags_sensor_disconnected_sentinel():
    result = protocol.parse_telemetry_line("T:-127.00,F:100,H:0,S:5,W:1")
    assert result["sensor_ok"] is False
    assert result["watchdog_tripped"] is True
    assert result["fan_pct"] == 100
    assert result["heater_on"] is False


def test_parse_telemetry_line_flags_watchdog_trip_without_sensor_failure():
    result = protocol.parse_telemetry_line("T:33.0,F:100,H:0,S:9,W:1")
    assert result["sensor_ok"] is True
    assert result["watchdog_tripped"] is True


def test_format_fan_command():
    assert protocol.format_fan_command(60) == "F:60\n"
    assert protocol.format_fan_command(0) == "F:0\n"
