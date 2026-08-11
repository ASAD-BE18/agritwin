"""
AgriTwin — Demo Chat UI (v4: Urdu language support + voice input)
=============================================================

What changed from v3:
  - Language toggle (EN / اردو). Server-renders the whole page in the
    selected language via a `?lang=` query param — simplest reliable way
    to swap UI strings, direction, and font without a JS templating layer.
  - Urdu text uses `direction: rtl` on text-bearing containers (not a
    full-page `dir="rtl"` flip) to avoid fighting the existing flex
    row/row-reverse bubble layout. Font stack falls back through common
    Arabic-script fonts already installed on most systems — no font CDN,
    same offline-demo reasoning as v3's system-font choice.
  - Voice input: a mic button next to the text input uses the browser's
    built-in SpeechRecognition API, language-matched to the toggle
    (ur-PK / en-US). Transcribed text fills the input box for review —
    NOT auto-sent — since STT accuracy for Urdu can be inconsistent and a
    farmer (or you, live) should be able to glance at it before sending.

    IMPORTANT CAVEAT, worth rehearsing around: browser SpeechRecognition
    is cloud-based (audio is sent to Google's servers to transcribe) even
    though it feels local — it needs real internet, not just a LAN, and
    only works in Chromium-based browsers (Chrome/Edge), not Firefox/
    Safari. If venue wifi is unreliable, this is the least dependable
    part of the demo. The Urdu quick-query chips are your offline-safe
    fallback — same idea as the project's existing "fallback Q&A cache."
  - ChatRequest now carries `lang`; call_agent_real appends a one-line
    language instruction to the grounding prompt; call_agent_stub has
    matching Urdu placeholder text. Tool names in the "grounded on" log
    stay in English deliberately — they're technical identifiers.

The MCP side follows docs/Implementation_Plan.md section 2.1 (same
mcp/mcp_server.py drives this and Claude Desktop/Code); the model call goes
through OpenRouter (OpenAI-compatible API) instead of a direct Anthropic key,
using the free "openrouter/free" router model since no Anthropic key is
available for this project.

Run:
    uvicorn chat_app:app --reload --port 8001
Env vars:
    USE_REAL_AGENT      "true"/"false", default false
    MCP_SERVER_CMD       command to launch mcp/mcp_server.py, default:
                          "<this process's own interpreter> <repo>/mcp/mcp_server.py"
                          -- both resolved from this file's own location/venv,
                          not the process's cwd or whatever "python" is on PATH
    OPENROUTER_API_KEY   required only when USE_REAL_AGENT=true
    OPENROUTER_MODEL      OpenRouter model slug, default "openrouter/free"
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

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

# Both pieces resolved from this process's own state, not assumed:
#   - the script path is relative to this file's location, not the process's
#     cwd (a hardcoded "../mcp/mcp_server.py" would break the moment uvicorn
#     is launched from anywhere other than this exact directory);
#   - the interpreter is sys.executable (this venv), not a bare "python" --
#     that resolves via PATH and can silently pick a different Python with
#     none of this project's dependencies installed (found by testing this:
#     it picked a system Python missing python-dotenv).
_DEFAULT_MCP_SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp" / "mcp_server.py"
MCP_SERVER_CMD = os.environ.get("MCP_SERVER_CMD", f"{sys.executable} {_DEFAULT_MCP_SERVER_PATH}")

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
MAX_TOOL_ITERATIONS = 8

# Holds the long-lived MCP client session (only used in real mode) so we
# connect once at startup instead of spawning mcp_server.py per request.
mcp_session = {"session": None}

LANGUAGE_NAMES = {"en": "English", "ur": "Urdu"}

# ---------------------------------------------------------------------------
# Suggested queries — (english, urdu, icon_key). Both language versions are
# real, reviewed translations of the brief's 5 required test questions, not
# machine-translated on the fly, so the "known-good phrasing" guarantee from
# v2 still holds in either language.
# ---------------------------------------------------------------------------
SUGGESTED_QUERIES = [
    ("Is it too hot for the crop right now?", "کیا ابھی فصل کے لیے بہت گرمی ہے؟", "thermometer"),
    ("What was the peak temperature in the last hour?", "پچھلے ایک گھنٹے میں سب سے زیادہ درجہ حرارت کیا تھا؟", "history"),
    ("Should I increase ventilation?", "کیا مجھے ہوا کی گردش بڑھانی چاہیے؟", "wind"),
    ("Set the fan to 80%.", "پنکھا 80 فیصد پر سیٹ کریں۔", "sliders"),
    ("Is the sensor working?", "کیا سینسر کام کر رہا ہے؟", "pulse"),
]

UI = {
    "en": {
        "subtitle": "Greenhouse monitoring assistant",
        "live": "LIVE AGENT",
        "stub": "STUB MODE",
        "stub_note": 'Running with placeholder answers — set <code>USE_REAL_AGENT=true</code> to connect the real agent.',
        "eyebrow": "Quick queries",
        "empty_glyph_line": "Ask about the greenhouse, or click a quick query above.<br>Every answer shows exactly which sensor/tool it checked.",
        "placeholder": "Ask about temperature, ventilation, or crop status…",
        "grounded_on": "GROUNDED ON",
        "connection_issue": "Connection issue — try again.",
        "mic_aria": "Record a voice question",
        "send_aria": "Send message",
        "lang_toggle_label": "EN",
    },
    "ur": {
        "subtitle": "گرین ہاؤس مانیٹرنگ اسسٹنٹ",
        "live": "لائیو ایجنٹ",
        "stub": "ٹیسٹ موڈ",
        "stub_note": 'فی الحال نمائشی جوابات دکھائے جا رہے ہیں — اصل ایجنٹ سے جوڑنے کے لیے <code>USE_REAL_AGENT=true</code> سیٹ کریں۔',
        "eyebrow": "فوری سوالات",
        "empty_glyph_line": "گرین ہاؤس کے بارے میں پوچھیں، یا اوپر دیے گئے سوالات میں سے کوئی منتخب کریں۔<br>ہر جواب یہ ظاہر کرتا ہے کہ اس نے کون سا سینسر یا ٹول چیک کیا۔",
        "placeholder": "درجہ حرارت، ہوا کی گردش، یا فصل کی حالت کے بارے میں پوچھیں…",
        "grounded_on": "ان ٹولز پر مبنی",
        "connection_issue": "رابطے میں مسئلہ — دوبارہ کوشش کریں۔",
        "mic_aria": "آواز سے سوال ریکارڈ کریں",
        "send_aria": "پیغام بھیجیں",
        "lang_toggle_label": "اردو",
    },
}

# Stub-mode placeholder answers, matched by language. Keys correspond to the
# same routing logic as before, just duplicated per language.
STUB_ANSWERS = {
    "en": {
        "peak": "(stub) Peak temperature in the last hour was 31.2°C.",
        "ventilation": "(stub) Conditions are trending warm — yes, increasing ventilation is reasonable.",
        "set_fan": "(stub) Fan speed has been set as requested.",
        "sensor": "(stub) Sensor is reporting fresh data, last update 2 seconds ago.",
        "default": "(stub) Current temperature is within a safe range for the crop.",
    },
    "ur": {
        "peak": "(نمائشی) پچھلے ایک گھنٹے میں سب سے زیادہ درجہ حرارت 31.2°C تھا۔",
        "ventilation": "(نمائشی) حالات گرم ہوتے جا رہے ہیں — جی ہاں، ہوا کی گردش بڑھانا مناسب ہے۔",
        "set_fan": "(نمائشی) پنکھے کی رفتار درخواست کے مطابق سیٹ کر دی گئی ہے۔",
        "sensor": "(نمائشی) سینسر تازہ ڈیٹا بھیج رہا ہے، آخری اپڈیٹ 2 سیکنڈ پہلے۔",
        "default": "(نمائشی) موجودہ درجہ حرارت فصل کے لیے محفوظ حد میں ہے۔",
    },
}

# Only instantiate in real mode -- avoids requiring OPENROUTER_API_KEY to even
# be set when running in stub mode.
openrouter_client = (
    AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ.get("OPENROUTER_API_KEY"))
    if USE_REAL_AGENT
    else None
)


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
    lang: str = "en"  # "en" or "ur"


def call_agent_stub(question: str, lang: str):
    q = question.lower()
    answers = STUB_ANSWERS.get(lang, STUB_ANSWERS["en"])
    # Routing still keys off English keywords AND their Urdu equivalents,
    # so stub mode responds sensibly regardless of which language the
    # question itself was typed/spoken in.
    if "peak" in q or "last hour" in q or "history" in q or "زیادہ درجہ حرارت" in q:
        return answers["peak"], [GET_HISTORICAL_RANGE]
    if "ventilation" in q or "increase" in q or "ہوا کی گردش" in q:
        return answers["ventilation"], [PREDICT_CROP_STRESS, GET_CURRENT_CONDITIONS]
    if "set the fan" in q or "set fan" in q or "پنکھا" in q:
        return answers["set_fan"], [SET_VENTILATION_LEVEL]
    if "sensor" in q or "working" in q or "سینسر" in q:
        return answers["sensor"], [GET_SYSTEM_HEALTH]
    return answers["default"], [GET_CURRENT_CONDITIONS, PREDICT_CROP_STRESS]


async def call_agent_real(question: str, lang: str):
    """
    Follows docs/Implementation_Plan.md section 2.1 on the MCP side: the same
    MCP server (mcp/mcp_server.py, spawned once at startup by lifespan())
    drives both this chat UI and Claude Desktop/Code.

    The model call itself goes through OpenRouter's OpenAI-compatible chat
    completions API rather than Anthropic's tool_runner -- tool_runner is an
    Anthropic-SDK-specific helper with no OpenRouter equivalent, so the same
    "offer tools, execute what the model calls, feed results back" loop is
    driven by hand here instead.
    """
    session = mcp_session["session"]
    if session is None:
        raise RuntimeError(
            "MCP session not initialized — this only runs correctly under "
            "USE_REAL_AGENT=true with the app's lifespan startup."
        )

    mcp_tools = (await session.list_tools()).tools
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in mcp_tools
    ]

    system_prompt = GROUNDING_SYSTEM_PROMPT
    if lang != "en":
        lang_name = LANGUAGE_NAMES.get(lang, lang)
        system_prompt += f" Respond in {lang_name}, regardless of the language of the tool data."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    tools_called = []
    for _ in range(MAX_TOOL_ITERATIONS):
        response = await openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            tools=openai_tools,
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content or "", tools_called

        messages.append(message.model_dump(exclude_unset=True))
        for call in message.tool_calls:
            tools_called.append(call.function.name)
            args = json.loads(call.function.arguments or "{}")
            result = await session.call_tool(call.function.name, args)
            result_text = "".join(
                block.text for block in result.content if getattr(block, "type", None) == "text"
            )
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result_text,
            })

    raise RuntimeError(f"exceeded {MAX_TOOL_ITERATIONS} tool-call iterations without a final answer")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    lang = req.lang if req.lang in ("en", "ur") else "en"
    if not USE_REAL_AGENT:
        answer, tools_called = call_agent_stub(req.message, lang)
        return {"reply": answer, "tools_called": tools_called}

    try:
        answer, tools_called = await call_agent_real(req.message, lang)
    except Exception as exc:
        # Matches the plan's own failure-drill requirement (Implementation_Plan.md
        # §6): "kill the LLM API -- does the UI degrade cleanly, or throw?" A raw
        # 500 here would fail that drill. Per the grounding system prompt's own
        # rule ("if a tool fails, say so -- do not estimate"), say so rather than
        # returning a fabricated answer.
        return {
            "reply": f"(unavailable) Could not reach the AI service: {exc}",
            "tools_called": [],
        }
    return {"reply": answer, "tools_called": tools_called}


ICONS = {
    "thermometer": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="7" y="2" width="4" height="9" rx="2"/><circle cx="9" cy="13.5" r="2.5"/><line x1="9" y1="4" x2="9" y2="10.5"/></svg>',
    "history": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="9.5" r="6.5"/><polyline points="9,6 9,9.5 12,11.5"/></svg>',
    "wind": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2 6h9a2 2 0 1 0-2-2"/><path d="M2 10.5h11a2 2 0 1 1-2 2"/><path d="M2 15h7a2 2 0 1 0-2-2"/></svg>',
    "sliders": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="4" y1="3" x2="4" y2="15"/><circle cx="4" cy="7" r="1.8"/><line x1="9" y1="3" x2="9" y2="15"/><circle cx="9" cy="11" r="1.8"/><line x1="14" y1="3" x2="14" y2="15"/><circle cx="14" cy="6" r="1.8"/></svg>',
    "pulse": '<svg viewBox="0 0 18 18" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,9.5 5,9.5 6.5,5 9.5,14 11,9.5 16,9.5"/></svg>',
}


@app.get("/", response_class=HTMLResponse)
def index(lang: str = Query("en")):
    lang = lang if lang in ("en", "ur") else "en"
    t = UI[lang]
    is_urdu = lang == "ur"

    status_label = t["live"] if USE_REAL_AGENT else t["stub"]
    status_class = "live" if USE_REAL_AGENT else "stub"
    stub_note = "" if USE_REAL_AGENT else f'<div class="stub-note{" urdu-text" if is_urdu else ""}">{t["stub_note"]}</div>'

    chips_html = "".join(
        f'<button class="chip" onclick="sendPreset({(ur if is_urdu else en)!r})">'
        f'<span class="chip-icon">{ICONS.get(icon_key, "")}</span>'
        f'<span class="{"urdu-text" if is_urdu else ""}">{ur if is_urdu else en}</span></button>'
        for en, ur, icon_key in SUGGESTED_QUERIES
    )

    speech_recognition_lang = "ur-PK" if is_urdu else "en-US"

    return f"""
