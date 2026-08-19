"""Read-only Zerodha Kite MCP configuration."""

import logging

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)


logger = logging.getLogger(__name__)

# Intentionally excludes place/modify/cancel order and all GTT mutation tools.
ZERODHA_READ_ONLY_TOOLS = (
    "login",
    "get_profile",
    "get_holdings",
    "get_positions",
    "get_mf_holdings",
    "get_quotes",
    "get_ltp",
    "get_ohlc",
    "get_historical_data",
    "search_instruments",
)

ZERODHA_BLOCKED_TRADING_TOOLS = frozenset(
    {
        "place_order",
        "modify_order",
        "cancel_order",
        "place_gtt_order",
        "modify_gtt_order",
        "delete_gtt_order",
    }
)


def create_zerodha_toolset(url: str, timeout_seconds: float = 15.0) -> McpToolset:
    """Construct an ADK MCP toolset with an explicit read-only allowlist."""

    logger.info("Creating read-only Zerodha MCP toolset for %s", url)
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            timeout=timeout_seconds,
            sse_read_timeout=max(30.0, timeout_seconds),
        ),
        tool_filter=list(ZERODHA_READ_ONLY_TOOLS),
    )

