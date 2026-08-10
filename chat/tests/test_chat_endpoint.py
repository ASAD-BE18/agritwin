"""
Covers the /api/chat route's failure handling directly (calling the route
function itself, not through TestClient/ASGI lifespan -- USE_REAL_AGENT also
gates lifespan's real MCP subprocess startup, which this test has no need to
spin up just to check the error-handling branch).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chat_app  # noqa: E402


def test_chat_endpoint_degrades_gracefully_when_real_agent_fails(monkeypatch):
    """Matches Implementation_Plan.md §6's failure drill: killing the LLM API
    must degrade the UI cleanly, not throw a raw 500."""
    monkeypatch.setattr(chat_app, "USE_REAL_AGENT", True)

    async def failing_agent(question):
        raise RuntimeError("simulated API outage")

    monkeypatch.setattr(chat_app, "call_agent_real", failing_agent)

    result = asyncio.run(chat_app.chat(chat_app.ChatRequest(message="Is it too hot?")))

    assert result["tools_called"] == []
    assert "unavailable" in result["reply"].lower()
    assert "simulated API outage" in result["reply"]


def test_chat_endpoint_stub_mode_unaffected_by_real_agent_errors(monkeypatch):
    """Stub mode must never even look at call_agent_real -- if it did, a
    broken real-agent implementation could break the stub demo path too."""
    monkeypatch.setattr(chat_app, "USE_REAL_AGENT", False)

    async def exploding_agent(question):
        raise AssertionError("stub mode must not call call_agent_real")

    monkeypatch.setattr(chat_app, "call_agent_real", exploding_agent)

    result = asyncio.run(chat_app.chat(chat_app.ChatRequest(message="Is it too hot?")))
    assert result["tools_called"]
