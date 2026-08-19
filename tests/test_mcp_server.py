from oncall_agent.mcp_server import mcp, query_cpu_metrics, query_logs


async def test_fastmcp_tools_are_registered_and_read_packaged_data():
    assert await mcp.get_tool("query_logs") is not None
    assert await mcp.get_tool("query_cpu_metrics") is not None
    assert await mcp.get_tool("query_memory_metrics") is not None

    cpu = query_cpu_metrics("checkout-api")
    logs = query_logs("checkout-api", keyword="timeout")

    assert cpu["payload"]["utilization"] == 0.93
    assert len(logs["payload"]["entries"]) == 1
