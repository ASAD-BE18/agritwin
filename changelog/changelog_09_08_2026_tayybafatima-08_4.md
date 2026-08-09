# Changelog — feat/tayybafatima-08/chat-ui

## What changed
Added `chat/chat_app.py` — a FastAPI page where someone types a question and
gets an answer back, with a visible badge under each reply showing exactly
which MCP tool(s) were called to produce it. Ships in stub mode today
(`USE_REAL_AGENT=false`) so the full UI is demoable before
`mcp/mcp_server.py` exists; the real async MCP tool-runner integration
(per `docs/Implementation_Plan.md` §2.1) is written and ready to enable
with a single environment variable flip once Asad's tools are live.

## Why it matters
The tool-call badges are the single most convincing thing in the whole
demo — they're the audience's visual proof that the AI is checking real
sensor data instead of guessing. Building the UI shell now, decoupled from
the real backend, means it doesn't sit on the critical path waiting for
`mcp_server.py`.

Verified: all 5 of the brief's required questions return the correct
placeholder tool call(s) end-to-end against a running instance, and the
homepage renders correctly.
