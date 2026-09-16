from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .data import CAPABILITIES, CONTRACTS, EXAMPLES_MD, GLOSSARY_MD, ORDER_TO_CASH_MD


def register_resources(mcp: FastMCP) -> None:
    # Capabilities / tool catalog
    @mcp.resource(
        "softone://capabilities",
        title="SoftOne MCP capabilities",
        description="Tool catalog, vocabularies, and safety rules (no tenant data).",
        mime_type="application/json",
    )
    def capabilities_resource():
        return CAPABILITIES

    # Glossary (terminology + table distinctions)
    @mcp.resource(
        "softone://glossary",
        title="Glossary",
        description="Terminology and key distinctions (e.g., invoices vs invoices_business).",
        mime_type="text/markdown",
    )
    def glossary_resource() -> str:
        return GLOSSARY_MD

    # Workflows
    @mcp.resource(
        "softone://workflows/order_to_cash",
        title="Workflow: Order to Cash",
        description="Canonical tool sequence for customer → order → invoice → payment.",
        mime_type="text/markdown",
    )
    def order_to_cash_resource() -> str:
        return ORDER_TO_CASH_MD

    # Contracts
    @mcp.resource(
        "softone://contracts/customer",
        title="Contract: Customer",
        description="Field-level contract for customer tools.",
        mime_type="application/json",
    )
    def contract_customer_resource():
        return CONTRACTS["customer"]

    @mcp.resource(
        "softone://contracts/item",
        title="Contract: Item",
        description="Field-level contract for item tools.",
        mime_type="application/json",
    )
    def contract_item_resource():
        return CONTRACTS["item"]

    @mcp.resource(
        "softone://contracts/order",
        title="Contract: Order",
        description="Field-level contract for order tools.",
        mime_type="application/json",
    )
    def contract_order_resource():
        return CONTRACTS["order"]

    @mcp.resource(
        "softone://contracts/invoice",
        title="Contract: Invoice",
        description="Field-level contract for invoice tools.",
        mime_type="application/json",
    )
    def contract_invoice_resource():
        return CONTRACTS["invoice"]

    # Examples
    @mcp.resource(
        "softone://examples",
        title="Examples",
        description="Minimal end-to-end examples of common flows.",
        mime_type="text/markdown",
    )
    def examples_resource() -> str:
        return EXAMPLES_MD

