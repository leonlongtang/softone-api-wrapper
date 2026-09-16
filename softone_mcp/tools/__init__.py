"""
Agent-facing tools ("business actions").

These tools sit above the raw CRUD helpers in `softone_mcp.internal` and the
domain logic in `softone_mcp.business`. They are the only layer that owns the
`{"ok": bool, ...}` envelope returned to the MCP agent.
"""

