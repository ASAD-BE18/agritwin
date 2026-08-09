from datetime import timedelta

from app import config
from app.models import IngestPayload


def test_sensor_online_immediately_after_ingest(fresh_store):
    fresh_store.ingest(IngestPayload(temp_c=24.0, fan_pct=50, heater_on=False, seq=1))
    assert fresh_store.is_sensor_online() is True


def test_sensor_offline_once_stale(fresh_store):
    fresh_store.ingest(IngestPayload(temp_c=24.0, fan_pct=50, heater_on=False, seq=1))
    last = fresh_store.latest()
    future = last.ts + timedelta(seconds=config.STALE_AFTER_S + 1)
    assert fresh_store.is_sensor_online(now=future) is False


def test_sensor_online_just_under_the_threshold(fresh_store):
    fresh_store.ingest(IngestPayload(temp_c=24.0, fan_pct=50, heater_on=False, seq=1))
    last = fresh_store.latest()
    future = last.ts + timedelta(seconds=config.STALE_AFTER_S - 0.5)
    assert fresh_store.is_sensor_online(now=future) is True


def test_no_data_is_not_online(fresh_store):
    assert fresh_store.is_sensor_online() is False
    assert fresh_store.data_age_s() is None
