from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class AppConfig:
    config_file: str
    ha_options_file: Path
    storage_dir: Path
    cache_dir: Path
    consumption_cache_dir: Path
    export_cache_dir: Path
    options_backup_file: Path
    fees_history_file: Path


@dataclass
class AppContainer:
    config: AppConfig


def build_container() -> AppContainer:
    config_file = "config.yaml"
    ha_options_file = Path("/data/options.json")
    config_dir = Path("/config")
    storage_env = os.getenv("ELEKTROAPP_STORAGE")
    if storage_env:
        storage_dir = Path(storage_env)
    else:
        storage_dir = config_dir / "elektroapp" if config_dir.exists() else Path("/data")

    cache_dir = storage_dir / "prices-cache"
    consumption_cache_dir = storage_dir / "consumption-cache"
    export_cache_dir = storage_dir / "export-cache"
    options_backup_file = storage_dir / "options.json"
    fees_history_file = storage_dir / "fees-history.json"

    return AppContainer(
        config=AppConfig(
            config_file=config_file,
            ha_options_file=ha_options_file,
            storage_dir=storage_dir,
            cache_dir=cache_dir,
            consumption_cache_dir=consumption_cache_dir,
            export_cache_dir=export_cache_dir,
            options_backup_file=options_backup_file,
            fees_history_file=fees_history_file,
        )
    )
