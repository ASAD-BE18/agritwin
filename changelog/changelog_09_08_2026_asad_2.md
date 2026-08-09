## What changed
This PR grew across several pushes — this entry reflects its current, final scope:

- **Firmware:** draft Arduino hardware build (`firmware/agritwin_hardware/` +
  `firmware/common/AgriTwinCore.*`) implementing the frozen serial protocol and the
  safety-first watchdog loop from `docs/team-briefs/IRFAN.md`. Not yet compiled or
  run on real hardware.
- **Web rig simulator** (`firmware/web_sim/`) replacing the earlier Wokwi scaffold
  (dropped — its wiring layout wasn't worth fighting). Lets anyone demo the rest of
  the stack against a real backend with zero hardware.
- **API contract:** added `watchdog_tripped: bool` to `Reading`/`IngestPayload`/
  `StateResponse` so the firmware's `W` safety flag actually reaches the backend and
  everything downstream, instead of being silently dropped. Additive, backward
  compatible.
- **MCP server** (`mcp/`): the 5-tool surface (`get_current_conditions`,
  `get_historical_range`, `predict_crop_stress`, `get_system_health`,
  `set_ventilation_level`) as tested `httpx` wrappers over the backend, plus the
  stdio server exposing them to Claude Desktop/Code. RBAC + audit on the one
  actuator tool; heater control stays read-only everywhere above the firmware.
- **Serial bridge** (`bridge/`): owns the Arduino's serial port as its own process,
  forwards telemetry to `/api/v1/ingest`, and pushes the fan setpoint back down —
  ready to test once real hardware exists.
- Merged `main` in and resolved a real conflict in `docs/API.md` (both sides had
  edited the same `/state` example block).
- Self-review fix: the bridge's fan-setpoint poll could crash the whole process on
  a malformed-but-200 backend response — broadened an overly narrow exception
  handler, added 2 regression tests.

73 tests total across backend/mcp/bridge (all green): 45 backend, 9 mcp, 19 bridge.

## Why it matters
Everything upstream of Claude is now built and tested end-to-end against the web
simulator: sensor data → backend (with the safety-relevant watchdog flag intact) →
MCP tools, including the fan-control RBAC/audit path and the stale-data rejection
that keeps a command from being applied against readings that are no longer live.
Firmware still needs a real compile-and-bench-test pass (per its own "not yet
verified" note) before anyone trusts the cutoff near a real heater — that hasn't
changed.
