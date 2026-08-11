/*
 * AgriTwin core -- DS18B20 read, the safety cutoff, and the serial protocol.
 * Owner: Muhammad Irfan -- see docs/team-briefs/IRFAN.md for the full spec.
 *
 * The safety logic and protocol are kept separate from the actuator wiring on
 * purpose -- see Actuators.h -- so a future second build target could reuse
 * this file without touching it.
 *
 * NOT YET COMPILE-CHECKED -- no Arduino toolchain was available wherever this
 * was written. Compile it (see firmware/agritwin_hardware, `arduino-cli
 * compile --fqbn arduino:avr:uno --libraries ..`) before trusting it on real
 * hardware, especially the safety logic.
 *
 * Wiring assumed below for the sensor (shared by both builds; placeholder --
 * confirm and adjust against the actual rig):
 *   DS18B20 data -> D2 (needs a 4.7k pull-up to 5V between data and VCC)
 *
 * Serial protocol (agree changes with Asad before editing -- the backend parses this exact format):
 *   Arduino -> host:  T:<temp_c>,F:<fan_pct>,H:<0|1>,S:<seq>,W:<0|1>\n   every 500ms
 *   host -> Arduino:  F:<0-100>\n   H:<0|1>\n   PING\n
 *   9600 baud -- confirm this matches whatever reads the port on the laptop side.
 *
 * Safety order every loop -- not overridable by any host command, and this is the one
 * part of this file that must not be simplified away for time:
 *   1. Read DS18B20.
 *   2. If temp >= TEMP_MAX, or the sensor read failed -> heater OFF, fan 100, W:1.
 *   3. Else if no host message for 5000ms -> heater OFF (fan keeps its last commanded value).
 *   4. Only otherwise does the last received host command actually apply.
 * Telemetry always reports what's *actually* being driven this loop, not just whatever
 * the host last asked for -- the two can differ the moment either safety check above fires.
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include "Actuators.h"
#include "AgriTwinCore.h"

// ---- Pins ----
const uint8_t PIN_ONE_WIRE = 2;

// ---- Safety thresholds ----
// TODO: confirm TEMP_MAX with Asad/Irfan together -- set a little above the 30C crop-stress
// "stress" band (docs/Implementation_Plan.md Step 0.5) so software has room to react first,
// while still being a hard physical ceiling the firmware alone enforces.
const float TEMP_MAX = 32.0;
const unsigned long HOST_TIMEOUT_MS = 5000;
const unsigned long TELEMETRY_INTERVAL_MS = 500;
const uint8_t MAX_LINE_LENGTH = 32; // protocol lines are all well under this; guards against noise

OneWire oneWire(PIN_ONE_WIRE);
DallasTemperature sensors(&oneWire);

int desiredFanPct = 0;      // last value the host asked for
bool desiredHeaterOn = false;
bool watchdogTripped = false;
unsigned long lastHostMessageMs = 0;
unsigned long lastTelemetryMs = 0;
uint32_t seq = 0;

String lineBuffer; // Arduino String is a deliberate simplification here (see note below)

static void readIncomingSerial();
static void handleLine(const String &line);
static void sendTelemetry(float tempC, int fanPct, bool heaterOn);

void coreSetup() {
  Serial.begin(9600);
  sensors.begin();
  actuatorsInit();

  // Grace period so the host-timeout watchdog doesn't trip before the laptop has even
  // had a chance to connect after power-on.
  lastHostMessageMs = millis();
}

void coreLoop() {
  readIncomingSerial();

  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);
  bool sensorOk = (tempC != DEVICE_DISCONNECTED_C); // confirm this constant name against your DallasTemperature version

  int actualFanPct = desiredFanPct;
  bool actualHeaterOn = desiredHeaterOn;
  watchdogTripped = false;

  // ---- SAFETY FIRST -- checked every loop, before any command is applied ----
  if (!sensorOk || tempC >= TEMP_MAX) {
    actualHeaterOn = false;
    actualFanPct = 100;
    watchdogTripped = true;
  } else if (millis() - lastHostMessageMs > HOST_TIMEOUT_MS) {
    actualHeaterOn = false;
  }

  actuatorsSetFan(actualFanPct);
  actuatorsSetHeater(actualHeaterOn);

  if (millis() - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    sendTelemetry(sensorOk ? tempC : -127.0, actualFanPct, actualHeaterOn);
    lastTelemetryMs = millis();
  }
}

static void sendTelemetry(float tempC, int fanPct, bool heaterOn) {
  Serial.print("T:");
  Serial.print(tempC, 2);
  Serial.print(",F:");
  Serial.print(fanPct);
  Serial.print(",H:");
  Serial.print(heaterOn ? 1 : 0);
  Serial.print(",S:");
  Serial.print(seq++);
  Serial.print(",W:");
  Serial.println(watchdogTripped ? 1 : 0);
}

static void readIncomingSerial() {
  // Non-blocking: only ever consumes whatever's already arrived, so it never delays
  // the safety checks above. Arduino String is used for simplicity (fine for a few-day
  // demo); if this firmware ever needs to run unattended for a long time, swap to a
  // fixed-size char buffer to avoid heap fragmentation from repeated String concatenation.
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    // Accept a lone '\n', a lone '\r', or '\r\n' as a line terminator -- some serial
    // monitors (Wokwi's included) default to sending only one of the two. The
    // length() > 0 guard stops a '\r\n' pair from being dispatched twice.
    if (c == '\n' || c == '\r') {
      if (lineBuffer.length() > 0) {
        handleLine(lineBuffer);
        lineBuffer = "";
      }
    } else {
      if (lineBuffer.length() < MAX_LINE_LENGTH) {
        lineBuffer += c;
      } else {
        lineBuffer = ""; // malformed/noisy line -- drop it rather than growing forever
      }
    }
  }
}

static void handleLine(const String &line) {
  if (line.length() == 0) return;
  lastHostMessageMs = millis(); // PING and real commands both count as "still connected"

  if (line == "PING") {
    return;
  }
  if (line.startsWith("F:")) {
    desiredFanPct = constrain(line.substring(2).toInt(), 0, 100);
  } else if (line.startsWith("H:")) {
    desiredHeaterOn = line.substring(2).toInt() != 0;
  }
}
