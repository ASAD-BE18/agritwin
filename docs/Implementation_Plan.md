# AgriTwin — Review & Implementation Plan

**Source:** `AgriTwin_Project_Proposal.docx` (CATCH_VR Summer School 2026 capstone)
**Prepared:** 7 August 2026
**Backend / AI lead:** Asad Majeed

---

## 1. Review

**What's strong:** the layering is genuinely correct — hardware → FastAPI → MCP → LLM → Unity, with the backend as single source of truth and the LLM only touching MCP tools. The API-first parallelism note in §11 is the right instinct. The 5-tool MCP surface in §5 is well-scoped.

Four things to change before building anything.

### 1.1 The timeline is the dominant risk, not a footnote

§8 gives Day 5 afternoon → Day 7 PM. That is **~1.5 working days** for five workstreams with three hard integration boundaries (serial↔backend, backend↔Unity, backend↔MCP↔LLM). Every one of those boundaries is where hackathon projects die.

This is buildable — but only if the backend, MCP server, crop-stress module, and mock data generator are **written and tested before arrival**, against a simulator instead of the Arduino. Then Day 5–7 is integration and demo polish, not construction. **Phase 0 is the single highest-leverage part of this plan.**

### 1.2 "RAG" is the wrong word and it will cost points in Q&A

There is no document corpus and no embedding retrieval. What's being built is **tool-augmented LLM reasoning over a time-series store** — function calling with grounded retrieval, which is *more* impressive and *more* production-accurate than RAG. A judge who knows the difference will ask.

Reframe as: *"tool-use grounding via MCP — the model cannot state a number it didn't retrieve."* Keep "retrieval-augmented" as a descriptor if desired; drop "RAG pipeline."

### 1.3 The crop-stress "ML classifier" should be an explainable rule-based scorer — and say so

§11 half-acknowledges this. Make it explicit. One sensor (temperature) and hours of data means there is no honest ML model here, and claiming one is the fastest way to lose credibility with an academic panel.

A deterministic, unit-tested, literature-calibrated scorer with named contributing factors is *stronger*: explainable, can't overfit, and maps cleanly onto §12's future work ("swap the scalar scorer for the YOLO/Faster R-CNN vision input"). The published research is the roadmap, not the Day-7 deliverable.

### 1.4 SAFETY FLAG — an LLM controlling a 12V PTC heater needs a hardware-independent interlock

`set_ventilation_level` is a real actuator on a real heating element. The proposal has RBAC and audit logging on the tool — good access control, but **not a safety control**. If the backend crashes, the serial link drops, or the LLM issues something unexpected, nothing turns the heater off.

Three independent layers are required before this is demo-safe:

- **Firmware watchdog (authoritative).** `temp > TEMP_MAX` → heater OFF, fan 100%, regardless of any command. No host command in 5 s → heater OFF. Lives in the Arduino loop; cannot be overridden by the backend, the MCP server, or the LLM.
- **Backend clamp.** Reject commands outside `0–100`; enforce a max continuous heater-on duration; refuse commands when the last reading is stale.
- **MCP layer.** RBAC + audit as proposed, **plus the LLM only ever sets fan level**. Keep heater control out of the LLM tool surface entirely for the bootcamp; expose it read-only in state.

Make that last point a feature of the demo narrative: *"the model can increase ventilation but cannot apply heat — a deliberate blast-radius decision, and the firmware enforces a thermal ceiling the software layer can't override."* Strong judge answer, and it's true.

---

## 2. Architectural decisions (settle first)

| Decision | Choice | Why |
|---|---|---|
| Twin transport | **HTTP polling @ 4 Hz**, WebSocket as stretch | Simple to build — Unity `UnityWebRequest` in a coroutine is ~20 lines. This is a prototype demo, not a production SLA: no formal latency target, just "feels responsive" (warm the sensor, watch the twin react within ~1–2 s). WebSockets in Unity is an afternoon you don't have and buys nothing a demo needs. |
| Datastore | **In-memory ring buffer**, SQLite optional | Ring buffer alone covers `/state` and `/history` for a 3-minute demo. Add SQLite only if there's spare time and you want history to survive a restart — it's insurance, not a requirement. |
| Serial ownership | **Separate bridge process**, not inside FastAPI | A wedged serial port must never take down the API the Unity team is polling. Bridge crashes → backend keeps serving last-known state and flags it stale. |
| Mock mode | **First-class runtime mode, built in Phase 0** | Not a fallback bolted on Day 7. `MODE=mock` replays a recorded CSV. Unity/LLM both develop against it from Day 6 AM. |
| Tool logic location | **One shared module**, imported by both MCP server and chat backend | Write `twin_tools.py` once. Zero duplication, one place to test. |
| LLM + model | **`claude-opus-5`** via the `anthropic` Python SDK | Current flagship, 1M context, strongest tool-use. Thinking is on by default — set `output_config={"effort": "low"}` for demo latency. |
| Tool loop | **`client.beta.messages.tool_runner`** with `anthropic.lib.tools.mcp` helpers | The SDK converts MCP tools into runnable tools and drives the loop. No hand-written agentic loop. |

