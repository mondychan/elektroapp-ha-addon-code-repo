import os
import time


def test_prices_cache_roundtrip_and_provider_metadata(backend_main, isolated_storage):
    date_str = "2026-02-10"
    entries = [{"time": "2026-02-10 00:00", "spot": 1.23, "final": 2.34}]

    backend_main.save_prices_cache(date_str, entries, provider="ote-cr.cz")

    loaded_entries = backend_main.load_prices_cache(date_str)
    loaded_meta = backend_main.load_prices_cache_meta(date_str)
    cached_provider = backend_main.get_cached_price_provider(date_str)

    assert loaded_entries == entries
    assert loaded_meta["provider"] == "ote"
    assert cached_provider == "ote"
    assert backend_main.is_price_cache_provider_match(date_str, "ote") is True
    assert backend_main.is_price_cache_provider_match(date_str, "spotovaelektrina") is False


def test_clear_prices_cache_for_date_removes_files(backend_main, isolated_storage):
    date_str = "2026-02-11"
    backend_main.save_prices_cache(date_str, [{"time": "2026-02-11 00:00"}], provider="spot")

    cache_path = backend_main.get_prices_cache_path(date_str)
    meta_path = backend_main.get_prices_cache_meta_path(date_str)
    assert cache_path.exists()
    assert meta_path.exists()

    backend_main.clear_prices_cache_for_date(date_str, remove_files=True)
    assert not cache_path.exists()
    assert not meta_path.exists()


def test_consumption_cache_key_mismatch_returns_empty(backend_main, isolated_storage):
    date_str = "2026-02-12"
    key_ok = {"entity_id": "sensor.a", "cache_version": 2}
    key_bad = {"entity_id": "sensor.b", "cache_version": 2}
    data = {"points": [{"time": "2026-02-12T00:00:00Z", "kwh": 0.5}]}

    backend_main.save_consumption_cache(date_str, key_ok, data)
    loaded, path, meta = backend_main.load_consumption_cache(date_str, key_bad)

    assert loaded is None
    assert path is None
    assert meta is None


def test_consumption_cache_roundtrip(backend_main, isolated_storage):
    date_str = "2026-02-13"
    key = {"entity_id": "sensor.load", "cache_version": 2}
    data = {"points": [{"time": "2026-02-13T00:00:00Z", "kwh": 1.0}]}

    backend_main.save_consumption_cache(date_str, key, data)
    loaded, path, meta = backend_main.load_consumption_cache(date_str, key)

    assert loaded == data
    assert path.exists()
    assert meta["key"] == key


def test_export_cache_roundtrip(backend_main, isolated_storage):
    date_str = "2026-02-14"
    key = {"entity_id": "sensor.export", "cache_version": 2}
    data = {"points": [{"time": "2026-02-14T00:00:00Z", "kwh": 0.2}]}

    backend_main.save_export_cache(date_str, key, data)
    loaded, path, meta = backend_main.load_export_cache(date_str, key)

    assert loaded == data
    assert path.exists()
    assert meta["key"] == key


def test_is_cache_fresh_works_for_recent_and_stale_files(backend_main, isolated_storage):
    cache_file = isolated_storage["storage_dir"] / "freshness.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{}", encoding="utf-8")

    assert backend_main.is_cache_fresh(cache_file, 60) is True

    stale_mtime = time.time() - 3600
    os.utime(cache_file, (stale_mtime, stale_mtime))
    assert backend_main.is_cache_fresh(cache_file, 60) is False
