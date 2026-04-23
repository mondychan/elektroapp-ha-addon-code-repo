from __future__ import annotations

from typing import Any

import app_service as legacy_app_service


class ApplicationServices:
    """Application-layer facade used by the runtime container.

    The legacy app_service module remains the compatibility surface for old imports
    while orchestration can move behind this explicit facade incrementally.
    """

    def __init__(self, legacy_module=legacy_app_service):
        self._legacy = legacy_module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._legacy, name)
