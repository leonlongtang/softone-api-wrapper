"""SoftOne agent platform: a LangGraph router in front of department agents that use SoftOne MCP tools.

- specs.py    department agents (sales / inventory / finance): prompt + scoped tool allowlist
- router.py   deterministic keyword router, or "clarify" when ambiguous
- graph.py    LangGraph orchestrator: route -> run agent -> recover / escalate
- runtimes/   the same specs on Ollama (local) or the Claude Agent SDK
"""
