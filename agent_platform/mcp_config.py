from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    name: str
    transport: str
    command: str
    args: list[str]
    cwd: str
    env: dict[str, str]


def softone_stdio_server_config(*, repo_root: Path = REPO_ROOT) -> McpServerConfig:
    return McpServerConfig(
        name="softone",
        transport="stdio",
        command=sys.executable,
        args=["-m", "softone_mcp.server"],
        cwd=str(repo_root),
        env=dict(os.environ),
    )

