from __future__ import annotations

from softone_mcp.catalog import CATALOG_PATH, render


def test_tools_catalog_matches_live_server() -> None:
    assert CATALOG_PATH.read_text(encoding="utf-8") == render(), "Run `python -m softone_mcp.catalog`."
