# AgriTwin — Your Task Brief

**For:** Maheen Nazam
**Your area:** Project Coordination, Documentation, Demo Prep
**Project:** AgriTwin

---

## What this project actually is, in plain terms

Picture a small box acting as a mini-greenhouse. Inside it: a temperature sensor, a small heater, and a fan. A computer program watches the sensor constantly and can turn the fan on or off. On top of that, there's an AI chat assistant (like a smarter version of a chatbot) that people can ask questions like *"is it too hot in there right now?"* — and instead of guessing, it actually looks up the real, current number before answering. There's also a 3D version of the whole setup shown on a screen (built in a tool called Unity), which updates live to match what's really happening in the physical box.

That's it. Sensor → computer → AI → 3D screen. Your role doesn't require understanding how any of that is coded — it requires making sure the *team* stays on track and that anyone watching the final demo (including non-technical judges) can actually follow what's happening.

## Quick glossary, so nothing anyone says in standup is confusing

- **Arduino** — a small computer chip that reads the sensor and controls the fan/heater.
- **Backend** — the main program running on a laptop that everything else talks to.
- **AI tool call** — when the chatbot looks something up (like the current temperature) instead of guessing. This is the thing the whole demo is trying to prove happens reliably.
- **Digital twin** — the 3D on-screen version of the physical box, kept in sync with it live.
- **Mock data** — realistic fake sensor readings used to test everything before the real hardware is ready.

## Your tasks

### 1. Timeline tracking
Keep a simple day-by-day checklist (a spreadsheet or even a shared doc is enough) mapped to the project's schedule:
- Pitch day → build day → demo day.
Ask each teammate briefly each day what's done and what's blocked, and flag it to Asad if something looks at risk — you don't need to solve technical blockers, just surface them early.

### 2. Changelog
Every time someone finishes a meaningful piece of work, write one short plain-English line about it — not code details, just *what changed and why it matters*. Example: "Added the safety cutoff so the heater always turns off if it gets too hot, even if the laptop crashes." Ask whoever built it to give you one sentence if you're not sure how to phrase it.

### 3. Hardware cost tracking
Keep a simple list of every physical part (Arduino board, sensor, heater, fan, driver board, wiring, box/enclosure) with its cost. This is standard budget tracking — exactly the kind of thing your Accounting & Finance background is directly useful for, not a "consolation task."

### 4. Demo script
Write the actual words that will be spoken during the ~3-minute live demo. You'll get the technical beats from Asad (e.g., "now we warm the sensor and the 3D twin reacts," "now we ask the AI a question and show it looking up the real answer") — your job is turning those into a clear, confident spoken narrative a judge can follow without a technical background. Also prepare simple answers to likely questions judges might ask (Asad can supply the technical substance; you shape how it's said).

### 5. Plain-language quality check
Before anything goes in front of judges or is shared publicly (slides, the project write-up, any project webpage), read it as the intended non-technical audience. **If a sentence doesn't make sense to you, that's real, valuable signal that it needs to be simplified — not a gap in your understanding.** Flag it and ask for a plainer rewrite. This exact kind of feedback already made the team's project explainer webpage significantly clearer earlier on.

## What you're waiting on

Nothing blocks you from starting today — the timeline sheet, changelog template, and cost list can all begin immediately. The demo script needs the technical beats from Asad closer to build day, and the plain-language check happens continuously as things get shared.

## How you'll know it's done

- [ ] Timeline sheet exists and is updated daily.
- [ ] Changelog has an entry for every meaningful piece of finished work.
- [ ] Full parts/cost list exists before the build days.
- [ ] Demo script is written and rehearsed with the team at least twice before the live demo.
- [ ] You've read through the demo script and any public-facing material and confirmed you understand every sentence without help.

## Who to talk to

- **Asad** — for the technical substance behind the demo script and for anything you don't understand well enough to simplify.
- **Everyone else** — for one-line changelog updates on what they just finished.
