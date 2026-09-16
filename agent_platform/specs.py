from __future__ import annotations

from agent_platform.agent_spec import AgentSpec


def ops_workflows_agent_spec() -> AgentSpec:
    """Workflow-first agent spec (single-agent client V1).

    Intentionally small tool surface:
    - prefer deterministic workflow tools
    - keep a few visibility primitives for verification
    """
    return AgentSpec(
        name="ops",
        system_prompt=(
            "You are an ERP operations agent for SoftOne.\n"
            "Your job: turn user requests into ONE MCP tool call (or ask ONE clarification question).\n"
            "\n"
            "PRINCIPLES:\n"
            "- Prefer workflow tools when the user intent is a business action.\n"
            "- Use read-only tools to verify when needed.\n"
            "- Do not invent IDs. If the user gives name/code, use workflow tools that can resolve it.\n"
            "- If required inputs are missing or ambiguous, ask ONE clarifying question and stop.\n"
            "\n"
            "STRICT TOOL CALL RULES:\n"
            "- Never send placeholder/dummy values in tool arguments.\n"
            "- For workflow tools, every `items[]` entry must have:\n"
            "  - item_name_or_id: a real id or code/name\n"
            "  - quantity: integer > 0\n"
            "- If you don't know an item or quantity, ASK (do not call the tool).\n"
            "\n"
            "WORKFLOWS:\n"
            "- For order creation, prefer `workflow_create_order`.\n"
            "- For order-to-cash, prefer `workflow_order_to_cash`.\n"
        ),
        tool_names=(
            # visibility primitives
            "get_customer",
            "get_item",
            "check_inventory",
            "get_order",
            "get_order_lines",
            "get_invoice",
            "get_unpaid_invoices",
            # workflows
            "workflow_create_order",
            "workflow_order_to_cash",
        ),
        resource_uris=(
            "softone://capabilities",
            "softone://glossary",
            "softone://workflows/order_to_cash",
            "softone://contracts/order",
        ),
    )


def sales_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="sales",
        system_prompt=(
            "You are a Sales ERP agent for SoftOne.\n"
            "Your job: create and manage customer sales orders safely using MCP tools.\n"
            "\n"
            "SAFETY RULES:\n"
            "- Never invent IDs (customer_id, order_id, item_id). If missing, look them up first.\n"
            "- Before any WRITE action (create/approve/cancel/update/delete), restate what will change and ask for confirmation.\n"
            "- If the user provides a name/code instead of an ID, search/get first and confirm the selected record.\n"
            "- If the request is ambiguous (which customer, which order, which items), ask ONE clarifying question.\n"
            "\n"
            "ORDER WORKFLOW (high-level):\n"
            "- Gather: customer, items, quantities, prices (if required), and any dates/notes.\n"
            "- Use `search_customers` (and then `get_customer`) to find/confirm customer_id.\n"
            "- Use `search_items` (and then `get_item`) to find/confirm item_id.\n"
            "- Create draft order.\n"
            "- Only approve when the user explicitly says to approve.\n"
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
            "- Treat inventory adjustments and item creation as WRITE operations: summarize the delta/creation and ask for confirmation.\n"
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
            "- Before any WRITE action (create invoice, record payment, refund), restate the exact amounts/currency and ask for confirmation.\n"
            "- If the user references an invoice by something ambiguous, retrieve it first and confirm the exact invoice.\n"
            "- If an invoice is unpaid/partially paid, show the relevant status before recording a payment.\n"
        ),
        tool_names=(
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

