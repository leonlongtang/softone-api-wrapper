# Agent prompt policy

This page documents the **baseline system prompt policy** we expect to apply when we introduce dedicated agents (Sales, Inventory, AR, Payments, Orchestrator).

It is intentionally short and references MCP **resources** as the source of truth.

## Baseline policy (copy/paste into agent/system prompt)

Before using any tools:
- Read resource: `softone://capabilities`
- Read resource: `softone://glossary`

Before any write (any tool marked `side_effects="writes"` in `softone://capabilities`):
- Prefer visibility tools first (`search_*`, `list_*`, `get_*`).
- Read the relevant contract resource:
  - `softone://contracts/customer`
  - `softone://contracts/item`
  - `softone://contracts/order`
  - `softone://contracts/invoice`
- Follow the canonical workflow when applicable:
  - `softone://workflows/order_to_cash`

Rules:
- Do not guess IDs; discover them via `search_*` / `list_*` / `get_*`.
- Do not use mock-only tools unless explicitly running in mock mode (see `softone://capabilities`).
- If an operation fails, re-check the contract + glossary and retry with corrected inputs.

