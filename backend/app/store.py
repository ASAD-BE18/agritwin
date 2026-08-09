"""
In-memory ring buffer for sensor readings — the backend's single source of truth.
No SQLite: per the plan, a ring buffer alone covers /state and /history for a demo,
and persistence across restarts is insurance the prototype doesn't need.
"""

import time
from collections import deque
from datetime import datetime, timedelta, timezone

from app import config
from app.models import HistorySummary, IngestPayload, Reading


class ReadingStore:
    def __init__(self, maxlen: int = config.BUFFER_MAXLEN) -> None:
        self._buffer: deque[Reading] = deque(maxlen=maxlen)
        self._desired_fan_pct: int = 0
        self._start_time = time.monotonic()

    def ingest(self, payload: IngestPayload) -> Reading:
        reading = Reading(
            ts=datetime.now(timezone.utc),
            temp_c=payload.temp_c,
            fan_pct=payload.fan_pct,
            heater_on=payload.heater_on,
            seq=payload.seq,
            source=payload.source,
            watchdog_tripped=payload.watchdog_tripped,
        )
        self._buffer.append(reading)
        return reading

    def latest(self) -> Reading | None:
        return self._buffer[-1] if self._buffer else None

    def data_age_s(self, now: datetime | None = None) -> float | None:
        last = self.latest()
        if last is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - last.ts).total_seconds()

    def is_sensor_online(self, now: datetime | None = None) -> bool:
        age = self.data_age_s(now)
        return age is not None and age < config.STALE_AFTER_S

    def history(
        self, start: datetime | None = None, end: datetime | None = None, max_points: int = 500
    ) -> tuple[list[Reading], HistorySummary | None]:
        readings = [
            r for r in self._buffer if (start is None or r.ts >= start) and (end is None or r.ts <= end)
        ]
        if not readings:
            return [], None

        summary = HistorySummary(
            min=min(r.temp_c for r in readings),
            max=max(r.temp_c for r in readings),
            avg=sum(r.temp_c for r in readings) / len(readings),
            count=len(readings),
        )

        downsampled = _downsample(readings, max_points)
        return downsampled, summary

    def stress_inputs(self) -> tuple[float, float, float, float] | None:
        """Derives score()'s 4 inputs from the raw buffer. See app/stress.py for how
        they're used; the band-boundary logic itself is tested there in isolation."""
        if not self._buffer:
            return None
        readings = list(self._buffer)
        current_reading = readings[-1]
        current = current_reading.temp_c
        now = current_reading.ts

        recent = [r for r in readings if r.ts >= now - timedelta(minutes=10)]
        mean_10min = sum(r.temp_c for r in recent) / len(recent) if recent else current

        prior = [r for r in readings if r.ts <= now - timedelta(minutes=1)]
        if prior:
            prior_reading = prior[-1]
            minutes_elapsed = max((now - prior_reading.ts).total_seconds() / 60.0, 1e-6)
            rate_c_per_min = (current - prior_reading.temp_c) / minutes_elapsed
        else:
            rate_c_per_min = 0.0

        minutes_above_30 = 0.0
        for r in reversed(readings):
            if r.temp_c > 30.0:
                minutes_above_30 = (now - r.ts).total_seconds() / 60.0
            else:
                break

        return current, mean_10min, rate_c_per_min, minutes_above_30

    def buffer_size(self) -> int:
        return len(self._buffer)

    def uptime_s(self) -> float:
        return time.monotonic() - self._start_time

    def set_desired_fan_pct(self, fan_pct: int) -> None:
        self._desired_fan_pct = fan_pct

    def desired_fan_pct(self) -> int:
        return self._desired_fan_pct


def _downsample(readings: list[Reading], max_points: int) -> list[Reading]:
    """Evenly samples down to at most `max_points` readings. Never hand the LLM
    (or anyone else) thousands of raw rows — see docs/API.md."""
    if max_points <= 0 or len(readings) <= max_points:
        return readings
    step = len(readings) / max_points
    indices = [int(i * step) for i in range(max_points)]
    return [readings[i] for i in indices]


store = ReadingStore()
