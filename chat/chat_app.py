"""
AgriTwin — Demo Chat UI 
=============================================================

  - Full visual redesign. Design system: a "grow-light monitoring
    dashboard" aesthetic instead of a generic chat-bubble skin — deep
    growth-green + amber grow-light accent palette, a humanist sans for
    conversation text paired with a monospace utility face for anything
    that's actually data (temperatures, tool names, status).
  - Signature element: tool-call chips are now styled like a small
    terminal/telemetry log strip under each AI reply, not a decorative
    badge — this is deliberate, since "the model can't state a number it
    didn't retrieve" is the whole point of the project, so the one place
    that should visually read as verified fact is where tools get cited.
  - Header status pill replaces the old banner box — shows LIVE (pulsing
    green) vs STUB MODE (static amber) inline instead of a separate alert.
  - Pre-seed query chips (unchanged in *logic* from v2) are now icon +
    label "quick query" pills grouped under a small eyebrow label.
  - Empty-state placeholder invites the first click instead of a blank box.
  - Typing indicator is now three animated dots instead of italic text.
  - No external font/CDN dependency — system font stack only, since this
    needs to survive on unreliable venue wifi during the actual demo.

Same backend contract as v1/v2 — only the index() HTML/CSS/JS changed;
call_agent_stub/call_agent_real/lifespan/the /api/chat route are unchanged.

Run:
    uvicorn chat_app:app --reload --port 8001
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from tool_names import (
    GET_CURRENT_CONDITIONS,
    GET_HISTORICAL_RANGE,
    PREDICT_CROP_STRESS,
    SET_VENTILATION_LEVEL,
    GET_SYSTEM_HEALTH,
    GROUNDING_SYSTEM_PROMPT,
)

USE_REAL_AGENT = os.environ.get("USE_REAL_AGENT", "false").lower() == "true"
MCP_SERVER_CMD = os.environ.get("MCP_SERVER_CMD", "python ../mcp/mcp_server.py")

mcp_session = {"session": None}
anthropic_client = AsyncAnthropic() if USE_REAL_AGENT else None

# The 5 pre-seed queries — exactly the brief's 5 required test questions,
# so clicking a chip always exercises a known-good, already-tested path.
# Each tuple is (question, icon_key) — icon_key maps to a tiny inline SVG
# in the ICONS dict below, purely cosmetic, purely optional to keep in sync.
SUGGESTED_QUERIES = [
    ("Is it too hot for the crop right now?", "thermometer"),
    ("What was the peak temperature in the last hour?", "history"),
    ("Should I increase ventilation?", "wind"),
    ("Set the fan to 80%.", "sliders"),
    ("Is the sensor working?", "pulse"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not USE_REAL_AGENT:
        yield
        return

    cmd_parts = MCP_SERVER_CMD.split()
    command, args = cmd_parts[0], cmd_parts[1:]
    params = StdioServerParameters(command=command, args=args)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_session["session"] = session
            yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


def call_agent_stub(question: str):
    q = question.lower()
    if "peak" in q or "last hour" in q or "history" in q:
        tools = [GET_HISTORICAL_RANGE]
        answer = "(stub) Peak temperature in the last hour was 31.2°C."
    elif "ventilation" in q or "increase" in q:
        tools = [PREDICT_CROP_STRESS, GET_CURRENT_CONDITIONS]
        answer = "(stub) Conditions are trending warm — yes, increasing ventilation is reasonable."
    elif "set the fan" in q or "set fan" in q:
        tools = [SET_VENTILATION_LEVEL]
        answer = "(stub) Fan speed has been set as requested."
    elif "sensor" in q or "working" in q:
        tools = [GET_SYSTEM_HEALTH]
        answer = "(stub) Sensor is reporting fresh data, last update 2 seconds ago."
    else:
        tools = [GET_CURRENT_CONDITIONS, PREDICT_CROP_STRESS]
        answer = "(stub) Current temperature is within a safe range for the crop."
    return answer, tools


async def call_agent_real(question: str):
    session = mcp_session["session"]
    if session is None:
        raise RuntimeError(
            "MCP session not initialized — this only runs correctly under "
            "USE_REAL_AGENT=true with the app's lifespan startup."
        )

    tools = (await session.list_tools()).tools

    runner = anthropic_client.beta.messages.tool_runner(
        model="claude-opus-5",
        max_tokens=4096,
        output_config={"effort": "low"},
        system=GROUNDING_SYSTEM_PROMPT,
        tools=[async_mcp_tool(t, session) for t in tools],
        messages=[{"role": "user", "content": question}],
    )

    tools_called = []
    final_text = ""
    async for message in runner:
        for block in getattr(message, "content", []):
            if getattr(block, "type", None) == "tool_use":
                tools_called.append(block.name)
            if getattr(block, "type", None) == "text":
                final_text += block.text

    return final_text, tools_called


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if USE_REAL_AGENT:
        answer, tools_called = await call_agent_real(req.message)
    else:
        answer, tools_called = call_agent_stub(req.message)
    return {"reply": answer, "tools_called": tools_called}


# Tiny inline stroke icons — no icon font, no CDN, no build step. Each is a
# self-contained 18x18 SVG. Purely decorative; if a SUGGESTED_QUERIES entry
# uses a key not listed here it just renders with no icon, no error.
ICONS = {
    "thermometer": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="7" y="2" width="4" height="9" rx="2"/><circle cx="9" cy="13.5" r="2.5"/><line x1="9" y1="4" x2="9" y2="10.5"/></svg>',
    "history": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="9.5" r="6.5"/><polyline points="9,6 9,9.5 12,11.5"/></svg>',
    "wind": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2 6h9a2 2 0 1 0-2-2"/><path d="M2 10.5h11a2 2 0 1 1-2 2"/><path d="M2 15h7a2 2 0 1 0-2-2"/></svg>',
    "sliders": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="4" y1="3" x2="4" y2="15"/><circle cx="4" cy="7" r="1.8"/><line x1="9" y1="3" x2="9" y2="15"/><circle cx="9" cy="11" r="1.8"/><line x1="14" y1="3" x2="14" y2="15"/><circle cx="14" cy="6" r="1.8"/></svg>',
    "pulse": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,9.5 5,9.5 6.5,5 9.5,14 11,9.5 16,9.5"/></svg>',
}


@app.get("/", response_class=HTMLResponse)
def index():
    status_label = "LIVE AGENT" if USE_REAL_AGENT else "STUB MODE"
    status_class = "live" if USE_REAL_AGENT else "stub"
    stub_note = "" if USE_REAL_AGENT else (
        '<div class="stub-note">Running with placeholder answers — set '
        '<code>USE_REAL_AGENT=true</code> to connect the real agent.</div>'
    )

    chips_html = "".join(
        f'<button class="chip" onclick="sendPreset({q!r})">'
        f'<span class="chip-icon">{ICONS.get(icon_key, "")}</span>'
        f'<span>{q}</span></button>'
        for q, icon_key in SUGGESTED_QUERIES
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AgriTwin — Greenhouse Assistant</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --ink: #10201a;
      --ink-soft: #1c3327;
      --paper: #f6faf6;
      --panel: #ffffff;
      --green: #2f6b49;
      --green-deep: #1f4e35;
      --green-soft: #e4f1e6;
      --amber: #d98f2b;
      --amber-soft: #fbeed9;
      --soil-soft: #eef1ec;
      --line: #dde6de;
      --muted: #5c6b62;
      --danger: #b3452f;
      --mono: ui-monospace, 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      --sans: -apple-system, 'Segoe UI', system-ui, Roboto, sans-serif;
      --radius: 14px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scrollbar-gutter: stable; }}
    body {{
      font-family: var(--sans);
      background: var(--paper);
      background-image:
        radial-gradient(circle at 100% 0%, rgba(47,107,73,0.06), transparent 45%),
        radial-gradient(circle at 0% 100%, rgba(217,143,43,0.05), transparent 45%);
      margin: 0;
      color: var(--ink);
      min-height: 100vh;
      display: flex;
      justify-content: center;
    }}
    .app {{
      width: 100%;
      max-width: 760px;
      padding: 20px 18px 28px;
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }}

    /* ---------- Header ---------- */
    header {{
      background: var(--ink);
      border-radius: var(--radius);
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      color: #eef4ef;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; }}
    .brand-mark {{
      width: 34px; height: 34px; border-radius: 9px;
      background: linear-gradient(155deg, var(--green) 0%, var(--green-deep) 100%);
      display: flex; align-items: center; justify-content: center;
      font-size: 1.05em; flex-shrink: 0;
    }}
    .brand-text h1 {{ font-size: 1.05em; margin: 0; letter-spacing: 0.01em; font-weight: 650; }}
    .brand-text p {{ margin: 1px 0 0; font-size: 0.74em; color: #9db3a6; }}

    .status-pill {{
      display: flex; align-items: center; gap: 6px;
      font-family: var(--mono);
      font-size: 0.68em;
      letter-spacing: 0.06em;
      padding: 6px 10px;
      border-radius: 20px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      white-space: nowrap;
    }}
    .dot {{ width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }}
    .status-pill.live .dot {{ background: #59d98a; box-shadow: 0 0 0 0 rgba(89,217,138,0.6); animation: pulse 2s infinite; }}
    .status-pill.stub .dot {{ background: var(--amber); }}
    @keyframes pulse {{
      0%   {{ box-shadow: 0 0 0 0 rgba(89,217,138,0.55); }}
      70%  {{ box-shadow: 0 0 0 6px rgba(89,217,138,0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(89,217,138,0); }}
    }}

    .stub-note {{
      font-size: 0.78em;
      color: var(--muted);
      background: var(--amber-soft);
      border: 1px solid #f0d9ae;
      padding: 8px 12px;
      border-radius: 10px;
      margin-top: 10px;
    }}
    .stub-note code {{ font-family: var(--mono); background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 4px; }}

    /* ---------- Quick queries ---------- */
    .eyebrow {{
      font-family: var(--mono);
      font-size: 0.68em;
      letter-spacing: 0.1em;
      color: var(--muted);
      margin: 18px 2px 8px;
      text-transform: uppercase;
    }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{
      display: inline-flex; align-items: center; gap: 7px;
      background: var(--panel);
      color: var(--ink-soft);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 8px 14px 8px 12px;
      font-size: 0.83em;
      cursor: pointer;
      transition: border-color 0.15s ease, background 0.15s ease, transform 0.1s ease;
    }}
    .chip-icon {{ display: flex; color: var(--green); flex-shrink: 0; }}
    .chip:hover {{ border-color: var(--green); background: var(--green-soft); }}
    .chip:active {{ transform: scale(0.98); }}
    .chip:disabled {{ opacity: 0.45; cursor: not-allowed; transform: none; }}

    /* ---------- Log ---------- */
    #log {{
      flex: 1;
      min-height: 340px;
      overflow-y: auto;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 18px;
      margin: 14px 0;
      background: var(--panel);
      display: flex;
      flex-direction: column;
    }}
    .empty-state {{
      margin: auto;
      text-align: center;
      color: var(--muted);
      max-width: 320px;
    }}
    .empty-state .glyph {{ font-size: 1.6em; margin-bottom: 6px; }}
    .empty-state p {{ font-size: 0.85em; line-height: 1.5; margin: 4px 0 0; }}

    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .bubble-row {{ display: flex; margin-bottom: 16px; align-items: flex-start; gap: 10px; animation: rise 0.25s ease; }}
    .bubble-row.user {{ flex-direction: row-reverse; }}
    .avatar {{
      width: 30px; height: 30px; border-radius: 9px;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.95em; flex-shrink: 0;
    }}
    .avatar.ai {{ background: var(--green-soft); }}
    .avatar.user {{ background: var(--soil-soft); }}
    .bubble-col {{ display: flex; flex-direction: column; max-width: 78%; }}
    .bubble-row.user .bubble-col {{ align-items: flex-end; }}
    .bubble {{
      padding: 10px 14px;
      border-radius: 14px;
      line-height: 1.45;
      font-size: 0.92em;
    }}
    .bubble.ai {{ background: var(--green-soft); color: var(--ink-soft); border-top-left-radius: 4px; }}
    .bubble.user {{ background: var(--soil-soft); color: var(--ink-soft); border-top-right-radius: 4px; }}

    /* ---------- Tool-call log (signature element) ---------- */
    .tool-log {{
      margin-top: 6px;
      background: var(--ink);
      border-left: 3px solid var(--green);
      border-radius: 8px;
      padding: 7px 10px;
      font-family: var(--mono);
      font-size: 0.72em;
      color: #a9c9b3;
      animation: rise 0.3s ease;
    }}
    .tool-log .tl-label {{
      color: #6f8a79;
      letter-spacing: 0.08em;
      font-size: 0.85em;
      margin-bottom: 3px;
      display: block;
    }}
    .tool-log .tl-item {{ display: flex; align-items: center; gap: 6px; padding: 1px 0; }}
    .tool-log .tl-item::before {{ content: "▸"; color: var(--green); }}

    .typing-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
    .typing-dots {{ display: flex; gap: 4px; background: var(--green-soft); padding: 10px 14px; border-radius: 14px; border-top-left-radius: 4px; }}
    .typing-dots span {{
      width: 6px; height: 6px; border-radius: 50%; background: var(--green);
      animation: bounce 1.1s infinite ease-in-out;
    }}
    .typing-dots span:nth-child(2) {{ animation-delay: 0.15s; }}
    .typing-dots span:nth-child(3) {{ animation-delay: 0.3s; }}
    @keyframes bounce {{
      0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }}
      30% {{ transform: translateY(-4px); opacity: 1; }}
    }}

    /* ---------- Input ---------- */
    .input-row {{ display: flex; gap: 8px; }}
    #question {{
      flex: 1;
      padding: 13px 16px;
      font-size: 0.95em;
      font-family: var(--sans);
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
    }}
    #question:focus {{ outline: none; border-color: var(--green); box-shadow: 0 0 0 3px rgba(47,107,73,0.12); }}
    #sendBtn {{
      width: 46px; height: 46px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      background: var(--ink);
      color: white;
      border: none;
      border-radius: 50%;
      cursor: pointer;
      transition: background 0.15s ease, transform 0.1s ease;
    }}
    #sendBtn:hover:not(:disabled) {{ background: var(--green-deep); }}
    #sendBtn:active:not(:disabled) {{ transform: scale(0.94); }}
    #sendBtn:disabled {{ background: #b7c2bb; cursor: not-allowed; }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ animation: none !important; transition: none !important; }}
    }}
    @media (max-width: 480px) {{
      .bubble-col {{ max-width: 88%; }}
      header {{ flex-wrap: wrap; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <div class="brand-mark">🌿</div>
        <div class="brand-text">
          <h1>AgriTwin</h1>
          <p>Greenhouse monitoring assistant</p>
        </div>
      </div>
      <div class="status-pill {status_class}">
        <span class="dot"></span><span>{status_label}</span>
      </div>
    </header>
    {stub_note}

    <div class="eyebrow">Quick queries</div>
    <div class="chips" id="chips">
      {chips_html}
    </div>

    <div id="log">
      <div class="empty-state" id="emptyState">
        <div class="glyph">🌱</div>
        <p>Ask about the greenhouse, or click a quick query above.<br>
        Every answer shows exactly which sensor/tool it checked.</p>
      </div>
    </div>

    <div class="input-row">
      <input id="question" placeholder="Ask about temperature, ventilation, or crop status…" autocomplete="off" />
      <button id="sendBtn" onclick="send()" aria-label="Send message">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <line x1="17" y1="3" x2="3" y2="10.5"/><polygon points="17,3 11,17 8,11 3,10.5" fill="currentColor" stroke="none"/>
        </svg>
      </button>
    </div>
  </div>

  <script>
    let waiting = false;

    function toolLogHtml(tools) {{
      if (!tools || tools.length === 0) return '';
      const items = tools.map(t => `<div class="tl-item">${{t}}</div>`).join('');
      return `<div class="tool-log"><span class="tl-label">GROUNDED ON</span>${{items}}</div>`;
    }}

    function clearEmptyState() {{
      const el = document.getElementById('emptyState');
      if (el) el.remove();
    }}

    function addBubble(role, text, tools) {{
      clearEmptyState();
      const log = document.getElementById('log');
      const row = document.createElement('div');
      row.className = 'bubble-row ' + role;
      const avatar = role === 'user' ? '🧑' : '🌿';
      row.innerHTML = `
        <div class="avatar ${{role}}">${{avatar}}</div>
        <div class="bubble-col">
          <div class="bubble ${{role}}">${{text}}</div>
          ${{role === 'ai' ? toolLogHtml(tools) : ''}}
        </div>`;
      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
      return row;
    }}

    function setWaiting(isWaiting) {{
      waiting = isWaiting;
      document.getElementById('sendBtn').disabled = isWaiting;
      document.getElementById('question').disabled = isWaiting;
      document.querySelectorAll('.chip').forEach(c => c.disabled = isWaiting);
    }}

    async function ask(question) {{
      if (!question || waiting) return;
      clearEmptyState();
      addBubble('user', question);
      setWaiting(true);

      const log = document.getElementById('log');
      const typingRow = document.createElement('div');
      typingRow.className = 'typing-row';
      typingRow.id = 'typingIndicator';
      typingRow.innerHTML = `
        <div class="avatar ai">🌿</div>
        <div class="typing-dots"><span></span><span></span><span></span></div>`;
      log.appendChild(typingRow);
      log.scrollTop = log.scrollHeight;

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{message: question}})
        }});
        const data = await res.json();
        document.getElementById('typingIndicator')?.remove();
        addBubble('ai', data.reply, data.tools_called);
      }} catch (e) {{
        document.getElementById('typingIndicator')?.remove();
        addBubble('ai', 'Connection issue — try again.', []);
      }}
      setWaiting(false);
    }}

    function send() {{
      const input = document.getElementById('question');
      const question = input.value.trim();
      input.value = '';
      ask(question);
    }}

    function sendPreset(question) {{
      ask(question);
    }}

    document.getElementById('question').addEventListener('keydown', e => {{
      if (e.key === 'Enter') send();
    }});
  </script>
</body>
</html>
"""