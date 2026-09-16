from __future__ import annotations

from typing import Any, Protocol


class SoftOneGateway(Protocol):
    def call(self, *, base_url: str, payload: dict[str, Any]) -> dict[str, Any]: ...

