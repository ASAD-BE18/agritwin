# AgriTwin — Your Task Brief

**For:** Shakila Naaz
**Your area:** Unity Digital Twin
**Project:** AgriTwin — a small greenhouse rig (sensor + heater + fan) that a laptop watches over, and that people can ask questions about in plain English.

---

## The 30-second version of the whole project

A temperature sensor sits in a small greenhouse box, wired to an Arduino that controls a fan and a heater. A laptop backend (built by Asad) reads that data continuously and exposes it over a simple web API. An AI layer on top of it can answer natural-language questions by checking the live numbers. **Your job is the visual half:** a 3D "digital twin" that mirrors the real rig in real time, shown in Unity.

**Scope note:** we don't have AR/VR headsets or an AR-capable device for this build — the team only has the Arduino kit and sensors. So this is a Unity 3D scene only, no AR overlay. If that changes later, an AR pass can be layered on afterward, but don't plan around it for now.

## New to Unity? Read this first

If you haven't used Unity or C# before, that's completely fine — the actual amount of code here is small (~40 lines, given to you below), and none of it requires deep Unity knowledge. Two things to make the on-ramp fast:

1. **A 1–2 hour pairing session** with Asad or Tayyaba to install Unity Hub, create the project, and drop the starter script in together, before you're expected to work on this solo. The goal is that your *first* experience with Unity is "this already runs," not a blank editor.
2. **No custom 3D art.** The scene is built entirely from Unity's built-in shapes — a Cube for the heater, a Cylinder for the fan — dragged in from Unity's own `GameObject > 3D Object` menu. No modeling, no importing, no rigging. You're changing their color and rotation speed from code, nothing more.

## What you're building

1. **A Unity scene** using built-in primitives only: a Cube (heater), a Cylinder (fan), and a Text (TextMeshPro) label for the numbers.
2. **Live data binding:** poll the backend's `/api/v1/state` endpoint 4 times a second and update those three objects to match. The full script for this is below — you shouldn't need to write this networking part from scratch.
3. **Make it demo-worthy on its own**, since it's the only visual centerpiece now (not one of two, alongside AR): good camera angle, clear readouts, legible from a few feet away.

You don't need to build any of the backend, sensor logic, or AI — you're purely a client of the API. Treat the backend as a black box that hands you JSON.

## Starter script — drop this in and wire it up

Create an empty GameObject in your scene called `TwinController`, attach this script to it, then drag your Cube, Cylinder, and Text objects onto the matching fields in the Inspector panel (no code needed for that part — just drag-and-drop).

```csharp
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;
using TMPro;

public class TwinController : MonoBehaviour
{
    public string baseUrl = "http://localhost:8000"; // Asad will give you the real one
    public Transform fanBlade;      // drag the Cylinder here
    public Renderer heaterRenderer; // drag the Cube here
    public TMP_Text readout;        // drag the Text (TMP) object here

    float fanSpeed = 0f;
    bool heaterOn = false;

    [System.Serializable]
    public class State
    {
        public string ts;
        public float temp_c;
        public int fan_pct;
        public bool heater_on;
        public int seq;
        public float data_age_s;
        public string mode;
    }

    void Start() => StartCoroutine(PollLoop());

    void Update()
    {
        // Spins the fan every frame, proportional to the last known fan_pct
        fanBlade.Rotate(Vector3.forward, fanSpeed * Time.deltaTime);
    }

    IEnumerator PollLoop()
    {
        while (true)
        {
            using (UnityWebRequest req = UnityWebRequest.Get(baseUrl + "/api/v1/state"))
            {
                yield return req.SendWebRequest();
                if (req.result == UnityWebRequest.Result.Success)
                {
                    State s = JsonUtility.FromJson<State>(req.downloadHandler.text);
                    ApplyState(s);
                }
            }
            yield return new WaitForSeconds(0.25f); // 4 times a second
        }
    }

    void ApplyState(State s)
    {
        fanSpeed = s.fan_pct * 3.6f; // tune this multiplier until it looks right
        heaterOn = s.heater_on;
        heaterRenderer.material.color = heaterOn ? Color.red : Color.gray;

        string stale = s.data_age_s > 5f ? "  [STALE]" : "";
        readout.text = $"Temp: {s.temp_c:F1}°C\nFan: {s.fan_pct}%{stale}";
    }
}
```

This is a real starting point, not pseudocode — it should run as-is once the field references are wired up in the Inspector. From here, the work is tuning and polish (camera angle, colors, text size), not writing new networking code.

## What the API will look like

Asad is publishing `docs/API.md` — a short document with the exact URL and JSON shape you'll be polling, something like:

```json
GET /api/v1/state
{
  "ts": "2026-08-08T12:00:00Z",
  "temp_c": 24.3,
  "fan_pct": 60,
  "heater_on": false,
  "seq": 1234,
  "data_age_s": 0.4,
  "mode": "mock"
}
```

`data_age_s` tells you how stale the reading is — worth showing a "stale" indicator in the twin if this climbs above a few seconds (e.g. the sensor got disconnected), so the demo doesn't silently freeze without explanation.

## You don't need to wait for real hardware

The backend runs a **mock mode** from day one — a realistic recorded 30-minute temperature profile that replays over the same API, indistinguishable from a live sensor as far as your code is concerned. Start building against that mock URL immediately; you'll swap to the real device later by changing nothing on your end (same URL, same JSON shape) once hardware is connected.

## What you're waiting on

- **`docs/API.md`** and the mock backend's URL, from Asad — this is the one thing that blocks you from starting. If it's late, ask him directly rather than guessing at the format.

## How you'll know it's done

- [ ] Twin visibly reacts to a changing mock temperature within roughly 1–2 seconds (this is a "feels responsive" demo, not a hard latency number — don't over-engineer timing precision here).
- [ ] Readouts are clear enough to read from a few feet away — this is now the main visual, so legibility matters more than it would if AR were sharing the load.
- [ ] Still works once the backend switches from mock data to the real sensor (Day 6) — test this switch explicitly, don't assume it "just works."

## Who to talk to

- **Asad or Tayyaba** — to schedule the initial pairing session (Unity install + project setup + starter script wired in). Do this first, before trying to work through setup alone.
- **Asad** — for the API contract, the mock backend URL, and once hardware's connected, for confirming the live switch works on his end too.
- If you want one reference doc for how the networking script works under the hood (not required, just background): Unity's own docs on `UnityWebRequest` — https://docs.unity3d.com/ScriptReference/Networking.UnityWebRequest.html
