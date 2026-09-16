from __future__ import annotations

import logging
import os
from dataclasses import dataclass


def _env_bool(name: str, *, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True, slots=True)
class AgentPlatformSettings:
    debug: bool = False

    ollama_model: str | None = None
    claude_model: str | None = None
    claude_fallback_model: str | None = None

    anthropic_api_key_present: bool = False


def load_agent_platform_settings(*, cli_debug: bool = False) -> AgentPlatformSettings:
    debug = bool(cli_debug) or _env_bool("OLLAMA_MCP_DEBUG", default=False)

    return AgentPlatformSettings(
        debug=debug,
        ollama_model=(os.getenv("OLLAMA_MODEL") or "").strip() or None,
        claude_model=(os.getenv("CLAUDE_MODEL") or "").strip() or None,
        claude_fallback_model=(os.getenv("CLAUDE_FALLBACK_MODEL") or "").strip() or None,
        anthropic_api_key_present=bool((os.getenv("ANTHROPIC_API_KEY") or "").strip()),
    )


def configure_logging(*, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


__all__ = ["AgentPlatformSettings", "load_agent_platform_settings", "configure_logging"]

