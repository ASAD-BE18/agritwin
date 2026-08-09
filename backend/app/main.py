"""
FastAPI entrypoint for the AgriTwin backend. Endpoint contract is frozen in
docs/API.md — this implements exactly that, nothing more.

CORS is permissive (`*`) deliberately: this runs on a LAN for a 3-day demo, not a
public deployment, and X-API-Key on write endpoints is the actual protection here.
See docs/Implementation_Plan.md §1.4 / Step 0.4 for why.
"""

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.control import apply_ventilation_command
from app.models import (
    DesiredState,
    HealthResponse,
    IngestPayload,
    Reading,
    StateResponse,
    StressResult,
    VentilationCommand,
    VentilationResponse,
)
from app.store import store
from app.stress import score

app = FastAPI(title="AgriTwin Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


@app.post("/api/v1/ingest", response_model=Reading, dependencies=[Depends(require_api_key)])
def ingest(payload: IngestPayload) -> Reading:
    return store.ingest(payload)


@app.get("/api/v1/state", response_model=StateResponse)
def get_state() -> StateResponse:
    last = store.latest()
    age = store.data_age_s()
    online = store.is_sensor_online()

    if last is None:
        return StateResponse(
            ts=None,
            temp_c=None,
            fan_pct=None,
            heater_on=None,
            seq=None,
            data_age_s=None,
            sensor_online=False,
            mode="unknown",
            watchdog_tripped=None,
        )

    return StateResponse(
        ts=last.ts,
        temp_c=last.temp_c,
        fan_pct=last.fan_pct,
        heater_on=last.heater_on,
        seq=last.seq,
        data_age_s=age,
        sensor_online=online,
        mode=last.source,
        watchdog_tripped=last.watchdog_tripped,
    )


@app.get("/api/v1/history")
def get_history(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    max_points: int = Query(default=500, ge=1, le=5000),
) -> dict:
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    readings, summary = store.history(start=start, end=end, max_points=max_points)
    return {
        "readings": [r.model_dump(mode="json") for r in readings],
        "summary": summary.model_dump() if summary else None,
    }


@app.get("/api/v1/stress", response_model=StressResult)
def get_stress() -> StressResult:
    inputs = store.stress_inputs()
    if inputs is None:
        raise HTTPException(status_code=503, detail="no readings yet")
    current, mean_10min, rate_c_per_min, minutes_above_30 = inputs
    return score(current, mean_10min, rate_c_per_min, minutes_above_30)


@app.get("/api/v1/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    last = store.latest()
    return HealthResponse(
        sensor_online=store.is_sensor_online(),
        last_reading_age_s=store.data_age_s(),
        buffer_size=store.buffer_size(),
        mode=last.source if last else "unknown",
        uptime_s=store.uptime_s(),
    )


@app.post(
    "/api/v1/control/ventilation",
    response_model=VentilationResponse,
    dependencies=[Depends(require_api_key)],
)
def set_ventilation(cmd: VentilationCommand) -> VentilationResponse:
    return apply_ventilation_command(cmd, store)


@app.get(
    "/api/v1/control/desired",
    response_model=DesiredState,
    dependencies=[Depends(require_api_key)],
)
def get_desired() -> DesiredState:
    return DesiredState(fan_pct=store.desired_fan_pct())
