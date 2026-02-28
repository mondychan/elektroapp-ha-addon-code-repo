import pathlib
import sys

import pytest


BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app_service  # noqa: E402


@pytest.fixture
def backend_main():
    return app_service


@pytest.fixture
def isolated_storage(monkeypatch, tmp_path, backend_main):
    storage_dir = tmp_path / "storage"
    cache_dir = storage_dir / "prices-cache"
    consumption_cache_dir = storage_dir / "consumption-cache"
    export_cache_dir = storage_dir / "export-cache"

    monkeypatch.setattr(backend_main, "STORAGE_DIR", storage_dir)
    monkeypatch.setattr(backend_main, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(backend_main, "CONSUMPTION_CACHE_DIR", consumption_cache_dir)
    monkeypatch.setattr(backend_main, "EXPORT_CACHE_DIR", export_cache_dir)
    monkeypatch.setattr(backend_main, "OPTIONS_BACKUP_FILE", storage_dir / "options.json")
    monkeypatch.setattr(backend_main, "FEES_HISTORY_FILE", storage_dir / "fees-history.json")
    monkeypatch.setattr(backend_main, "PRICES_CACHE", {})
    monkeypatch.setattr(backend_main, "PRICES_CACHE_PROVIDER", {})

    return {
        "storage_dir": storage_dir,
        "cache_dir": cache_dir,
        "consumption_cache_dir": consumption_cache_dir,
        "export_cache_dir": export_cache_dir,
    }
