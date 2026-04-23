from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo as tzinfo_type
from typing import Any

from api import get_local_tz
from application import ApplicationServices
import app_service as svc
from fastapi import Request


@dataclass
class RequestContext:
    config: dict[str, Any]
    tzinfo: tzinfo_type


def get_request_context() -> RequestContext:
    cfg = svc.load_config()
    tz = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    return RequestContext(config=cfg, tzinfo=tz)


_DEFAULT_APPLICATION_SERVICES = ApplicationServices()


def get_application_services(request: Request) -> ApplicationServices:
    container = getattr(request.app.state, "container", None)
    services = getattr(container, "application", None)
    return services if isinstance(services, ApplicationServices) else _DEFAULT_APPLICATION_SERVICES
