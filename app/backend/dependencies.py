from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo as tzinfo_type
from typing import Any

from api import get_local_tz
import app_service as svc


@dataclass
class RequestContext:
    config: dict[str, Any]
    tzinfo: tzinfo_type


def get_request_context() -> RequestContext:
    cfg = svc.load_config()
    tz = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    return RequestContext(config=cfg, tzinfo=tz)
