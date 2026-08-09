"""
Pydantic models for the AgriTwin backend. Shapes here must match docs/API.md exactly —
that file is the frozen contract Unity and the chat UI build against.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Reading(BaseModel):
    ts: datetime
    temp_c: float
    fan_pct: int = Field(ge=0, le=100)
    heater_on: bool
    seq: int
    source: Literal["device", "mock"]
    watchdog_tripped: bool = False


class IngestPayload(BaseModel):
    """What the bridge process POSTs to /api/v1/ingest. The backend stamps `ts` itself
    on receipt rather than trusting the Arduino's clock (it has none) or the bridge's."""

    temp_c: float
    fan_pct: int = Field(ge=0, le=100)
    heater_on: bool
    seq: int
    source: Literal["device", "mock"] = "device"
    watchdog_tripped: bool = False


class StateResponse(BaseModel):
    ts: datetime | None
    temp_c: float | None
    fan_pct: int | None
    heater_on: bool | None
    seq: int | None
    data_age_s: float | None
    sensor_online: bool
    mode: Literal["device", "mock", "unknown"]
    watchdog_tripped: bool | None


class HistorySummary(BaseModel):
    min: float
    max: float
    avg: float
    count: int


class HistoryResponse(BaseModel):
    readings: list[Reading]
    summary: HistorySummary | None


class StressResult(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_label: Literal["ok", "caution", "stress"]
    factors: list[str]


class HealthResponse(BaseModel):
    sensor_online: bool
    last_reading_age_s: float | None
    buffer_size: int
    mode: Literal["device", "mock", "unknown"]
    uptime_s: float


class VentilationCommand(BaseModel):
    fan_pct: int = Field(ge=0, le=100)
    actor: str = "unknown"
    role: str = "operator"


class VentilationResponse(BaseModel):
    fan_pct: int
    allowed: bool
    reason: str | None = None


class DesiredState(BaseModel):
    fan_pct: int
