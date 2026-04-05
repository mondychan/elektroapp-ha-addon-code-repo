import json
import os

import app_service
import config_loader


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


def test_save_config_writes_ha_and_backup_options(isolated_storage):
    payload = {
        "dph": 21,
        "price_provider": "spotovaelektrina.cz",
        "pnd": {
            "enabled": True,
            "username": "user@example.com",
            "password": "secret",
            "meter_id": "3000012345",
        },
    }

    response = app_service.save_config(payload)

    assert response["status"] == "ok"
    ha_options = json.loads(isolated_storage["ha_options_file"].read_text(encoding="utf-8"))
    backup_options = json.loads((isolated_storage["storage_dir"] / "options.json").read_text(encoding="utf-8"))
    assert ha_options["pnd"]["username"] == "user@example.com"
    assert backup_options["pnd"]["username"] == "user@example.com"
