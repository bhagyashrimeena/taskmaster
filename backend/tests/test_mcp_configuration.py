import pytest

from wealth_copilot.mcp.zerodha import (
    ZERODHA_BLOCKED_TRADING_TOOLS,
    ZERODHA_READ_ONLY_TOOLS,
    create_zerodha_toolset,
)


@pytest.mark.asyncio
async def test_zerodha_toolset_constructs_without_secrets() -> None:
    toolset = create_zerodha_toolset("https://mcp.kite.trade/mcp")
    try:
        assert not set(ZERODHA_READ_ONLY_TOOLS).intersection(ZERODHA_BLOCKED_TRADING_TOOLS)
        assert set(toolset.tool_filter) == set(ZERODHA_READ_ONLY_TOOLS)
    finally:
        await toolset.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_zerodha_tool_discovery() -> None:
    toolset = create_zerodha_toolset("https://mcp.kite.trade/mcp")
    try:
        names = {tool.name for tool in await toolset.get_tools()}
        assert names.issubset(set(ZERODHA_READ_ONLY_TOOLS))
        assert "login" in names
        assert not names.intersection(ZERODHA_BLOCKED_TRADING_TOOLS)
    finally:
        await toolset.close()
