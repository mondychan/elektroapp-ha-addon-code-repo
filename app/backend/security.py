from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import Header, HTTPException, Request


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _host_without_port(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"http://{value}")
    return (parsed.hostname or "").lower()


def _is_same_origin(request: Request) -> bool:
    host = _host_without_port(request.headers.get("host"))
    origin = _host_without_port(request.headers.get("origin"))
    referer = _host_without_port(request.headers.get("referer"))
    if origin:
        return origin == host
    if referer:
        return referer == host
    return True


def _looks_like_ha_ingress(request: Request) -> bool:
    headers = request.headers
    return any(
        headers.get(name)
        for name in (
            "x-ingress-path",
            "x-hassio-ingress",
            "x-home-assistant-ingress",
            "x-forwarded-host",
        )
    )


async def require_mutation_access(
    request: Request,
    x_elektroapp_token: str | None = Header(default=None, alias="X-Elektroapp-Token"),
):
    if request.method.upper() not in MUTATING_METHODS:
        return

    configured_token = os.getenv("ELEKTROAPP_API_TOKEN")
    if configured_token:
        auth_header = request.headers.get("authorization", "")
        bearer = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else None
        if x_elektroapp_token == configured_token or bearer == configured_token:
            return
        if _looks_like_ha_ingress(request) and _is_same_origin(request):
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "mutation_forbidden",
                "message": "Mutation endpoint requires Home Assistant Ingress or ELEKTROAPP_API_TOKEN.",
            },
        )

    if not _is_same_origin(request):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "cross_origin_mutation_forbidden",
                "message": "Cross-origin mutation requests are not allowed.",
            },
        )
