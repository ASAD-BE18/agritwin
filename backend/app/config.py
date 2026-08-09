"""
Env/config loading for the AgriTwin backend.

Everything here is read once at import time from environment variables (a `.env`
file works too via python-dotenv). Never hardcode a secret as a fallback default.
"""

import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("AGRITWIN_API_KEY", "dev-only-key-change-me")

# Sensor considered offline once the last reading is older than this.
STALE_AFTER_S = float(os.environ.get("AGRITWIN_STALE_AFTER_S", "5.0"))

# Ring buffer size: default ~1h at 2 readings/sec (matches the plan's Step 0.4 sizing).
BUFFER_MAXLEN = int(os.environ.get("AGRITWIN_BUFFER_MAXLEN", "7200"))

# Crop-stress band boundaries (°C) — see backend/app/stress.py for how these are used.
STRESS_OPTIMAL_LOW = float(os.environ.get("AGRITWIN_STRESS_OPTIMAL_LOW", "18.0"))
STRESS_OPTIMAL_HIGH = float(os.environ.get("AGRITWIN_STRESS_OPTIMAL_HIGH", "26.0"))
STRESS_CAUTION_LOW = float(os.environ.get("AGRITWIN_STRESS_CAUTION_LOW", "15.0"))
STRESS_CAUTION_HIGH = float(os.environ.get("AGRITWIN_STRESS_CAUTION_HIGH", "30.0"))

AUDIT_LOG_PATH = os.environ.get("AGRITWIN_AUDIT_LOG_PATH", "control_audit.jsonl")
