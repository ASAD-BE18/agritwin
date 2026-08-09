# Running the firmware in Wokwi

`diagram.json` and `wokwi.toml` here are a starting circuit, not a guaranteed-correct one —
I wrote them without access to Wokwi itself to test against, so **treat the circuit as a
draft to open and fix, not a finished thing.** Confidence varies by part, noted below.

## Option A — browser only, fastest to try (recommended first)

1. Go to wokwi.com, start a **New Project → Arduino Uno**.
2. Open the diagram editor's JSON view (the `</>` / "diagram.json" tab) and replace its
   contents with this folder's `diagram.json`.
3. Paste `agritwin.ino`'s contents into the sketch editor.
4. Click **Start Simulation**. If any part shows an error (red outline / "part not found"),
   open the parts search panel, search for the part by name, and re-add it — you won't lose
   the rest of the circuit.
5. Click the DS18B20 part to get a temperature slider — drag it above 32°C and confirm the
   heater indicator LED turns off and stays off (that's the watchdog test from your brief).

## Option B — VS Code + Wokwi extension (needed later for the backend-integration testing Asad's using)

1. Install the **Wokwi for VS Code** extension, plus `arduino-cli` with the AVR core.
2. Open this `firmware/` folder in VS Code.
3. Compile: `arduino-cli compile --fqbn arduino:avr:uno --output-dir build agritwin.ino`
4. Press F1 → **Wokwi: Start Simulator** — it reads `wokwi.toml` to find the compiled
   `build/agritwin.ino.hex` / `.elf`, and `diagram.json` for the circuit.

## Confidence notes on `diagram.json` — check these first if something won't load

- **DS18B20 + pull-up resistor + Arduino Uno wiring**: high confidence, this is a very
  standard, well-documented Wokwi circuit.
- **LED as a heater stand-in** on D6: high confidence on the LED/resistor part itself. The
  pin (D6) matches the firmware's placeholder — change both together if Irfan's actual
  heater driver uses a different pin.
- **`chip-l298n` part, and its `ENA`/`IN1`/`IN2`/`OUT1`/`OUT2` pin names**: medium confidence —
  confirmed `ENA`/`IN1`/`IN2` exist on this part from Wokwi example projects, but the exact
  output pin names weren't verified directly. If the L298N or the `wokwi-dc-motor` part
  errors on load, search Wokwi's part picker for "L298N" / "DC Motor" and re-wire that one
  section — everything else should be unaffected.
- The fan/L298N section isn't what the watchdog test depends on anyway — the DS18B20 +
  heater LED are the two parts that actually matter for verifying the safety cutoff.
