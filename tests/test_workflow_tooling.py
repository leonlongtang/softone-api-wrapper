from __future__ import annotations

from agent_platform.specs import ops_workflows_agent_spec


def test_ops_workflows_spec_prefers_workflows() -> None:
    spec = ops_workflows_agent_spec()
    assert "workflow_create_order" in spec.tool_names
    assert "workflow_order_to_cash" in spec.tool_names
    assert "check_inventory" in spec.tool_names

