import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Tuple, Optional

logger = logging.getLogger("uvicorn.error")

class SeriesCache:
    """Generic cache for time-series data (consumption, export)."""
    def __init__(self, prefix: str, cache_dir: Path, ttl_seconds: int, version: int = 2):
        self.prefix = prefix
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.version = version

    def build_path(self, date_str: str) -> Path:
        return self.cache_dir / f"{self.prefix}-{date_str}.json"

    def load(self, date_str: str, cache_key: Any) -> Tuple[Optional[Any], Optional[Path], Optional[dict]]:
        path = self.build_path(date_str)
        if not path.exists():
            return None, None, None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError, TypeError):
            return None, None, None
        
        if not isinstance(payload, dict):
            return None, None, None
        
        meta = payload.get("meta", {})
        if meta.get("key") != cache_key:
            return None, None, None
            
        data = payload.get("data")
        if data is None:
            return None, None, None
        return data, path, meta

    def save(self, date_str: str, cache_key: Any, data: Any):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.build_path(date_str)
        payload = {
            "meta": {
                "key": cache_key, 
                "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            "data": data,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        logger.info("Saved %s cache for %s to %s", self.prefix, date_str, path)

    def get_status(self) -> dict:
        if not self.cache_dir.exists():
            return {"dir": str(self.cache_dir), "count": 0, "latest": None, "size_bytes": 0}
        files = []
        for file_path in self.cache_dir.glob(f"{self.prefix}-*.json"):
            suffix = file_path.stem.replace(f"{self.prefix}-", "", 1)
            if re.match(r"^\d{4}-\d{2}-\d{2}$", suffix):
                files.append(file_path)
        files.sort()
        latest = None
        total_size = 0
        if files:
            latest = files[-1].stem.replace(f"{self.prefix}-", "")
            total_size = sum(file_path.stat().st_size for file_path in files)
        return {"dir": str(self.cache_dir), "count": len(files), "latest": latest, "size_bytes": total_size}

def build_series_cache_key(influx_cfg: dict, entity_id: str, version: int = 2) -> dict:
    return {
        "cache_version": version,
        "entity_id": entity_id,
        "measurement": influx_cfg.get("measurement"),
        "field": influx_cfg.get("field"),
        "interval": influx_cfg.get("interval", "15m"),
        "retention_policy": influx_cfg.get("retention_policy"),
        "timezone": influx_cfg.get("timezone"),
    }
