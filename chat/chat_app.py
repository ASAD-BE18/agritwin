"""
AgriTwin — Demo Chat UI
========================

A minimal FastAPI page: type a question, get an answer, see exactly which
MCP tool(s) fired as a visible chip under the reply — the single most
convincing thing in the demo, per the brief.

STATUS: ships with USE_REAL_AGENT = False (env-overridable), so the whole UI
is buildable and demoable today against `call_agent_stub`, before Asad's
mcp/mcp_server.py exists. Flip it once he's ready — see call_agent_real()
below, which already implements the exact async MCP tool_runner pattern from
docs/Implementation_Plan.md section 2.1.

Run:
    uvicorn chat_app:app --reload --port 8001
Env vars:
    USE_REAL_AGENT      "true"/"false", default false
    MCP_SERVER_CMD       command to launch mcp/mcp_server.py, default:
                          "python ../mcp/mcp_server.py"
    ANTHROPIC_API_KEY    required only when USE_REAL_AGENT=true
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from tool_names import (
    GET_CURRENT_CONDITIONS,
    GET_HISTORICAL_RANGE,
    PREDICT_CROP_STRESS,
    SET_VENTILATION_LEVEL,
    GET_SYSTEM_HEALTH,
    GROUNDING_SYSTEM_PROMPT,
)

USE_REAL_AGENT = os.environ.get("USE_REAL_AGENT", "false").lower() == "true"

# Holds the long-lived MCP client session (only used in real mode) so we
# connect once at startup instead of spawning mcp_server.py per request.
mcp_session = {"session": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if USE_REAL_AGENT:
        # ============================================================
        # Real startup — connects once, kept alive for the app's lifetime.
        # Uncomment once anthropic[mcp] is installed and mcp_server.py exists.
        # ============================================================
        # from mcp import ClientSession
        # from mcp.client.stdio import stdio_client, StdioServerParameters
        # params = StdioServerParameters(command="python", args=["../mcp/mcp_server.py"])
        # async with stdio_client(params) as (r, w):
        #     async with ClientSession(r, w) as session:
        #         await session.initialize()
        #         mcp_session["session"] = session
        #         yield
        # return
        raise RuntimeError(
            "USE_REAL_AGENT=true but the real MCP startup block is still "
            "commented out — uncomment it in chat_app.py once mcp/mcp_server.py "
            "exists and anthropic[mcp] is installed."
        )
    yield  # stub mode: nothing to start up


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


def call_agent_stub(question: str):
    """
    Fake agent driven by keyword matching against the 5 REAL tool names —
    good enough to build/demo the UI shell against today. Return shape
    (answer: str, tools_called: list[str]) is exactly what call_agent_real
    must also return, so the UI code below never has to change.
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
    ============================================================
    FILL THIS IN once mcp/mcp_server.py exists (Asad).
    ============================================================
    Follows docs/Implementation_Plan.md section 2.1 exactly:

        from anthropic import AsyncAnthropic
        from anthropic.lib.tools.mcp import async_mcp_tool

        client = AsyncAnthropic()
        session = mcp_session["session"]
        tools = (await session.list_tools()).tools

        runner = client.beta.messages.tool_runner(
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
    ============================================================
    """
    raise NotImplementedError("Wire this up once mcp/mcp_server.py is ready.")


def render_chip(name: str) -> str:
    return (
        f'<span style="background:#1F4E79;color:white;padding:4px 10px;'
        f'border-radius:12px;margin-right:6px;font-size:0.85em;display:inline-block;'
        f'margin-top:4px;">🔧 called {name}</span>'
    )


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
        'Set USE_REAL_AGENT=true once mcp/mcp_server.py is ready.</div>'
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
