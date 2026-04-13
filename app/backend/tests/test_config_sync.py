import json
import os

import app_service
import config_loader
from fastapi import HTTPException


class DummySupervisorService:
    def __init__(self, *, available=True, response=None, error=None):
        self.available = available
        self.response = response or {"ok": True, "message": "synced"}
        self.error = error
        self.calls = []

    def is_available(self):
        return self.available

    def sync_addon_options(self, options):
        self.calls.append(options)
        if self.error:
            raise self.error
        return self.response


def test_load_config_prefers_newer_backup_over_ha_options(isolated_storage):
    config_path = isolated_storage["config_file"]
    ha_options_path = isolated_storage["ha_options_file"]
    backup_path = isolated_storage["storage_dir"] / "options.json"

    config_path.write_text("price_provider: spotovaelektrina\npnd:\n  enabled: false\n", encoding="utf-8")
    ha_options_path.parent.mkdir(parents=True, exist_ok=True)
    ha_options_path.write_text(json.dumps({"pnd": {"enabled": True, "username": "ha-user"}}), encoding="utf-8")
    backup_path.write_text(json.dumps({"pnd": {"enabled": True, "username": "ui-user"}}), encoding="utf-8")

    # Ensure backup is newer than HA options.
    ha_mtime = ha_options_path.stat().st_mtime
    os.utime(ha_options_path, (ha_mtime, ha_mtime))
    backup_mtime = ha_mtime + 5
    os.utime(backup_path, (backup_mtime, backup_mtime))

    loaded = config_loader.load_config()

    assert loaded["pnd"]["username"] == "ui-user"
    mirrored = json.loads(ha_options_path.read_text(encoding="utf-8"))
    assert mirrored["pnd"]["username"] == "ui-user"


def test_save_config_writes_ha_and_backup_options(isolated_storage, monkeypatch):
    supervisor = DummySupervisorService()
    monkeypatch.setattr(app_service, "SUPERVISOR_SERVICE", supervisor)
    payload = {
        "dph": 21,
        "price_provider": "spotovaelektrina.cz",
        "pnd": {
            "enabled": True,
            "username": "user@example.com",
            "password": "secret",
            "meter_id": "3000012345",
        },
        "hp": {
            "enabled": True,
            "entities": [
                {
                    "entity_id": "sensor.ebusd_ha_daemon_hmu_currentyieldpower",
                    "label": "Yield",
                    "display_kind": "numeric",
                    "source_kind": "instant",
                    "kpi_enabled": True,
                    "chart_enabled": True,
                    "kpi_mode": "last",
                    "unit": "kW",
                }
            ],
        },
    }

    response = app_service.save_config(payload)

    assert response["status"] == "ok"
    ha_options = json.loads(isolated_storage["ha_options_file"].read_text(encoding="utf-8"))
    backup_options = json.loads((isolated_storage["storage_dir"] / "options.json").read_text(encoding="utf-8"))
    assert ha_options["pnd"]["username"] == "user@example.com"
    assert backup_options["pnd"]["username"] == "user@example.com"
    assert ha_options["hp"]["entities"][0]["entity_id"] == "sensor.ebusd_ha_daemon_hmu_currentyieldpower"
    assert backup_options["hp"]["enabled"] is True
    assert supervisor.calls and supervisor.calls[0]["hp"]["enabled"] is True
    assert response["supervisor_sync"]["ok"] is True


def test_load_config_prefers_custom_backup_over_newer_default_ha_options(isolated_storage):
    config_path = isolated_storage["config_file"]
    ha_options_path = isolated_storage["ha_options_file"]
    backup_path = isolated_storage["storage_dir"] / "options.json"

    config_path.write_text(
        "price_provider: spotovaelektrina.cz\nhp:\n  enabled: false\n  entities: []\n",
        encoding="utf-8",
    )
    backup_payload = {
        "price_provider": "spotovaelektrina.cz",
        "hp": {
            "enabled": True,
            "entities": [
                {
                    "entity_id": "sensor.ebusd_ha_daemon_broadcast_outsidetemp",
                    "label": "Outside temp",
                    "display_kind": "numeric",
                    "source_kind": "instant",
                    "kpi_enabled": True,
                    "chart_enabled": True,
                    "kpi_mode": "last",
                    "unit": "°C",
                }
            ],
        },
    }
    ha_options_payload = {
        "price_provider": "spotovaelektrina.cz",
        "hp": {
            "enabled": False,
            "entities": [],
        },
    }

    ha_options_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(backup_payload), encoding="utf-8")
    ha_options_path.write_text(json.dumps(ha_options_payload), encoding="utf-8")

    ha_mtime = backup_path.stat().st_mtime + 5
    os.utime(ha_options_path, (ha_mtime, ha_mtime))

    loaded = config_loader.load_config()

    assert loaded["hp"]["enabled"] is True
    assert loaded["hp"]["entities"][0]["entity_id"] == "sensor.ebusd_ha_daemon_broadcast_outsidetemp"
    mirrored = json.loads(ha_options_path.read_text(encoding="utf-8"))
    assert mirrored["hp"]["enabled"] is True


def test_save_config_raises_when_supervisor_sync_fails_in_addon_runtime(isolated_storage, monkeypatch):
    from services.supervisor_service import SupervisorSyncError

    monkeypatch.setattr(
        app_service,
        "SUPERVISOR_SERVICE",
        DummySupervisorService(
            available=True,
            error=SupervisorSyncError(
                "Ulozeni do Supervisor options selhalo.",
                status_code=502,
                detail={"code": "supervisor_request_failed"},
            ),
        ),
    )

    payload = {
        "price_provider": "spotovaelektrina.cz",
        "hp": {
            "enabled": True,
            "entities": [{"entity_id": "sensor.ebusd_ha_daemon_broadcast_outsidetemp"}],
        },
    }

    try:
        app_service.save_config(payload)
        assert False, "save_config was expected to raise HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 502
        assert exc.detail["code"] == "supervisor_request_failed"

    backup_options = json.loads((isolated_storage["storage_dir"] / "options.json").read_text(encoding="utf-8"))
    assert backup_options["hp"]["enabled"] is True
