import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import config_loader


def restored_history():
    snapshot = {
        "dph_percent": 21.0,
        "kwh_fees": {
            "komodita_sluzba": 0.35,
            "oze": 0.495,
            "dan": 0.0283,
            "systemove_sluzby": 0.17092,
            "distribuce": {"NT": 0.206, "VT": 0.72145},
        },
        "fixed": {
            "daily": {"staly_plat": 4.18},
            "monthly": {"provoz_nesitove_infrastruktury": 12.45, "jistic": 600.0},
        },
        "prodej": {"koeficient_snizeni_ceny": 450.0},
        "extension": {"preserve": True},
    }
    second = json.loads(json.dumps(snapshot))
    second["kwh_fees"]["oze"] = 0
    second["kwh_fees"]["systemove_sluzby"] = 0.16424
    second["kwh_fees"]["distribuce"] = {"NT": 0.1165, "VT": 0.75477}
    second["fixed"]["monthly"] = {"provoz_nesitove_infrastruktury": 12.87, "jistic": 710.0}
    second["prodej"]["koeficient_snizeni_ceny"] = 390.0
    third = json.loads(json.dumps(second))
    third["prodej"]["koeficient_snizeni_ceny"] = 350.0
    return [
        {"effective_from": "2025-01-01", "effective_to": "2025-12-31", "snapshot": snapshot},
        {"effective_from": "2026-01-01", "effective_to": "2026-01-14", "snapshot": second},
        {"effective_from": "2026-01-15", "snapshot": third},
    ]


def test_migration_preserves_restored_history_and_is_idempotent(isolated_storage):
    original = restored_history()
    isolated_storage["storage_dir"].mkdir(parents=True, exist_ok=True)
    config_loader.FEES_HISTORY_FILE.write_text(json.dumps(original), encoding="utf-8")

    assert config_loader.migrate_fee_history() == 3
    migrated = config_loader.load_fee_history()
    assert [(item["effective_from"], item.get("effective_to")) for item in migrated] == [
        ("2025-01-01", "2025-12-31"),
        ("2026-01-01", "2026-01-14"),
        ("2026-01-15", None),
    ]
    for old, new in zip(original, migrated):
        for key, value in old["snapshot"].items():
            if key in {"prodej", "nakup"}:
                assert {name: new["snapshot"][key][name] for name in value} == value
            else:
                assert new["snapshot"][key] == value
        assert new["snapshot"]["prodej"]["fixni_cena_enabled"] is False
        assert new["snapshot"]["prodej"]["fixni_cena"] == 0
        assert new["snapshot"]["nakup"] == {"fixni_cena_enabled": False, "fixni_cena": 0}
    backups = list(isolated_storage["storage_dir"].glob("fees-history.json.*.bak"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8")) == original

    migrated_content = config_loader.FEES_HISTORY_FILE.read_text(encoding="utf-8")
    assert config_loader.migrate_fee_history() == 0
    assert config_loader.FEES_HISTORY_FILE.read_text(encoding="utf-8") == migrated_content
    assert len(list(isolated_storage["storage_dir"].glob("fees-history.json.*.bak"))) == 1


def test_migration_refuses_invalid_history_without_changing_source(isolated_storage):
    path = config_loader.FEES_HISTORY_FILE
    isolated_storage["storage_dir"].mkdir(parents=True, exist_ok=True)
    path.write_text("[{broken", encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        config_loader.migrate_fee_history()

    assert path.read_bytes() == original
    assert not list(isolated_storage["storage_dir"].glob("fees-history.json.*.bak"))


def test_fee_history_backup_is_kept_if_atomic_replace_fails(isolated_storage, monkeypatch):
    path = config_loader.FEES_HISTORY_FILE
    isolated_storage["storage_dir"].mkdir(parents=True, exist_ok=True)
    original = restored_history()
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(config_loader.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))

    with pytest.raises(OSError, match="replace failed"):
        config_loader.migrate_fee_history()

    assert json.loads(path.read_text(encoding="utf-8")) == original
    backups = list(isolated_storage["storage_dir"].glob("fees-history.json.*.bak"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8")) == original


def test_startup_migrates_before_services(monkeypatch):
    import main

    calls = []
    monkeypatch.setattr(main.config_loader, "migrate_fee_history", lambda: calls.append("migrate"))
    monkeypatch.setattr(main.app_service, "start_prefetch_scheduler", lambda: calls.append("prefetch"))
    monkeypatch.setattr(main.app_service, "start_pnd_scheduler", lambda: calls.append("pnd"))
    monkeypatch.setattr(main.app_service, "start_dip_scheduler", lambda: calls.append("dip"))
    monkeypatch.setattr(main.app_service, "log_cache_status", lambda: calls.append("cache"))

    main.startup_hook()

    assert calls == ["migrate", "prefetch", "pnd", "dip", "cache"]
