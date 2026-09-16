from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .deps import build_client
from .resources.register import register_resources
from .tools.connect import register_connect_tools
from .tools.customers import register_customer_tools
from .tools.invoices import register_invoice_tools
from .tools.items import register_item_tools
from .tools.orders import register_order_tools
from .tools.payments import register_payment_tools


mcp = FastMCP()

# One client per process (keeps wrapper's in-memory session store).
client = build_client()

register_connect_tools(mcp, client)
register_customer_tools(mcp, client)
register_item_tools(mcp, client)
register_order_tools(mcp, client)
register_invoice_tools(mcp, client)
register_payment_tools(mcp, client)
register_resources(mcp)


def main() -> None:
    # Default transport is stdio, which is what Claude Code SDK expects for
    # subprocess MCP servers.
    mcp.run()


if __name__ == "__main__":
    main()
