from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SoftOneAppConfig:
    """
    Runtime configuration for local testing.

    Set via environment variables:
    - SOFTONE_MOCK: "1" / "true" to use the local mock backend
    - SOFTONE_BASE_URL: e.g. "https://demo.oncloud.gr/s1services"
    - SOFTONE_USERNAME
    - SOFTONE_PASSWORD
    - SOFTONE_APP_ID: e.g. "2001"
    """

    mock: bool
    base_url: str
    username: str
    password: str
    app_id: str


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_dotenv(dotenv_path: str | os.PathLike[str] = ".env") -> None:
    """
    Minimal .env loader (no external dependencies).

    - Ignores comments/blank lines
    - Supports KEY=VALUE (no interpolation)
    - Does not override existing environment variables
    """
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config() -> SoftOneAppConfig:
    load_dotenv()
    mock = _env_bool("SOFTONE_MOCK", default=True)

    # Defaults match the seeded mock credentials.
    # `or` (not a getenv default) so blank values copied from .env.example still fall back.
    base_url = os.getenv("SOFTONE_BASE_URL") or "mock://"
    username = os.getenv("SOFTONE_USERNAME") or "john"
    password = os.getenv("SOFTONE_PASSWORD") or "aitis"
    app_id = os.getenv("SOFTONE_APP_ID") or "2001"

    return SoftOneAppConfig(
        mock=mock,
        base_url=base_url,
        username=username,
        password=password,
        app_id=app_id,
    )

