/*
 * AgriTwin firmware -- HARDWARE build.
 * Real Arduino Uno R3 + DS18B20 + L298N motor driver (fan) + relay/MOSFET (PTC heater).
 * Owner: Muhammad Irfan -- see docs/team-briefs/IRFAN.md for the full spec.
 *
 * All safety logic and the serial protocol live in ../common/AgriTwinCore.*, shared
 * with the sim build so the two can never drift apart. This file only wires up the
 * real actuators via HardwareActuators.cpp -- see that file for pin assignments.
 */

#include "AgriTwinCore.h"

void setup() {
  coreSetup();
}

void loop() {
  coreLoop();
}
