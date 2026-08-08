# AgriTwin — Your Task Brief

**For:** Tayyaba Fatima
**Your area:** Mock Data, Chat UI, Automated Tests
**Project:** AgriTwin — a small greenhouse rig (sensor + heater + fan) that a laptop watches over, and that people can ask questions about in plain English.

---

## The 30-second version of the whole project

A temperature sensor sits in a small greenhouse box, wired to an Arduino that controls a fan and a heater. A laptop backend (built by Asad) reads that data continuously. On top of that, an AI (Claude) can answer questions like "is it too hot in there?" — but only by actually looking up the real number through a defined set of tools, never by guessing. **Your job covers three pieces that make that provable and demoable.**

## Piece 1 — the mock data generator

Before real hardware exists, the whole team needs *something* realistic to build against. You're writing a small Python script that generates a fake 30-minute greenhouse temperature log:

- Normal slow drift (ambient temperature wandering a little).
- A period where the heater is on and temperature ramps up.
- A period where the fan kicks in and it cools back down.
- **One spike above 30°C** somewhere in there — this matters because the "is my crop stressed" feature needs at least one moment where it has something interesting to flag.

Save it as a CSV file that replays the exact same way every time it's run — that predictability is what makes it useful both for development and for a reliable demo (nobody wants the demo to randomly not have an interesting moment happen).

## Piece 2 — the chat UI

A simple web page where someone types a question (e.g. "is it too hot right now?") and gets an answer back from the AI. Use whatever's fastest for you — a small FastAPI + HTMX page, or Streamlit if you're more comfortable there.

**The one thing that matters most here:** every time the AI calls one of its tools (e.g., checking the current temperature), show a visible little badge or chip on screen saying so — like *"called get_current_conditions."* This is the single most convincing thing in the whole demo, because it visibly proves the AI is checking real data instead of making something up. Prioritize that over making the page look polished.

You'll wire this up to Asad's tool-calling code once he has it ready (`twin_tools.py`) — check with him on timing, but you can build the page's layout and styling before that's ready.

## Piece 3 — automated tests for 5 specific questions

Write a test script that asks the AI these exact 5 questions and checks it calls the *right* tool for each one:

1. *"Is it too hot for the crop right now?"* → should check current conditions + crop stress
2. *"What was the peak temperature in the last hour?"* → should check historical data
3. *"Should I increase ventilation?"* → should check both stress and current conditions
4. *"Set the fan to 80%."* → should actually call the fan-control tool
5. *"Is the sensor working?"* → should check system health

This test suite **is** the project's proof that the AI is properly "grounded" — it's more convincing to say "we tested this and it passes" than to just claim it works.

## What you can start on immediately (no dependency)

The mock data generator and the test scaffolding don't need anything from anyone else — start there first.

## What you're waiting on

- **Asad's `twin_tools.py`** (the shared functions the AI's tools call) — needed before the chat UI can actually talk to the AI, and before the 5-question tests can run for real. Build the UI layout and the test *questions* in the meantime; wire them up once he's ready.

## How you'll know it's done

- [ ] Mock CSV replays the same realistic 30-minute profile every time, includes one >30°C spike.
- [ ] Chat UI answers a question and visibly shows which tool(s) it called.
- [ ] All 5 test questions pass, asserting the correct tool was called each time.

## Who to talk to

- **Asad** — for `twin_tools.py` readiness and the exact tool names/schemas to test against.