<!DOCTYPE html>
<html lang="{lang}">
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
      --urdu: 'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', 'Segoe UI', Tahoma, Arial, sans-serif;
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
    .app {{ width: 100%; max-width: 760px; padding: 20px 18px 28px; display: flex; flex-direction: column; min-height: 100vh; }}

    .urdu-text {{ font-family: var(--urdu); direction: rtl; text-align: right; unicode-bidi: plaintext; line-height: 1.9; }}

    header {{ background: var(--ink); border-radius: var(--radius); padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #eef4ef; flex-wrap: wrap; }}
    .brand {{ display: flex; align-items: center; gap: 10px; }}
    .brand-mark {{ width: 34px; height: 34px; border-radius: 9px; background: linear-gradient(155deg, var(--green) 0%, var(--green-deep) 100%); display: flex; align-items: center; justify-content: center; font-size: 1.05em; flex-shrink: 0; }}
    .brand-text h1 {{ font-size: 1.05em; margin: 0; letter-spacing: 0.01em; font-weight: 650; }}
    .brand-text p {{ margin: 1px 0 0; font-size: 0.74em; color: #9db3a6; }}

    .header-right {{ display: flex; align-items: center; gap: 8px; }}
    .lang-toggle {{ display: flex; border: 1px solid rgba(255,255,255,0.16); border-radius: 20px; overflow: hidden; }}
    .lang-toggle a {{ padding: 6px 12px; font-size: 0.75em; color: #cfe0d5; text-decoration: none; font-family: var(--mono); }}
    .lang-toggle a.active {{ background: var(--green); color: white; }}

    .status-pill {{ display: flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 0.68em; letter-spacing: 0.06em; padding: 6px 10px; border-radius: 20px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); white-space: nowrap; }}
    .dot {{ width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }}
    .status-pill.live .dot {{ background: #59d98a; animation: pulse 2s infinite; }}
    .status-pill.stub .dot {{ background: var(--amber); }}
    @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(89,217,138,0.55); }} 70% {{ box-shadow: 0 0 0 6px rgba(89,217,138,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(89,217,138,0); }} }}

    .stub-note {{ font-size: 0.78em; color: var(--muted); background: var(--amber-soft); border: 1px solid #f0d9ae; padding: 8px 12px; border-radius: 10px; margin-top: 10px; }}
    .stub-note code {{ font-family: var(--mono); background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 4px; direction: ltr; unicode-bidi: embed; display: inline-block; }}

    .eyebrow {{ font-family: var(--mono); font-size: 0.68em; letter-spacing: 0.1em; color: var(--muted); margin: 18px 2px 8px; text-transform: uppercase; }}
    .eyebrow.urdu-text {{ font-family: var(--urdu); letter-spacing: normal; text-transform: none; font-size: 0.85em; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ display: inline-flex; align-items: center; gap: 7px; background: var(--panel); color: var(--ink-soft); border: 1px solid var(--line); border-radius: 20px; padding: 8px 14px 8px 12px; font-size: 0.83em; cursor: pointer; transition: border-color 0.15s ease, background 0.15s ease, transform 0.1s ease; }}
    .chip-icon {{ display: flex; color: var(--green); flex-shrink: 0; }}
    .chip:hover {{ border-color: var(--green); background: var(--green-soft); }}
    .chip:active {{ transform: scale(0.98); }}
    .chip:disabled {{ opacity: 0.45; cursor: not-allowed; transform: none; }}

    #log {{ flex: 1; min-height: 340px; overflow-y: auto; border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; margin: 14px 0; background: var(--panel); display: flex; flex-direction: column; }}
    .empty-state {{ margin: auto; text-align: center; color: var(--muted); max-width: 340px; }}
    .empty-state .glyph {{ font-size: 1.6em; margin-bottom: 6px; }}
    .empty-state p {{ font-size: 0.85em; line-height: 1.5; margin: 4px 0 0; }}

    @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    .bubble-row {{ display: flex; margin-bottom: 16px; align-items: flex-start; gap: 10px; animation: rise 0.25s ease; }}
    .bubble-row.user {{ flex-direction: row-reverse; }}
    .avatar {{ width: 30px; height: 30px; border-radius: 9px; display: flex; align-items: center; justify-content: center; font-size: 0.95em; flex-shrink: 0; }}
    .avatar.ai {{ background: var(--green-soft); }}
    .avatar.user {{ background: var(--soil-soft); }}
    .bubble-col {{ display: flex; flex-direction: column; max-width: 78%; }}
    .bubble-row.user .bubble-col {{ align-items: flex-end; }}
    .bubble {{ padding: 10px 14px; border-radius: 14px; line-height: 1.45; font-size: 0.92em; }}
    .bubble.ai {{ background: var(--green-soft); color: var(--ink-soft); border-top-left-radius: 4px; }}
    .bubble.user {{ background: var(--soil-soft); color: var(--ink-soft); border-top-right-radius: 4px; }}

    .tool-log {{ margin-top: 6px; background: var(--ink); border-left: 3px solid var(--green); border-radius: 8px; padding: 7px 10px; font-family: var(--mono); font-size: 0.72em; color: #a9c9b3; animation: rise 0.3s ease; direction: ltr; text-align: left; }}
    .tool-log .tl-label {{ color: #6f8a79; letter-spacing: 0.08em; font-size: 0.85em; margin-bottom: 3px; display: block; }}
    .tool-log .tl-label.urdu-text {{ font-family: var(--mono); direction: ltr; text-align: left; letter-spacing: 0.08em; }}
    .tool-log .tl-item {{ display: flex; align-items: center; gap: 6px; padding: 1px 0; }}
    .tool-log .tl-item::before {{ content: "▸"; color: var(--green); }}

    .typing-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
    .typing-dots {{ display: flex; gap: 4px; background: var(--green-soft); padding: 10px 14px; border-radius: 14px; border-top-left-radius: 4px; }}
    .typing-dots span {{ width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: bounce 1.1s infinite ease-in-out; }}
    .typing-dots span:nth-child(2) {{ animation-delay: 0.15s; }}
    .typing-dots span:nth-child(3) {{ animation-delay: 0.3s; }}
    @keyframes bounce {{ 0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }} 30% {{ transform: translateY(-4px); opacity: 1; }} }}

    .input-row {{ display: flex; gap: 8px; }}
    #question {{ flex: 1; padding: 13px 16px; font-size: 0.95em; font-family: var(--sans); border: 1px solid var(--line); border-radius: 24px; background: var(--panel); }}
    #question.urdu-text {{ font-family: var(--urdu); font-size: 1em; }}
    #question:focus {{ outline: none; border-color: var(--green); box-shadow: 0 0 0 3px rgba(47,107,73,0.12); }}

    #micBtn, #sendBtn {{ width: 46px; height: 46px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border: none; border-radius: 50%; cursor: pointer; transition: background 0.15s ease, transform 0.1s ease; }}
    #sendBtn {{ background: var(--ink); color: white; }}
    #sendBtn:hover:not(:disabled) {{ background: var(--green-deep); }}
    #sendBtn:active:not(:disabled) {{ transform: scale(0.94); }}
    #sendBtn:disabled {{ background: #b7c2bb; cursor: not-allowed; }}
    #micBtn {{ background: var(--panel); color: var(--ink-soft); border: 1px solid var(--line); }}
    #micBtn:hover:not(:disabled) {{ border-color: var(--amber); color: var(--amber); }}
    #micBtn.recording {{ background: var(--danger); color: white; border-color: var(--danger); animation: pulse 1.2s infinite; }}
    #micBtn:disabled {{ opacity: 0.35; cursor: not-allowed; }}
    #micUnsupported {{ font-size: 0.7em; color: var(--muted); text-align: center; margin-top: 6px; display: none; }}

    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation: none !important; transition: none !important; }} }}
    @media (max-width: 480px) {{ .bubble-col {{ max-width: 88%; }} header {{ flex-wrap: wrap; }} }}
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <div class="brand-mark">🌿</div>
        <div class="brand-text">
          <h1>AgriTwin</h1>
          <p class="{"urdu-text" if is_urdu else ""}">{t["subtitle"]}</p>
        </div>
      </div>
      <div class="header-right">
        <div class="lang-toggle">
          <a href="/?lang=en" class="{'active' if lang == 'en' else ''}">EN</a>
          <a href="/?lang=ur" class="{'active' if lang == 'ur' else ''}">اردو</a>
        </div>
        <div class="status-pill {status_class}"><span class="dot"></span><span>{status_label}</span></div>
      </div>
    </header>
    {stub_note}

    <div class="eyebrow{' urdu-text' if is_urdu else ''}">{t["eyebrow"]}</div>
    <div class="chips" id="chips">
      {chips_html}
    </div>

    <div id="log">
      <div class="empty-state" id="emptyState">
        <div class="glyph">🌱</div>
        <p class="{"urdu-text" if is_urdu else ""}">{t["empty_glyph_line"]}</p>
      </div>
    </div>

    <div class="input-row">
      <input id="question" class="{"urdu-text" if is_urdu else ""}" placeholder="{t['placeholder']}" autocomplete="off" dir="{'rtl' if is_urdu else 'ltr'}" />
      <button id="micBtn" onclick="toggleMic()" aria-label="{t['mic_aria']}" title="{t['mic_aria']}">
        <svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <rect x="7" y="2.5" width="6" height="10" rx="3"/><path d="M4 9.5a6 6 0 0 0 12 0"/><line x1="10" y1="15.5" x2="10" y2="18"/>
        </svg>
      </button>
      <button id="sendBtn" onclick="send()" aria-label="{t['send_aria']}">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <line x1="17" y1="3" x2="3" y2="10.5"/><polygon points="17,3 11,17 8,11 3,10.5" fill="currentColor" stroke="none"/>
        </svg>
      </button>
    </div>
    <div id="micUnsupported">Voice input needs Chrome or Edge, and an internet connection.</div>
  </div>

  <script>
    let waiting = false;
    const PAGE_LANG = "{lang}";
    const IS_URDU = {str(is_urdu).lower()};
    const GROUNDED_ON_LABEL = {t["grounded_on"]!r};
    const CONNECTION_ISSUE_TEXT = {t["connection_issue"]!r};

    function toolLogHtml(tools) {{
      if (!tools || tools.length === 0) return '';
      const items = tools.map(x => `<div class="tl-item">${{x}}</div>`).join('');
      return `<div class="tool-log"><span class="tl-label${{IS_URDU ? ' urdu-text' : ''}}">${{GROUNDED_ON_LABEL}}</span>${{items}}</div>`;
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
      const textClass = IS_URDU ? 'urdu-text' : '';
      row.innerHTML = `
        <div class="avatar ${{role}}">${{avatar}}</div>
        <div class="bubble-col">
          <div class="bubble ${{role}} ${{textClass}}">${{text}}</div>
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
      typingRow.innerHTML = `<div class="avatar ai">🌿</div><div class="typing-dots"><span></span><span></span><span></span></div>`;
      log.appendChild(typingRow);
      log.scrollTop = log.scrollHeight;

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{message: question, lang: PAGE_LANG}})
        }});
        const data = await res.json();
        document.getElementById('typingIndicator')?.remove();
        addBubble('ai', data.reply, data.tools_called);
      }} catch (e) {{
        document.getElementById('typingIndicator')?.remove();
        addBubble('ai', CONNECTION_ISSUE_TEXT, []);
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

    // --- Voice input (browser SpeechRecognition — cloud-based, needs real
    // internet + Chrome/Edge). Fills the input box for review; does not
    // auto-send. Fails silently to a disabled mic button if unsupported. ---
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    const micBtn = document.getElementById('micBtn');
    let recognizer = null;
    let recording = false;

    if (!SpeechRecognitionAPI) {{
      micBtn.disabled = true;
      document.getElementById('micUnsupported').style.display = 'block';
    }} else {{
      recognizer = new SpeechRecognitionAPI();
      recognizer.lang = "{speech_recognition_lang}";
      recognizer.interimResults = false;
      recognizer.maxAlternatives = 1;

      recognizer.onresult = (event) => {{
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById('question');
        input.value = transcript;
        input.focus();
      }};
      recognizer.onerror = () => {{ stopRecording(); }};
      recognizer.onend = () => {{ stopRecording(); }};
    }}

    function stopRecording() {{
      recording = false;
      micBtn.classList.remove('recording');
    }}

    function toggleMic() {{
      if (!recognizer || waiting) return;
      if (recording) {{
        recognizer.stop();
        stopRecording();
        return;
      }}
      recording = true;
      micBtn.classList.add('recording');
      try {{
        recognizer.start();
      }} catch (e) {{
        stopRecording();
      }}
    }}
  </script>
</body>
</html>
"""
