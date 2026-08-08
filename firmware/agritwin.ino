/*
 * AgriTwin firmware — Arduino Uno R3 + DS18B20 + L298N + PTC heater.
 * Owner: Muhammad Irfan — see docs/team-briefs/IRFAN.md for the full spec.
 *
 * Serial protocol (agree changes with Asad before editing — the backend parses this exact format):
 *   Arduino -> host:  T:<temp_c>,F:<fan_pct>,H:<0|1>,S:<seq>,W:<0|1>\n   every 500ms
 *   host -> Arduino:  F:<0-100>\n   H:<0|1>\n   PING\n
 *
 * Safety order every loop — not overridable by any host command:
 *   1. Read DS18B20.
 *   2. If temp >= TEMP_MAX -> heater OFF, fan 100, W:1.
 *   3. If no host message for 5000ms -> heater OFF.
 *   4. Only then apply the last received command.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

const float TEMP_MAX = 32.0; // TODO: confirm against crop-stress bands in docs/Implementation_Plan.md

void setup() {
  // TODO: init serial, DS18B20, L298N pins
}

void loop() {
  // TODO: implement the safety-first loop described above
}
