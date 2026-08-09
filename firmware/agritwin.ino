/*
 * AgriTwin firmware — Arduino Uno R3 + DS18B20 + L298N (fan) + relay/MOSFET (PTC heater).
 * Owner: Muhammad Irfan — see docs/team-briefs/IRFAN.md for the full spec.
 *
 * NOT YET COMPILE-CHECKED — no Arduino/Wokwi toolchain was available wherever this was
 * written. Load it into Wokwi (per your brief) or compile locally before trusting it on
 * real hardware, especially the safety logic.
 *
 * Wiring assumed below (placeholders — confirm and adjust against the actual rig):
 *   DS18B20 data        -> D2   (needs a 4.7k pull-up to 5V between data and VCC)
 *   L298N ENA (fan PWM)  -> D9
 *   L298N IN1            -> D8  (fixed HIGH — direction doesn't matter for a fan)
 *   L298N IN2            -> D7  (fixed LOW)
 *   Heater relay/MOSFET  -> D6  (HIGH = heater on) — confirm this matches your actual driver
 *
 * Serial protocol (agree changes with Asad before editing — the backend parses this exact format):
 *   Arduino -> host:  T:<temp_c>,F:<fan_pct>,H:<0|1>,S:<seq>,W:<0|1>\n   every 500ms
 *   host -> Arduino:  F:<0-100>\n   H:<0|1>\n   PING\n
 *   9600 baud — confirm this matches whatever reads the port on the laptop side.
 *
 * Safety order every loop — not overridable by any host command, and this is the one
 * part of this file that must not be simplified away for time:
 *   1. Read DS18B20.
 *   2. If temp >= TEMP_MAX, or the sensor read failed -> heater OFF, fan 100, W:1.
 *   3. Else if no host message for 5000ms -> heater OFF (fan keeps its last commanded value).
 *   4. Only otherwise does the last received host command actually apply.
 * Telemetry always reports what's *actually* being driven this loop, not just whatever
 * the host last asked for — the two can differ the moment either safety check above fires.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

// ---- Pins ----
const uint8_t PIN_ONE_WIRE = 2;
const uint8_t PIN_FAN_ENA = 9;
const uint8_t PIN_FAN_IN1 = 8;
const uint8_t PIN_FAN_IN2 = 7;
const uint8_t PIN_HEATER = 6;

// ---- Safety thresholds ----
// TODO: confirm TEMP_MAX with Asad/Irfan together — set a little above the 30C crop-stress
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

void setup() {
  Serial.begin(9600);
  sensors.begin();

  pinMode(PIN_FAN_ENA, OUTPUT);
  pinMode(PIN_FAN_IN1, OUTPUT);
  pinMode(PIN_FAN_IN2, OUTPUT);
  pinMode(PIN_HEATER, OUTPUT);

  digitalWrite(PIN_FAN_IN1, HIGH);
  digitalWrite(PIN_FAN_IN2, LOW);
  digitalWrite(PIN_HEATER, LOW);

  // Grace period so the host-timeout watchdog doesn't trip before the laptop has even
  // had a chance to connect after power-on.
  lastHostMessageMs = millis();
}

void loop() {
  readIncomingSerial();

  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);
  bool sensorOk = (tempC != DEVICE_DISCONNECTED_C); // confirm this constant name against your DallasTemperature version

  int actualFanPct = desiredFanPct;
  bool actualHeaterOn = desiredHeaterOn;
  watchdogTripped = false;

  // ---- SAFETY FIRST — checked every loop, before any command is applied ----
  if (!sensorOk || tempC >= TEMP_MAX) {
    actualHeaterOn = false;
    actualFanPct = 100;
    watchdogTripped = true;
  } else if (millis() - lastHostMessageMs > HOST_TIMEOUT_MS) {
    actualHeaterOn = false;
  }

  applyFan(actualFanPct);
  digitalWrite(PIN_HEATER, actualHeaterOn ? HIGH : LOW);

  if (millis() - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    sendTelemetry(sensorOk ? tempC : -127.0, actualFanPct, actualHeaterOn);
    lastTelemetryMs = millis();
  }
}

void applyFan(int pct) {
  pct = constrain(pct, 0, 100);
  analogWrite(PIN_FAN_ENA, map(pct, 0, 100, 0, 255));
}

void sendTelemetry(float tempC, int fanPct, bool heaterOn) {
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

void readIncomingSerial() {
  // Non-blocking: only ever consumes whatever's already arrived, so it never delays
  // the safety checks above. Arduino String is used for simplicity (fine for a few-day
  // demo); if this firmware ever needs to run unattended for a long time, swap to a
  // fixed-size char buffer to avoid heap fragmentation from repeated String concatenation.
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      handleLine(lineBuffer);
      lineBuffer = "";
    } else if (c != '\r') {
      if (lineBuffer.length() < MAX_LINE_LENGTH) {
        lineBuffer += c;
      } else {
        lineBuffer = ""; // malformed/noisy line — drop it rather than growing forever
      }
    }
  }
}

void handleLine(const String &line) {
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
