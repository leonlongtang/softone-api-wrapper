"""Unified multi-runtime agent infrastructure (model-agnostic specs + runtimes).

This package is intentionally runtime-agnostic:
- Agents are defined once (AgentSpec).
- Runtimes execute those specs (Ollama, Claude SDK, later others).
- Orchestrators (LangGraph) route between AgentSpecs without knowing runtime details.
"""

