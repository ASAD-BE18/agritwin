"""
AgriTwin — Demo Chat UI
========================
Owned by: Tayyaba.

A minimal FastAPI page: type a question, get an answer, see exactly which
MCP tool(s) fired as a visible chip under the reply — the single most
convincing thing in the demo, per the brief.

Two modes, controlled by USE_REAL_AGENT (env var, default "false"):
  - stub mode:  call_agent_stub() — keyword-matched placeholder answers,
                zero dependency on mcp/mcp_server.py, for building/demoing
                the UI shell before the real tool pipeline exists.
  - real mode:  call_agent_real() — connects to mcp/mcp_server.py via stdio
                once at app startup (see lifespan()), and drives the actual
                Anthropic tool_runner loop per docs/Implementation_Plan.md
                section 2.1. This is now REAL, working code (not a stub) —
                requires mcp/mcp_server.py to exist (merged in PR #2) and
                ANTHROPIC_API_KEY to be set.

Run (stub mode, no dependencies beyond requirements.txt):
    uvicorn chat_app:app --reload --port 8001

Run (real mode, once mcp/mcp_server.py is available):
    USE_REAL_AGENT=true ANTHROPIC_API_KEY=<key> uvicorn chat_app:app --reload --port 8001

Env vars:
    USE_REAL_AGENT     "true"/"false", default false
    MCP_SERVER_CMD      command to launch mcp/mcp_server.py, default:
                         "python ../mcp/mcp_server.py" — actually read and
                         used (see lifespan() below), not just documented.
    ANTHROPIC_API_KEY   required only when USE_REAL_AGENT=true
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

# Holds the long-lived MCP client session (real mode only) so we connect
# once at startup instead of spawning mcp_server.py per request.
mcp_session = {"session": None}

# Only instantiate the Anthropic client in real mode — avoids requiring
# ANTHROPIC_API_KEY to even be set when running in stub mode.
anthropic_client = AsyncAnthropic() if USE_REAL_AGENT else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not USE_REAL_AGENT:
        yield
        return

    # MCP_SERVER_CMD is a single command string, e.g. "python ../mcp/mcp_server.py"
    # — split it into (command, args) the way StdioServerParameters expects.
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
    """
    Fake agent driven by keyword matching against the 5 REAL tool names —
    kept alongside the real implementation so the UI is still demoable with
    zero external dependencies (no API key, no mcp_server.py subprocess)
    when USE_REAL_AGENT=false. Return shape (answer, tools_called) matches
    call_agent_real() exactly, so the routes below never branch on shape.
    """
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
    """
    Real implementation per docs/Implementation_Plan.md section 2.1: connects
    to the live MCP session (established once in lifespan()), converts its
    tools into runnable Anthropic tools, and drives the tool_runner loop.
    """
    session = mcp_session["session"]
    if session is None:
        raise RuntimeError(
            "MCP session not initialized — this only runs correctly under "
            "USE_REAL_AGENT=true with the app's lifespan startup, not when "
            "called standalone without the FastAPI app having started."
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


@app.get("/", response_class=HTMLResponse)
def index():
    mode_banner = "" if USE_REAL_AGENT else (
        '<div style="background:#fff3cd;padding:8px;border-radius:6px;margin-bottom:12px;">'
        'Running in STUB mode — answers are placeholders. '
        'Set USE_REAL_AGENT=true (with ANTHROPIC_API_KEY set) to use the real agent.</div>'
    )
    return f"""
<!DOCTYPE html>
<html>
<head>
  <title>AgriTwin Chat</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 16px; }}
    #log {{ min-height: 300px; border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
    .msg {{ margin-bottom: 14px; }}
    .user {{ font-weight: bold; }}
    input {{ width: 78%; padding: 10px; font-size: 1em; }}
    button {{ padding: 10px 16px; font-size: 1em; }}
  </style>
</head>
<body>
  <h2>🌱 AgriTwin — Ask about the greenhouse</h2>
  {mode_banner}
  <div id="log"></div>
  <input id="question" placeholder="e.g. Is it too hot for the crop right now?" />
  <button onclick="send()">Send</button>

  <script>
    async function send() {{
      const input = document.getElementById('question');
      const question = input.value.trim();
      if (!question) return;
      input.value = '';

      const log = document.getElementById('log');
      log.innerHTML += `<div class="msg user">You: ${{question}}</div>`;

      const res = await fetch('/api/chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{message: question}})
      }});
      const data = await res.json();

      const chips = data.tools_called.map(t =>
        `<span style="background:#1F4E79;color:white;padding:4px 10px;border-radius:12px;
         margin-right:6px;font-size:0.85em;display:inline-block;margin-top:4px;">
         🔧 called ${{t}}</span>`
      ).join('');

      log.innerHTML += `<div class="msg">AgriTwin: ${{data.reply}}<br/>${{chips}}</div>`;
      log.scrollTop = log.scrollHeight;
    }}
    document.getElementById('question').addEventListener('keydown', e => {{
      if (e.key === 'Enter') send();
    }});
  </script>
</body>
</html>
"""
