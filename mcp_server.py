"""
Backward-compatible entrypoint for the MCP server.

The organized implementation lives in the `softone_mcp/` package.
Import `mcp` from here if you were already using `mcp_server:mcp`.
"""

from softone_mcp.server import mcp  # noqa: F401