# AgriTwin API Contract

This is the contract between the backend and everyone building against it (Unity, the chat UI, the MCP server). If this changes, tell the whole team immediately — Unity and the chat UI are built directly against these shapes.

## Reading model

```python
class Reading(BaseModel):
    ts: datetime          # ISO-8601, UTC, always
    temp_c: float
    fan_pct: int          # 0–100
    heater_on: bool
    seq: int
    source: Literal["device", "mock"]
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/ingest` | Bridge → backend. `X-API-Key` header. |
| `GET` | `/api/v1/state` | Current snapshot + `data_age_s` + `mode`. |
| `GET` | `/api/v1/history?start=&end=&max_points=` | Readings + `{min,max,avg,count}` summary. Downsampled server-side. |
| `GET` | `/api/v1/stress` | `{risk_score, risk_label, factors[]}` |
| `GET` | `/api/v1/health` | `{sensor_online, last_reading_age_s, buffer_size, mode, uptime_s}` |
| `POST` | `/api/v1/control/ventilation` | `{fan_pct}` → clamped, audited desired state. |
| `GET` | `/api/v1/control/desired` | Bridge polls this to push down to the Arduino. |

Every response carries units in field names (`temp_c`, `fan_pct`, `data_age_s`).
`history` **must** downsample — never hand the LLM 10,000 raw rows.

## Example `/api/v1/state` response

```json
{
  "ts": "2026-08-09T12:00:00Z",
  "temp_c": 24.3,
  "fan_pct": 60,
  "heater_on": false,
  "seq": 1234,
  "data_age_s": 0.4,
  "mode": "mock"
}
```

## Status

Draft — pre-populated from the planning doc. Asad will confirm this is final (or note changes) by end of Day 5, per the implementation plan's Step 0.2.
