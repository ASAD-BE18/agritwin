"""
Env/config loading for the MCP layer. Same pattern as backend/app/config.py but a
separate module — the MCP server is a standalone process that only ever talks to the
backend over HTTP, never by importing backend code directly.
"""

import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.environ.get("AGRITWIN_BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.environ.get("AGRITWIN_API_KEY", "dev-only-key-change-me")

# Static per-instance role — RBAC "from config, not a token" (docs/Implementation_Plan.md
# §8's stated security posture). To demo an RBAC denial, run a second server instance
# with AGRITWIN_ROLE=viewer.
ROLE = os.environ.get("AGRITWIN_ROLE", "operator")

# MCP-layer audit trail (§1.4 layer 3 of 3) — separate from the backend's own audit log
# (control.py, layer 2), since an RBAC denial here never reaches the backend at all.
AUDIT_LOG_PATH = os.environ.get("AGRITWIN_MCP_AUDIT_LOG_PATH", "mcp_audit.jsonl")

REQUEST_TIMEOUT_S = float(os.environ.get("AGRITWIN_MCP_TIMEOUT_S", "5.0"))