### 2.1 Build the tool module once, expose it twice

```
twin_tools.py  (async fns → httpx → FastAPI)
      ├─→ mcp_server.py    (Python MCP SDK, stdio)  → Claude Desktop / Claude Code
      └─→ chat_app.py      (Anthropic SDK tool_runner) → demo web UI
```

The chat UI connects to the same MCP server as a client and converts the tools:

```python
from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async with stdio_client(StdioServerParameters(command="python", args=["mcp_server.py"])) as (r, w):
    async with ClientSession(r, w) as mcp:
        await mcp.initialize()
        tools = (await mcp.list_tools()).tools
        runner = client.beta.messages.tool_runner(
            model="claude-opus-5",
            max_tokens=4096,
            output_config={"effort": "low"},
            system=GROUNDING_PROMPT,
            tools=[async_mcp_tool(t, mcp) for t in tools],
            messages=[{"role": "user", "content": question}],
        )
        async for message in runner:
            ...
```

This is the demo centrepiece: **the same MCP server serves both the custom UI and Claude Desktop.** Show both and the "production MCP architecture" claim proves itself.

> Requires `pip install "anthropic[mcp]"` (Python 3.10+). The tool runner is a beta SDK helper — pin the `anthropic` version in `requirements.txt` so it can't shift mid-bootcamp.

### 2.2 Digital twin — what it's actually for, not just a 3D model

Worth stating explicitly, since evaluators will fairly ask it: the twin doesn't need to run its own analysis to earn its place, but it does have two distinct jobs, not one.

1. **Live mirror.** Poll `/api/v1/state` at 4 Hz, reflect fan/heater/temperature in the Unity scene. This alone earns its keep as a demo device — it's the difference between telling an audience data is flowing and showing them a physical action (warming the sensor) produce an immediate reaction on screen.
2. **Visualization surface for the backend's actual prediction.** The crop-stress scorer (Step 0.5) *is* the predictive piece, and it's a backend computation, not something Unity does. The twin's job is to make that prediction spatially legible: poll `/api/v1/stress` alongside `/state`, color the rig by `risk_label` (green/yellow/red), and add one simple object representing the crop itself that visually degrades — a color shift toward wilted/brown — as `risk_score` rises. That's the honest answer to "does it predict and show damage": the backend predicts crop-stress risk; the twin is where that prediction becomes visible on the object it's about, in real time.

AI and digital twin aren't competing for importance here — they're two interfaces, conversational and spatial, onto the same underlying prediction. Keep both halves of that sentence in the pitch; dropping either makes the project sound like less than it is.

---

## 3. Phase 0 — Before Day 5 (critical path)

Everything here is buildable with **zero hardware**. Target: done and green before travel.

### Step 0.1 — Repo + CI
*Verify: `pytest` green in GitHub Actions on push.*

```
agritwin/
  firmware/agritwin.ino
  backend/
    app/{main,models,store,control,stress,config}.py
    tests/
  bridge/{serial_bridge,mock_source}.py
  mcp/{twin_tools,mcp_server}.py
  chat/chat_app.py
  unity/          # Unity team's, referenced not vendored
  changelog/
  docs/API.md
```

Python 3.11, `pyproject.toml`, ruff + pytest. Run tests locally before each merge — GitHub Actions CI is a nice-to-have, not worth setup time for a 3-day prototype. Branch `main`, work on `feat/*`.
**`.gitignore` covers `.env`, `*.db`, `*.csv` recordings — no API keys, ever.**

### Step 0.2 — Freeze the contracts, publish `docs/API.md`
*Verify: another person can write a client from the doc alone.*

