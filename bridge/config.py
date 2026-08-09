"""
Env/config loading for the serial bridge. Same pattern as backend/app/config.py and
mcp/config.py — this is a standalone process, only ever talking to the backend over
HTTP and to the Arduino over serial.
"""

import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.environ.get("AGRITWIN_BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.environ.get("AGRITWIN_API_KEY", "dev-only-key-change-me")

# None -> auto-detect an Arduino-like port (see serial_bridge.resolve_port). Set this
# explicitly if auto-detect ever picks the wrong device on a machine with multiple
# serial adapters plugged in.
SERIAL_PORT = os.environ.get("AGRITWIN_SERIAL_PORT")
SERIAL_BAUD = int(os.environ.get("AGRITWIN_SERIAL_BAUD", "9600"))

# Must stay comfortably under the firmware's 5000ms host-timeout
# (firmware/common/AgriTwinCore.cpp's HOST_TIMEOUT_MS) — this cadence is what keeps
# the firmware's watchdog from tripping heater-off on silence alone.
CONTROL_PUSH_INTERVAL_S = float(os.environ.get("AGRITWIN_CONTROL_PUSH_INTERVAL_S", "1.0"))

RECONNECT_INITIAL_BACKOFF_S = float(os.environ.get("AGRITWIN_RECONNECT_INITIAL_BACKOFF_S", "0.5"))
RECONNECT_MAX_BACKOFF_S = float(os.environ.get("AGRITWIN_RECONNECT_MAX_BACKOFF_S", "5.0"))

REQUEST_TIMEOUT_S = float(os.environ.get("AGRITWIN_BRIDGE_TIMEOUT_S", "3.0"))
