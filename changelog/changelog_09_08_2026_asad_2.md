## What changed
Added a draft Arduino firmware sketch and a Wokwi browser-simulator setup for it, so
the hardware safety cutoff can be tested with a temperature slider before real
hardware arrives.

## Why it matters
This is the piece that makes the heater safe to leave running: if the sensor reads too
hot, or fails entirely, the firmware turns the heater off on its own — no laptop, backend,
or AI involved in that decision. It hasn't been compiled or run yet, so treat it as a
starting point for Irfan to verify in Wokwi, not a finished, trusted safety mechanism.
