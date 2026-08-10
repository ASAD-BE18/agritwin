# AgriTwin

A small IoT greenhouse rig (temperature sensor + heater + fan) with a live "digital twin" and a tool-grounded LLM chat interface on top. Built for the CATCH_VR Summer School 2026 capstone.

**Architecture:** hardware (Arduino) → FastAPI backend (single source of truth) → MCP server (5 tools) → LLM (Claude by design; see [Running the dev stack locally](#running-the-dev-stack-locally) for why the demo chat UI currently calls OpenRouter instead) → Unity digital twin. The LLM never touches hardware or the database directly — it can only call the 5 named MCP tools, and heater control is intentionally excluded from that tool surface entirely (read-only, firmware-enforced safety cutoff independent of any software layer).

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

## Running the dev stack locally

`scripts/run-dev-stack.ps1` starts the backend, the mock data replay, and the chat UI together, streaming all three logs into one window (each line prefixed `[backend]`/`[mock]`/`[chat]`); Ctrl+C stops all three at once.

```powershell
.\scripts\run-dev-stack.ps1
```

The chat UI defaults to **stub mode** at http://127.0.0.1:8001 — keyword-matched placeholder answers, no API key needed. For the real agent path (actual MCP tool-calling against a live model), pass `-RealAgent` with an OpenRouter key:

```powershell
.\scripts\run-dev-stack.ps1 -RealAgent -OpenRouterApiKey "sk-or-..."
```

Real mode calls the model through [OpenRouter](https://openrouter.ai) (an OpenAI-compatible API) using the free `openrouter/free` router model, rather than a direct Anthropic key — no Anthropic key is currently available for this project. See `chat/chat_app.py`'s module docstring for the full env var list (`USE_REAL_AGENT`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`).
