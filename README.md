# SoftOne Agent Platform

An agentic integration layer over the SoftOne ERP system, built around the Model Context Protocol (MCP) and a LangGraph orchestrator.

## What it does

Rather than hand-coding a client for each SoftOne endpoint, this exposes ERP operations — customers, invoices, items, orders, payments — as MCP tools, and puts an LLM-driven orchestrator in front of them:

- **MCP server** (`softone_mcp/`): a full server exposing SoftOne business operations as MCP tools, layered into business logic / internal helpers / tool definitions per domain.
- **LangGraph orchestrator** (`agent_platform/orchestrator/`): routes each request to a domain-specific agent (sales, inventory, finance) using a combination of deterministic routing and explicit ambiguity handling (`router.py`, `graph.py`).
- **Structured agent specs**: each domain agent (`agent_platform/specs.py`, `agent_spec.py`) has explicit safety rules — e.g. never invent a record ID, confirm before any write operation.
- **Dual runtime support** (`agent_platform/runtimes/`): the same agent logic runs against either a local model via Ollama or Claude via the Claude Agent SDK, switchable with a `--runtime` flag.
- **Resilient tool calls**: a structured `ok/data/meta` (or `ok:false/error`) response envelope with retry-on-transient-failure handling, plus prompt-policy scaffolding that injects relevant MCP resource reads before tool use.

## Status

Runs end-to-end against a sandboxed mock backend (`SOFTONE_MOCK=true`, seeded mock data/credentials) — the orchestration, routing, and tool-calling logic is fully exercised, but it isn't yet wired up to a live SoftOne instance.

## Tech stack

Python, MCP, LangGraph, Claude Agent SDK, Ollama.

## Setup

```bash
cp .env.example .env   # defaults to SOFTONE_MOCK=true, no live credentials needed
pip install -e .
python -m agent_platform                 # interactive chat
python -m agent_platform "List unpaid invoices for customer 47"   # single-turn
```

Design docs, including the MCP tool catalogue and agent architecture notes, live under `docs/`.

## Development notes

Built with AI-assisted development (Claude Code): the architecture was directed from a rough initial design, then iterated on together — debugging failures and checking real outcomes — rather than accepted as generated output.
