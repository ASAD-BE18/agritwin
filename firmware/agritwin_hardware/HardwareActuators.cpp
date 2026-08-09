/*
 * Real actuator outputs -- L298N motor driver (fan) + relay/MOSFET (PTC heater).
 *
 * Wiring assumed below (placeholders -- confirm and adjust against the actual rig):
 *   L298N ENA (fan PWM) -> D9
 *   L298N IN1            -> D8  (fixed HIGH -- direction doesn't matter for a fan)
 *   L298N IN2            -> D7  (fixed LOW)
 *   Heater relay/MOSFET  -> D6  (HIGH = heater on) -- confirm this matches your actual driver
 */

#include "Actuators.h"

const uint8_t PIN_FAN_ENA = 9;
const uint8_t PIN_FAN_IN1 = 8;
const uint8_t PIN_FAN_IN2 = 7;
const uint8_t PIN_HEATER = 6;

void actuatorsInit() {
  pinMode(PIN_FAN_ENA, OUTPUT);
  pinMode(PIN_FAN_IN1, OUTPUT);
  pinMode(PIN_FAN_IN2, OUTPUT);
  pinMode(PIN_HEATER, OUTPUT);

  digitalWrite(PIN_FAN_IN1, HIGH);
  digitalWrite(PIN_FAN_IN2, LOW);
  digitalWrite(PIN_HEATER, LOW);
}

void actuatorsSetFan(int pct) {
  pct = constrain(pct, 0, 100);
  analogWrite(PIN_FAN_ENA, map(pct, 0, 100, 0, 255));
}

void actuatorsSetHeater(bool on) {
  digitalWrite(PIN_HEATER, on ? HIGH : LOW);
}
