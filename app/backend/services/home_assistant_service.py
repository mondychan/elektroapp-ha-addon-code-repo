from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import HTTPException


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class HomeAssistantService:
    def __init__(self, logger, base_url: str | None = None, token_env: str = "SUPERVISOR_TOKEN"):
        self.logger = logger
        self.base_url = (base_url or os.getenv("HA_CORE_API_URL") or "http://supervisor/core/api").rstrip("/")
        self.token_env = token_env
        self.session = requests.Session()

    def is_available(self) -> bool:
        return bool(os.getenv(self.token_env))

    def _build_headers(self) -> dict[str, str]:
        token = os.getenv(self.token_env)
        if not token:
            raise HTTPException(
                status_code=503,
                detail="Home Assistant API neni dostupne. Add-on potrebuje homeassistant_api a SUPERVISOR_TOKEN.",
            )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get_entity_state(self, entity_id: str) -> dict[str, Any]:
        if not entity_id:
            raise HTTPException(status_code=400, detail="entity_id je povinne.")
        url = f"{self.base_url}/states/{entity_id}"
        try:
            response = self.session.get(url, headers=self._build_headers(), timeout=10)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Entita '{entity_id}' nebyla v Home Assistant nalezena.")
            response.raise_for_status()
            payload = response.json()
        except HTTPException:
            raise
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Dotaz na Home Assistant API selhal: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Home Assistant API vratilo neplatny JSON.") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Home Assistant API vratilo neocekavanou odpoved.")
        return payload

    def get_states(self) -> list[dict[str, Any]]:
        url = f"{self.base_url}/states"
        try:
            response = self.session.get(url, headers=self._build_headers(), timeout=10)
            response.raise_for_status()
            payload = response.json()
        except HTTPException:
            raise
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Dotaz na Home Assistant API selhal: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Home Assistant API vratilo neplatny JSON.") from exc

        if not isinstance(payload, list):
            raise HTTPException(status_code=502, detail="Home Assistant API vratilo neocekavanou odpoved.")
        return payload

    def resolve_metadata_from_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity_id = payload.get("entity_id", "")
        attributes = payload.get("attributes", {}) if isinstance(payload.get("attributes"), dict) else {}
        state = payload.get("state")
        state_class = attributes.get("state_class")
        device_class = attributes.get("device_class")
        unit = attributes.get("unit_of_measurement")
        label = attributes.get("friendly_name") or entity_id

        is_numeric = False
        if entity_id.startswith("binary_sensor."):
            is_numeric = False
        elif state_class in {"measurement", "total", "total_increasing"}:
            is_numeric = True
        elif unit:
            is_numeric = True
        elif _safe_float(state) is not None:
            is_numeric = True

        if not is_numeric:
            display_kind = "state"
            source_kind = "state"
            kpi_mode = "last"
        else:
            display_kind = "numeric"
            source_kind = "counter" if state_class in {"total", "total_increasing"} else "instant"
            kpi_mode = "delta" if source_kind == "counter" else "last"

        return {
            "entity_id": entity_id,
            "label": str(label).strip(),
            "unit": str(unit).strip() if unit else None,
            "device_class": str(device_class).strip() if device_class else None,
            "state_class": str(state_class).strip() if state_class else None,
            "state": state,
            "display_kind": display_kind,
            "source_kind": source_kind,
            "kpi_mode": kpi_mode,
            "chart_enabled": display_kind == "numeric",
            "kpi_enabled": True,
        }

    def resolve_entity_metadata(self, entity_id: str) -> dict[str, Any]:
        payload = self.get_entity_state(entity_id)
        return self.resolve_metadata_from_state(payload)

    def resolve_entity_metadata_safe(self, entity_id: str) -> dict[str, Any] | None:
        try:
            return self.resolve_entity_metadata(entity_id)
        except HTTPException as exc:
            self.logger.warning("Home Assistant metadata resolve failed for %s: %s", entity_id, exc.detail)
            return None
