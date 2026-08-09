#pragma once
#include <Arduino.h>

// Actuator interface -- AgriTwinCore calls only these, never a pin directly.
// Implemented by agritwin_hardware/HardwareActuators.cpp (real L298N fan driver
// + relay/MOSFET heater). The implementation must produce the physical output
// within the same loop iteration the safety logic calls it in -- AgriTwinCore
// relies on that to keep telemetry truthful to what's actually being driven.

void actuatorsInit();
void actuatorsSetFan(int pct);      // 0-100, already safety-clamped by the caller
void actuatorsSetHeater(bool on);
