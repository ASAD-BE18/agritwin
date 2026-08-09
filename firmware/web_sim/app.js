// AgriTwin web rig simulator — stands in for the physical greenhouse rig.
//
// This is a separate reimplementation of the safety rule in
// ../common/AgriTwinCore.cpp, not a port of it — if the real firmware's
// TEMP_MAX ever changes, update it here too.
const TEMP_MAX = 32.0;

// Matches backend/app/config.py's default STRESS_OPTIMAL_LOW/HIGH — used here
// as a simple bang-bang thermostat so the heater has something to react to.
const THERMOSTAT_LOW = 18.0;
const THERMOSTAT_HIGH = 26.0;

// Matches AgriTwinCore.cpp's TELEMETRY_INTERVAL_MS.
const SEND_INTERVAL_MS = 500;

const tempSlider = document.getElementById("tempSlider");
const fanSlider = document.getElementById("fanSlider");
const tempReadout = document.getElementById("tempReadout");
const fanReadout = document.getElementById("fanReadout");
const heaterReadout = document.getElementById("heaterReadout");
const thermoTubeFill = document.getElementById("thermoTubeFill");
const thermoBulb = document.getElementById("thermoBulb");
const fanBladeGroup = document.getElementById("fanBladeGroup");
const heaterGroup = document.getElementById("heaterGroup");
const rigDiagram = document.getElementById("rigDiagram");
const banner = document.getElementById("banner");
const backendUrlInput = document.getElementById("backendUrl");
const apiKeyInput = document.getElementById("apiKey");
const toggleBtn = document.getElementById("toggleBtn");
const statusEl = document.getElementById("status");

let heaterThermostatOn = false; // persists across ticks for the hysteresis band
let seq = 0;
let running = false;
let timerId = null;

for (const [key, el] of [["agritwin_backendUrl", backendUrlInput], ["agritwin_apiKey", apiKeyInput]]) {
  const saved = localStorage.getItem(key);
  if (saved) el.value = saved;
  el.addEventListener("change", () => localStorage.setItem(key, el.value));
}

function computeState() {
  const tempC = parseFloat(tempSlider.value);
  const desiredFanPct = parseInt(fanSlider.value, 10);

  if (tempC <= THERMOSTAT_LOW) heaterThermostatOn = true;
  else if (tempC >= THERMOSTAT_HIGH) heaterThermostatOn = false;
  // else: hold whatever the thermostat was already doing (hysteresis band)

  let actualFanPct = desiredFanPct;
  let actualHeaterOn = heaterThermostatOn;
  let watchdogTripped = false;

  // Safety cutoff — mirrors the order in AgriTwinCore.cpp: checked before
  // anything else applies, unconditionally overrides both outputs.
  if (tempC >= TEMP_MAX) {
    actualHeaterOn = false;
    actualFanPct = 100;
    watchdogTripped = true;
    heaterThermostatOn = false;
  }

  return { tempC, actualFanPct, actualHeaterOn, watchdogTripped };
}

function render({ tempC, actualFanPct, actualHeaterOn, watchdogTripped }) {
  tempReadout.textContent = `${tempC.toFixed(1)}°C`;
  const fillPct = Math.min(100, Math.max(0, ((tempC + 10) / 55) * 100));
  const tubeTop = 4, tubeBottom = 52; // inner vertical span of the thermometer tube in thermoTube's local coords
  const fillHeight = ((tubeBottom - tubeTop) * fillPct) / 100;
  thermoTubeFill.setAttribute("y", tubeBottom - fillHeight);
  thermoTubeFill.setAttribute("height", fillHeight);
  const tempColor = watchdogTripped ? "var(--danger)" : actualHeaterOn ? "var(--heat)" : "var(--cold)";
  thermoTubeFill.style.fill = tempColor;
  thermoBulb.style.fill = tempColor;

  fanReadout.textContent = `${actualFanPct}%`;
  fanBladeGroup.style.animation = actualFanPct > 0
    ? `spin ${(1.3 - (actualFanPct / 100) * 1.1).toFixed(2)}s linear infinite`
    : "none";

  // Airflow in the diagram tracks the fan: faster drift and stronger dashes as the
  // speed rises, nothing at all at 0%. Set on the <svg> so the arrowhead marker,
  // which sits in <defs>, inherits it too.
  const fanFraction = actualFanPct / 100;
  rigDiagram.style.setProperty("--wind-speed", actualFanPct > 0 ? `${(1.5 - fanFraction * 1.2).toFixed(2)}s` : "0s");
  rigDiagram.style.setProperty("--wind-opacity", actualFanPct > 0 ? (0.35 + fanFraction * 0.45).toFixed(2) : "0");

  heaterReadout.textContent = actualHeaterOn ? "ON" : "OFF";
  heaterGroup.classList.toggle("on", actualHeaterOn);

  banner.hidden = !watchdogTripped;
}

async function sendReading({ tempC, actualFanPct, actualHeaterOn }) {
  const url = `${backendUrlInput.value.replace(/\/$/, "")}/api/v1/ingest`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKeyInput.value,
      },
      body: JSON.stringify({
        temp_c: tempC,
        fan_pct: actualFanPct,
        heater_on: actualHeaterOn,
        seq: seq++,
        source: "mock",
      }),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`${res.status} ${res.statusText} — ${detail}`);
    }
    statusEl.textContent = `sent seq ${seq - 1} at ${new Date().toLocaleTimeString()}`;
    statusEl.className = "status ok";
  } catch (err) {
    statusEl.textContent = `send failed: ${err.message}`;
    statusEl.className = "status error";
  }
}

function tick() {
  const state = computeState();
  render(state);
  if (running) sendReading(state);
}

tempSlider.addEventListener("input", tick);
fanSlider.addEventListener("input", tick);

toggleBtn.addEventListener("click", () => {
  running = !running;
  if (running) {
    toggleBtn.textContent = "Stop sending";
    statusEl.textContent = "sending...";
    statusEl.className = "status";
    tick();
    timerId = setInterval(tick, SEND_INTERVAL_MS);
  } else {
    toggleBtn.textContent = "Start sending";
    statusEl.textContent = "stopped";
    statusEl.className = "status";
    clearInterval(timerId);
  }
});

tick();
