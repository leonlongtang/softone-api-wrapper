from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from ..domain.errors import InvalidRequest, SoftOneError
from .gateway import SoftOneGateway


@dataclass(frozen=True)
class HttpGatewayConfig:
    timeout_seconds: float = 30.0
    user_agent: str = "softone-wrapper/0.1"
    verify_tls: bool = True  # kept for future extension; urllib verifies by default


class HttpGateway(SoftOneGateway):
    def __init__(self, *, config: Optional[HttpGatewayConfig] = None) -> None:
        self._config = config or HttpGatewayConfig()

    def call(self, *, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            base_url,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": self._config.user_agent,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # Try to parse error body as JSON if present.
            try:
                raw = e.read().decode("utf-8")
                return json.loads(raw)
            except Exception as parse_exc:  # noqa: BLE001
                raise InvalidRequest(-9, f"HTTP error {e.code}", {"exception": str(parse_exc)}) from e
        except urllib.error.URLError as e:
            raise SoftOneError(-9, "Network error", {"exception": str(e)}) from e

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise InvalidRequest(-9, "Invalid JSON response", {"raw": raw[:500]}) from e

