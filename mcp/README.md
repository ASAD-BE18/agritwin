# AgriTwin — MCP Server

Exposes the 5-tool surface from `docs/Implementation_Plan.md` §5/Step 0.6 over stdio, so
Claude Desktop (or Claude Code, or `chat_app.py` once it exists) can answer questions
about the greenhouse by calling real tools instead of guessing.

```
twin_tools.py   async functions -> httpx -> the backend's frozen HTTP contract (docs/API.md)
mcp_server.py   thin @tool() wrappers over twin_tools.py, no business logic
config.py       env/config, incl. this instance's RBAC role
```

Heater control is **not** a tool here — read-only via `get_current_conditions`, enforced
independently by the firmware thermal cutoff. `set_ventilation_level` is the only
actuator exposed, and it's RBAC-gated on this server instance's configured role.

## Setup

```
pip install -e .[dev]      # from this directory — installs mcp[cli], httpx, python-dotenv, pytest
```

Environment (`.env` in this directory, or exported):

| Var | Default | Purpose |
|---|---|---|
| `AGRITWIN_BACKEND_URL` | `http://localhost:8000` | Where the FastAPI backend is running |
| `AGRITWIN_API_KEY` | `dev-only-key-change-me` | Must match the backend's `AGRITWIN_API_KEY` |
| `AGRITWIN_ROLE` | `operator` | `operator` can set fan speed; anything else gets denied (and audited) locally |
| `AGRITWIN_MCP_AUDIT_LOG_PATH` | `mcp_audit.jsonl` | This layer's own audit trail — separate from the backend's |

To demo the RBAC denial (Phase 4 runbook), run a second instance with
`AGRITWIN_ROLE=viewer` pointed at a different audit log path.

## Running it

```
python mcp_server.py
```

Or point Claude Desktop's config at it directly:

```json
{
  "mcpServers": {
    "agritwin": {
      "command": "python",
      "args": ["C:\\Users\\AsadMajeed\\agritwin\\mcp\\mcp_server.py"]
    }
  }
}
```

**Always run/invoke it as a script from this directory (or by absolute path).** Never
`python -m mcp.mcp_server` and never `from mcp import twin_tools` — this folder is
named `mcp`, same as the third-party SDK on PyPI (`pip install "mcp[cli]"`), and the
sibling imports (`import twin_tools`, `import config`) only resolve correctly because
running as a plain script puts *this directory* at `sys.path[0]`, not the repo root.
Do not add an `__init__.py` here — that would turn this into a real importable `mcp`
package and risk shadowing the SDK for anything that later puts the repo root on
`sys.path`.

## Tests

```
pytest
```

Runs against `httpx.MockTransport` — no live backend needed. Note: run this suite from
*this* directory (or `pytest mcp/tests` from the repo root); combining it with
`backend/tests` in one `pytest` invocation from the repo root won't pick up both
directories' `pythonpath` config at once, since they're independently-runnable
services sharing a venv, not one Python package — same as `backend/` already works
today.
