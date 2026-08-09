# AgriTwin

A small IoT greenhouse rig (temperature sensor + heater + fan) with a live "digital twin" and a tool-grounded LLM chat interface on top. Built for the CATCH_VR Summer School 2026 capstone.

**Architecture:** hardware (Arduino) → FastAPI backend (single source of truth) → MCP server (5 tools) → LLM (Claude) → Unity digital twin. The LLM never touches hardware or the database directly — it can only call the 5 named MCP tools, and heater control is intentionally excluded from that tool surface entirely (read-only, firmware-enforced safety cutoff independent of any software layer).

## Start here

- **New to the project?** Read your task brief in [`docs/team-briefs/`](docs/team-briefs/) first — it's written for your specific part and doesn't assume you've read anything else.
- **Full technical plan:** [`docs/Implementation_Plan.md`](docs/Implementation_Plan.md).
- **API contract** (what the backend serves, exact JSON shapes): [`docs/API.md`](docs/API.md).

## Repo layout

```
firmware/           Arduino sketch (common/ + agritwin_hardware/) + web_sim/ browser demo — Irfan
backend/app/        FastAPI backend — Asad
backend/tests/
bridge/             Serial<->backend bridge + mock data source — Asad / Tayyaba
mcp/                MCP server + shared tool functions — Asad
chat/               Demo chat UI — Tayyaba
unity/              Unity digital twin project — Shakila
docs/               API contract, implementation plan, team briefs
changelog/          One file per PR — see changelog/README.md
```

## Working in this repo

- Branch off `main` as `feat/<yourname>/<short-description>` (e.g. `feat/irfan/watchdog`). Never commit to `main` directly.
- Open a Pull Request when ready — that's how your work gets merged and how contribution shows up per-person.
- Every PR needs a one-line changelog entry — see [`changelog/README.md`](changelog/README.md).
- Not comfortable with git commands yet? GitHub's web UI lets you edit or create files directly in the browser (the pencil icon on any file) — that's enough for docs/changelog work.

## Mock mode

The backend supports `MODE=mock` from day one — a recorded, realistic 30-minute greenhouse profile replayed through the same API as real hardware would use. Everyone except firmware work can build and test against this before any hardware exists.
