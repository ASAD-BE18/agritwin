# AgriTwin — Your Task Brief

**For:** Muhammad Irfan
**Your area:** Hardware & Firmware
**Project:** AgriTwin — a small greenhouse rig (sensor + heater + fan) that a laptop watches over, and that people can ask questions about in plain English.

---

## The 30-second version of the whole project

A temperature sensor sits in a small greenhouse box. An Arduino reads it and controls a fan and a heater. A laptop program watches that data, keeps a 3D model in sync with it, and lets an AI answer questions like "is it too hot in there?" by actually checking the live number — not guessing.

**Your job is the physical half:** the box, the sensor, the fan, the heater, and the code on the Arduino that runs it all safely.

## What you're building

1. **Wire it up:** Arduino Uno R3 + DS18B20 temperature sensor + L298N motor driver board + a small fan + a PTC heater.
2. **Write the firmware** (the code that runs on the Arduino itself) to:
   - Read the temperature sensor.
   - Send a status line to the laptop every half-second.
   - Accept fan/heater commands from the laptop.
3. **Build the safety cutoff — this is the part that matters most.** It is not optional and it cannot be skipped for time. It has to work exactly like this, in this order, every single loop of the program:
   - Read the sensor.
   - **Before anything else:** if the temperature is above the safe maximum → turn the heater off and the fan to full, immediately, no matter what command the laptop last sent.
   - **Also before anything else:** if the laptop hasn't sent any message in 5 seconds (meaning the connection might be dead) → turn the heater off.
   - *Only after* those two checks does it apply whatever fan/heater command the laptop asked for.

   Why this order matters: if the laptop crashes, or the USB cable comes loose, or the AI does something unexpected, the heater still has to turn itself off on its own. The Arduino can never wait for permission from the laptop to protect itself — it has to decide that independently, every loop.

## The message format (agree this with Asad before you start writing code)

```
Arduino → laptop:   T:23.44,F:60,H:1,S:1234,W:0
                     (T=temp °C, F=fan %, H=heater on/off, S=sequence number, W=1 if the cutoff just tripped)

laptop → Arduino:   F:60      (set fan to 60%)
                     H:0       (set heater off)
                     PING      (just checking the connection is alive)
```

Talk to Asad before you finalize this — his backend code parses exactly this format, so if either of you changes it, tell the other immediately.

## You don't need to wait for the hardware kit to start

The safety logic and serial protocol live in `firmware/common/AgriTwinCore.cpp`, shared by
the one real-hardware build target (`firmware/agritwin_hardware/`). You can compile it
without any hardware or simulator attached to at least catch build errors early:

```
cd firmware/agritwin_hardware
arduino-cli compile --fqbn arduino:avr:uno --libraries .. --output-dir build agritwin_hardware.ino
```

For actually *exercising* the safety cutoff (dragging a fake temperature up and watching
the heater turn itself off) before real hardware arrives, your best option is still a
Wokwi circuit (wokwi.com, free, no signup for basic use) — we don't ship a pre-built one
anymore (the earlier attempt kept fighting us on part wiring/layout with no real payoff),
so you'd wire up your own Arduino Uno + DS18B20 project there and paste in
`agritwin_hardware.ino` + the `common/` files as extra tabs. Not required to start, but
worth doing before you'd ever trust the cutoff on a real heater.

Separately, there's `firmware/web_sim/` — a browser page that stands in for the whole rig
(temperature slider, fan/heater visuals) and feeds the backend directly. That's for
demoing the *rest* of the system (Unity, chat, dashboards) with zero hardware — it
reimplements the safety rule in JS for the visuals, it does not run your actual firmware
code, so it doesn't substitute for compiling and testing your C++.

## How you'll know it's done

- [ ] Firmware compiles without errors (`arduino-cli compile`, see above).
- [ ] On real hardware (or your own Wokwi circuit): drag/heat the temperature up past the safe threshold — heater turns off and fan goes to 100%, on its own, without you sending any command.
- [ ] Disconnect the sensor — heater turns off.
- [ ] Stop sending messages from the laptop side for 5+ seconds — heater turns off.
- [ ] These three checks pass **before** the heater is ever left running unattended with real hardware.

## Who to talk to

- **Asad** — for the message format, and once hardware arrives, for wiring the Arduino's serial output into his laptop-side code.
- If you're stuck on the safety logic specifically, flag it loudly and early — this is the one piece of the whole project that isn't allowed to be "good enough for a demo," because it's the difference between a prototype and something that can actually burn someone.