This artifact unblocks Unity on Day 6 AM. Publish it Day 5 evening at the latest.

**Reading model**

```python
class Reading(BaseModel):
    ts: datetime          # ISO-8601, UTC, always
    temp_c: float
    fan_pct: int          # 0–100
    heater_on: bool
    seq: int
    source: Literal["device", "mock"]
```

**Endpoints**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/ingest` | Bridge → backend. `X-API-Key` header. |
| `GET` | `/api/v1/state` | Current snapshot + `data_age_s` + `mode`. |
| `GET` | `/api/v1/history?start=&end=&max_points=` | Readings + `{min,max,avg,count}` summary. Downsampled server-side. |
| `GET` | `/api/v1/stress` | `{risk_score, risk_label, factors[]}` |
| `GET` | `/api/v1/health` | `{sensor_online, last_reading_age_s, buffer_size, mode, uptime_s}` |
| `POST` | `/api/v1/control/ventilation` | `{fan_pct}` → clamped, audited desired state. |
| `GET` | `/api/v1/control/desired` | Bridge polls this to push down to the Arduino. |

Every response carries units in field names (`temp_c`, `fan_pct`, `data_age_s`).
`history` **must** downsample — never hand the LLM 10,000 raw rows.

### Step 0.3 — Serial protocol + firmware
*Verify: firmware compiles; watchdog trips in a bench test with the sensor unplugged.*

Line-based ASCII, both directions:

```
Arduino → host:   T:23.44,F:60,H:1,S:1234,W:0\n     (W = watchdog-tripped flag)
host → Arduino:   F:60\n      H:0\n      PING\n
```

Firmware loop, in priority order:

1. Read DS18B20.
2. **Safety first:** `if (temp >= TEMP_MAX)` → heater off, fan 100, set `W:1`. `if (millis() - lastHostMsg > 5000)` → heater off. These run *before* any command handling and are not overridable.
3. Apply pending command (clamped to 0–100).
4. Emit telemetry line every 500 ms.

Write this even without hardware — the IoT lead flashes and tunes on Day 5 with the protocol already fixed.

### Step 0.4 — Backend
*Verify: `pytest` covers ingest, staleness, clamping, history downsampling, control audit.*

- Ring buffer (`collections.deque`, maxlen ~7200 = 1 h @ 2 Hz) + async SQLite writer.
- `data_age_s` computed on every `/state` read; `sensor_online = age < 5.0`.
- Control endpoint: clamp → persist desired → append JSONL audit line
  `{ts, actor, role, tool, args, allowed, resulting_state}`.
- **CORS**: permissive (`*`) is fine — this runs on a LAN for a 3-day demo, not a public deployment. The `X-API-Key` on write endpoints is the actual protection; don't spend time on origin allowlisting for a prototype.
- `X-API-Key` on `/ingest` and `/control/*`, read from env. Never in code.

### Step 0.5 — Crop-stress scorer
*Verify: unit tests pin every band boundary and the factor strings.*

Pure function, no state, no ML:

```python
def score(current: float, mean_10min: float, rate_c_per_min: float,
          minutes_above_30: float) -> StressResult
```

Bands: optimal 18–26 °C; caution 26–30 / 15–18; stress >30 / <15.
Penalty for `|rate| > 0.5 °C/min` (thermal shock) and for sustained time-above-threshold.

Output `risk_score` 0–100, `risk_label` ∈ {ok, caution, stress}, and `factors` as human-readable strings the LLM can quote verbatim:
`"Temperature 31.2 °C is above the 30 °C stress threshold"`.

**Cite the band source in a docstring.** That one line turns "we made up numbers" into "we calibrated from published crop temperature tolerances."

### Step 0.6 — MCP server
*Verify: `get_current_conditions` returns real JSON in Claude Desktop.*

Thin wrappers over `twin_tools.py`. No business logic. Rules:

- Every return value includes `data_age_s` so the model can flag staleness itself.
- Tool descriptions are **prescriptive about when to call**, not just what they do:
  `"Call this whenever the user asks about the current temperature, fan, or heater state. Never state a current value without calling this first."`
- `set_ventilation_level` gated on `role == "operator"` from config; every invocation audited whether allowed or denied.
- **Heater control is not exposed as a tool.** Read-only in `get_current_conditions`.

### Step 0.7 — Mock source + recorded dataset
*Verify: `MODE=mock` runs the full stack end-to-end with no Arduino attached.*

`mock_source.py` generates a realistic 30-minute greenhouse profile: ambient drift, a heater ramp, a fan-triggered cooldown, one spike above 30 °C so `predict_crop_stress` has something interesting to say. Save as CSV and replay deterministically.

**This is both the demo insurance and the parallel-development unblock.**

### Step 0.8 — Chat UI
*Verify: 5 query types answered correctly against mock data.*

Minimal FastAPI + HTMX page (or Streamlit if faster) driving the tool runner. Stream tokens. **Render each tool call as a visible chip** — *"called `get_historical_range`"* — so the audience sees grounding happen. That visual is worth more in the demo than the prose answer.

Grounding system prompt, roughly:

> You answer questions about a live greenhouse. Never state a temperature, timestamp, fan speed, or risk assessment that did not come from a tool result in this conversation. If `data_age_s` exceeds 10, say the data is stale before answering. If a tool fails, say so — do not estimate.

### Step 0.9 — Lock the 5 query types and test them
*Verify: all 5 pass against mock, scripted.*

1. *"Is it too hot for the crop right now?"* → `get_current_conditions` + `predict_crop_stress`
2. *"What was the peak temperature in the last hour?"* → `get_historical_range`
3. *"Should I increase ventilation?"* → stress + current, reasoning over both
4. *"Set the fan to 80%."* → `set_ventilation_level`, RBAC + audit visible
5. *"Is the sensor working?"* → `get_system_health`, correctly reports staleness

Turn these into an automated test asserting the right tool was called for each. That test **is** the §10 "100% grounding" success metric — measured rather than claimed.

---

## 4. Phase 1 — Day 5 (pitch + roles)

- Pitch with the Phase 0 stack **already running on mock data**. Pitching a working system rather than a slide is the entire advantage of Phase 0.
- Lock roles per §11. Hand the Unity lead `docs/API.md` and the mock backend URL immediately.
- IoT lead: flash firmware, wire DS18B20 + L298N, verify the watchdog trips with the sensor disconnected. **Bench-test the thermal cutoff before the heater is ever left unattended.**
- Backend: stand up on a laptop with a fixed LAN IP, mock mode on. Publish the URL.

*Verify: three teammates can `GET /api/v1/state` from their own machines.*

## 5. Phase 2 — Day 6 (hardware integration + parallel build)

**AM — Bridge process.** Real serial → `/ingest`. Handle port enumeration, reconnect-on-drop with backoff, malformed lines (log and skip, never crash). `MODE` toggle to flip device↔mock in one env var without restarting the API.

*Verify: unplug the USB cable mid-run — backend keeps serving, `sensor_online` goes false within 5 s, replug recovers within 10 s, Unity never errors.*

**PM — Live integration.** Swap the MCP/chat layer from mock to live device. Unity team binds the twin to live `/state` and adds the crop-stress color-coding + plant visualization from §2.2, polling `/stress` alongside it.

*Verify: warm the sensor by hand → twin readout and fan animation change within 2 s → ask the chat "is it hot?" → grounded answer citing the real number.*

## 6. Phase 3 — Day 7 AM/midday (end-to-end + hardening)

- Full chain test: sensor → bridge → backend → MCP → LLM → answer, and separately → twin.
- **Sanity-check responsiveness, informally.** Warm the sensor, watch the twin react. If it feels laggy, look at it; otherwise don't build latency instrumentation or a p95 measurement pipeline — that's production rigor a prototype doesn't need. No slide claim to back up here; skip it rather than manufacture one.
- **Failure drills**, each rehearsed at least once:
  - Unplug sensor mid-demo → does the LLM say "data is stale" rather than inventing a number?
  - Kill the LLM API (airplane-mode the laptop) → does the UI degrade to the cached Q&A set?
  - Kill the bridge → does the twin freeze cleanly with a visible stale indicator, or throw?
- **Freeze the code. Tag it. No feature work after midday** — only demo rehearsal.

## 7. Phase 4 — Day 7 PM (demo)

### 3-minute runbook — rehearse end to end at least twice

| Time | Action |
|---|---|
| 0:00–0:20 | Physical rig + Unity twin side by side, both live. Architecture in one sentence. |
| 0:20–0:50 | Warm the sensor by hand. Twin reacts live. |
| 0:50–1:40 | Three natural-language questions. **Show the tool-call chips** — the differentiating moment. |
| 1:40–2:10 | Issue a control command. Show the audit log line and the RBAC denial for a viewer role. |
| 2:10–2:35 | AR overlay on the physical rig. *(Cut — no AR/VR hardware available; use this time for extra Q&A or a second live question instead.)* |
| 2:35–3:00 | Close on the research thread: temperature-only scorer today → YOLO / Faster R-CNN vision input tomorrow (§12). |

### Pre-demo checklist

- [ ] LLM API key valid, connectivity tested **in the venue, on venue wifi**
- [ ] Mock replay ready as a one-keystroke fallback
- [ ] Fallback Q&A cache loaded
- [ ] Laptop on mains power
- [ ] Screen mirroring tested

---

## 8. Cross-cutting requirements

**Changelog** — one file per PR in `changelog/`, named `changelog_dd_mm_yyyy_asad_<pr>.md`, describing user-facing impact. Update it on every subsequent push to an open PR.

**Commits** — atomic, imperative subject ≤50 chars (`feat(mcp): add get_system_health tool`), body explains *why*. Branch off `main`, never commit to it directly. Never push — branches are handed over local and ready.

**Security posture, stated honestly for the demo:**

- *Confirmed*: API-key auth on write endpoints; named-origin CORS; RBAC + JSONL audit on control tools; no secrets in the repo; firmware thermal cutoff independent of software.
- *Not done, and say so if asked*: TLS (plain HTTP on a LAN), real identity/authn (role comes from config, not a token), persistent tamper-evident audit storage, rate limiting.

Naming those gaps yourself is a better Q&A answer than being caught by them.

---

## 9. Success criteria (mapped to §10, measured not claimed)

| Metric | Target | How it's verified |
|---|---|---|
| Answer grounding | 100% | Automated test asserting tool-call-before-numeric-claim on all 5 queries |
| Query coverage | ≥ 5 types | The Step 0.9 test suite, green |
| Crop-stress explainability | ≥ 1 named factor | Unit test asserts `factors` non-empty for every non-ok label |
| Demo reliability | 3 min, no intervention | Two clean full rehearsals on Day 7 AM |
| Thermal safety | Cutoff verified | Bench test: sensor disconnected + over-temperature simulation |

**Dropped from this table: sensor→twin latency.** The original proposal (§10) lists "<2 s end-to-end latency" as a metric. For a prototype demo that's not worth formally measuring or instrumenting — polling at 4 Hz is visually responsive and that's enough. If you want to keep the line in the proposal document itself for the write-up, it's true by construction (4 Hz polling ≈ 250 ms), but don't build logging/percentile-reporting infrastructure to prove it.

Thermal safety stays as a hard requirement regardless of prototype scope — it's a physical burn/fire risk on real hardware, not a production-readiness concern that scales down with project size.

---

## 10. Open questions

1. **Chat UI vs. Claude Desktop as primary demo surface.**
   Claude Desktop is zero UI work and looks legitimately production-real; a custom UI shows tool-call chips and looks more like a product.
   *Recommendation:* build the custom UI (Step 0.8) as primary, keep Claude Desktop connected as the "and it works with any MCP host" reveal. If Phase 0 time gets tight, cutting the custom UI is the safest single cut available.

2. **Is the Arduino kit available before Day 5, or only on-site?**
   With hardware in advance, Step 0.3 moves from "write blind" to "test the watchdog on the bench" — materially de-risking the safety layer. Without it, the mock path carries the build and the IoT lead validates the cutoff Day 5 morning — but then the thermal test is on the critical path and must happen before the heater runs unattended.

---

## 11. Team assignment (5 members) — see docs/team-briefs/ for individual briefs

| Person | Owns |
|---|---|
| Asad Majeed (Lead) | Backend, MCP server, LLM/tool_runner integration, crop-stress scorer, API contract, overall integration |
| Muhammad Irfan | Firmware, sensor + actuator wiring, thermal watchdog, hardware bring-up |
| Shakila Naaz | Unity digital twin (3D scene only — no AR/VR hardware available) |
| Tayyaba Fatima | Mock data generator, chat UI, automated tests |
| Maheen Nazam | Timeline, changelog, cost tracking, demo script, plain-language QA |

**Note (added after initial planning):** the original proposal's AR overlay is out of scope — the team only has the Arduino kit and sensors, no AR/VR-capable hardware. The Phase 4 runbook above reflects this cut.
