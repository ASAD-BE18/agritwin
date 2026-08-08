import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.store import ReadingStore
import app.store as store_module
import app.main as main_module


@pytest.fixture
def fresh_store(monkeypatch, tmp_path):
    """Every test gets an isolated ring buffer instead of sharing the module-level
    singleton — otherwise tests would leak state into each other. Also redirects the
    audit log to a temp file so tests don't write into the repo working directory."""
    new_store = ReadingStore()
    monkeypatch.setattr(store_module, "store", new_store)
    monkeypatch.setattr(main_module, "store", new_store)
    monkeypatch.setattr(config, "AUDIT_LOG_PATH", str(tmp_path / "control_audit.jsonl"))
    return new_store


@pytest.fixture
def client(fresh_store):
    return TestClient(app)


@pytest.fixture
def api_key_headers():
    return {"X-API-Key": config.API_KEY}
