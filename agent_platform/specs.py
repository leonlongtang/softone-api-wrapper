"""Department agents: one AgentSpec per business area, each with a scoped tool allowlist."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """A runtime-agnostic agent definition: prompt, allowed MCP tools, resources to read first."""

    name: str
    system_prompt: str
    tool_names: tuple[str, ...] = ()
    resource_uris: tuple[str, ...] = ()


def sales_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="sales",
        system_prompt=(
            "You are a Sales ERP agent for SoftOne.\n"
            "Your job: create and manage customer sales orders safely using MCP tools.\n"
            "\n"
            "SAFETY RULES:\n"
            "- Never invent IDs (customer_id, order_id, item_id). If missing, look them up first.\n"
            "- If the user provides a name/code instead of an ID, search/get first and confirm the selected record.\n"
            "- If the request is ambiguous (which customer, which order, which items), ask ONE clarifying question.\n"
            "\n"
            "ORDER WORKFLOW (high-level):\n"
            "- Gather: customer, items, quantities, prices (if required), and any dates/notes.\n"
            "- Use `search_customers` (and then `get_customer`) to find/confirm customer_id.\n"
            "- Use `search_items` (and then `get_item`) to find/confirm item_id.\n"
            "- Create a draft order (prefer `workflow_create_order`: it resolves names/codes for you).\n"
            "- Only approve when the user explicitly says to approve.\n"
            "- For a full order -> invoice -> payment run, use `workflow_order_to_cash`.\n"
            "\n"
            "TOOL ARGUMENTS:\n"
            "- Never send placeholder values. Every `items[]` entry needs a real item id/code and a quantity > 0.\n"
            "- If you don't know an item or quantity, ASK instead of calling the tool.\n"
        ),
        tool_names=(
            # customers
            "create_customer",
            "get_customer",
            "update_customer",
            "delete_customer",
            "search_customers",
            # item lookup (useful for order creation)
            "get_item",
            "search_items",
            # orders
            "create_order",
            "update_order",
            "add_order_line",
            "remove_order_line",
            "approve_order",
            "get_order",
            "get_order_lines",
            "list_orders",
            "cancel_order",
            "check_inventory",
            # multi-step workflows
            "workflow_create_order",
            "workflow_order_to_cash",
        ),
        resource_uris=(
            "softone://contracts/customer",
            "softone://contracts/order",
            "softone://workflows/order_to_cash",
        ),
    )


def inventory_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="inventory",
        system_prompt=(
            "You are an Inventory ERP agent for SoftOne.\n"
            "Your job: manage catalog items and stock safely using MCP tools.\n"
            "\n"
            "SAFETY RULES:\n"
            "- Never invent item IDs. If the user gives a code/name, search/get first and confirm the chosen item.\n"
            "- Do NOT change inventory as a side effect of other workflows (e.g. order creation). Only do writes when the user explicitly asks to change stock or create/update items.\n"
            "- If stock is insufficient or constraints apply, explain clearly and ask how to proceed.\n"
            "\n"
            "DEFAULTS:\n"
            "- Prefer read-only checks first: search item, get item, get stock balance.\n"
        ),
        tool_names=(
            "create_item",
            "get_item",
            "update_item",
            "delete_item",
            "get_stock_balance",
            "inventory_adjustment",
            "search_items",
        ),
        resource_uris=("softone://contracts/item",),
    )


def finance_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="finance",
        system_prompt=(
            "You are a Finance/AR ERP agent for SoftOne.\n"
            "Your job: create invoices, record payments, and verify invoice/payment status.\n"
            "\n"
            "SAFETY RULES:\n"
            "- Never guess amounts, invoice IDs, or payment IDs.\n"
            "- If the user references an invoice by something ambiguous, retrieve it first and confirm the exact invoice.\n"
            "- If an invoice is unpaid/partially paid, show the relevant status before recording a payment.\n"
        ),
        tool_names=(
            # orders and customers are read-only here: invoicing needs to see them
            "get_order",
            "list_orders",
            "get_customer",
            "search_customers",
            "create_invoice",
            "get_unpaid_invoices",
            "get_invoice",
            "record_payment",
            "list_invoice_payments",
            "get_payment",
            "refund_payment",
        ),
        resource_uris=("softone://contracts/invoice", "softone://workflows/order_to_cash"),
    )



SPECS: dict[str, AgentSpec] = {s.name: s for s in (sales_agent_spec(), inventory_agent_spec(), finance_agent_spec())}
