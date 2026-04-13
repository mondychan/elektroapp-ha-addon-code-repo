from __future__ import annotations

import os
from typing import Any

import requests


class SupervisorSyncError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class SupervisorService:
    def __init__(self, logger, base_url: str | None = None, token_env: str = "SUPERVISOR_TOKEN"):
        self.logger = logger
        self.base_url = (base_url or os.getenv("SUPERVISOR_API_URL") or "http://supervisor").rstrip("/")
        self.token_env = token_env
        self.session = requests.Session()

    def is_available(self) -> bool:
        return bool(os.getenv(self.token_env))

    def _build_headers(self) -> dict[str, str]:
        token = os.getenv(self.token_env)
        if not token:
            raise SupervisorSyncError(
                "Supervisor API neni dostupne. Chybi SUPERVISOR_TOKEN.",
                detail={"code": "missing_supervisor_token"},
            )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def sync_addon_options(self, options: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(options, dict):
            options = {}
        options = self._strip_none_values(options)

        if not self.is_available():
            self.logger.info("Supervisor options sync skipped because SUPERVISOR_TOKEN is not available.")
            return {
                "ok": False,
                "skipped": True,
                "reason": "missing_supervisor_token",
                "message": "Supervisor sync preskocen mimo Home Assistant add-on runtime.",
            }

        url = f"{self.base_url}/addons/self/options"
        payload = {"options": options}
        try:
            response = self.session.post(url, headers=self._build_headers(), json=payload, timeout=10)
        except SupervisorSyncError:
            raise
        except requests.RequestException as exc:
            raise SupervisorSyncError(
                "Ulozeni do Supervisor options selhalo.",
                status_code=502,
                detail={"code": "supervisor_request_failed", "error": str(exc), "url": url},
            ) from exc

        parsed = self._parse_response_json(response, url)

        if response.status_code >= 400:
            detail: dict[str, Any] = {
                "code": "supervisor_http_error",
                "url": url,
                "status_code": response.status_code,
            }
            if parsed:
                detail["result"] = parsed.get("result")
                if parsed.get("message") is not None:
                    detail["message"] = parsed.get("message")
                if parsed.get("data") is not None:
                    detail["data"] = parsed.get("data")
            raise SupervisorSyncError(
                "Supervisor vratil chybu pri ukladani add-on options.",
                status_code=response.status_code,
                detail=detail,
            )

        if parsed and parsed.get("result") not in {None, "ok"}:
            raise SupervisorSyncError(
                "Supervisor odmitl ulozit add-on options.",
                status_code=502,
                detail={
                    "code": "supervisor_rejected",
                    "url": url,
                    "result": parsed.get("result"),
                    "message": parsed.get("message"),
                },
            )

        return {
            "ok": True,
            "message": "Konfigurace byla synchronizovana do Supervisor options.",
            "endpoint": "/addons/self/options",
        }

    def _strip_none_values(self, value: Any):
        if isinstance(value, dict):
            return {
                key: self._strip_none_values(item)
                for key, item in value.items()
                if item is not None
            }
        if isinstance(value, list):
            return [self._strip_none_values(item) for item in value]
        return value

    def _parse_response_json(self, response, url: str) -> dict[str, Any] | None:
        if not response.content:
            return None
        try:
            maybe_json = response.json()
        except ValueError as exc:
            raise SupervisorSyncError(
                "Supervisor API vratilo neplatny JSON.",
                status_code=502,
                detail={"code": "supervisor_invalid_json", "url": url},
            ) from exc
        return maybe_json if isinstance(maybe_json, dict) else None
