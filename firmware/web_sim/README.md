# AgriTwin — Web Rig Simulator

Replaces the Wokwi-based sim build (dropped — its circuit layout/wiring kept fighting us
for no real payoff). This is a plain HTML/CSS/JS page, no build step, that stands in for
the physical rig and feeds the real backend so the rest of the stack (Unity, chat, any
dashboard) can be demoed with zero hardware.

**This is not a port of the Arduino firmware.** The safety-cutoff rule (temp ≥ 32°C →
heater off, fan 100%) is reimplemented here in JS for the demo visuals — it does not run
`firmware/common/AgriTwinCore.cpp`. If that file's `TEMP_MAX` ever changes, update
`app.js`'s `TEMP_MAX` to match. Testing the *actual* firmware's safety logic still
requires compiling and running it (real hardware, or a from-scratch Wokwi/`arduino-cli`
setup) — this page is for demoing the rest of the system, not for verifying the firmware.

## Running it

1. Start the backend (`uvicorn app.main:app` from `backend/`, or however the team runs it).
2. Open `index.html` directly in a browser (no server needed — CORS on the backend is
   permissive, see `backend/app/main.py`), or serve the folder with
   `python -m http.server` if your browser blocks `fetch` from a `file://` page.
3. Fill in:
   - **Backend URL** — defaults to `http://localhost:8000`.
   - **X-API-Key** — must match the backend's `AGRITWIN_API_KEY` env var (defaults to
     `dev-only-key-change-me` if unset — check `backend/app/config.py`).
4. Click **Start sending**. Drag the temperature slider to move through:
   - **< 18°C** — thermostat turns the heater on.
   - **18–26°C** — heater holds its last state (hysteresis band).
   - **> 26°C** — thermostat turns the heater off.
   - **≥ 32°C** — safety cutoff trips: heater forced off, fan forced to 100%, banner
     shown, regardless of the fan slider or thermostat state.
5. The fan slider is the "operator" input (what a dashboard/chat command would eventually
   set) — it's applied as-is unless the safety cutoff overrides it.

Every 500ms while running, it POSTs a `Reading`-shaped payload to `/api/v1/ingest` with
`source: "mock"`, same as `bridge/mock_source.py` would for a CSV replay — this just lets
you drive it live and see the visuals react before hooking up anything else.
