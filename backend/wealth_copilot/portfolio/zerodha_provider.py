"""Normalized portfolio provider backed by Zerodha's hosted MCP server."""

import asyncio
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import logging
import uuid
from typing import Any

from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ..mcp.zerodha import ZERODHA_READ_ONLY_TOOLS, create_zerodha_toolset
from .provider import (
    PortfolioAuthenticationRequired,
    PortfolioProvider,
    PortfolioProviderError,
    PortfolioToolUnavailable,
)
from .schemas import HistoricalCandle, Holding, Position, Profile, Quote


logger = logging.getLogger(__name__)


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError, ArithmeticError) as exc:
        raise PortfolioProviderError(f"Invalid numeric portfolio value: {value!r}") from exc
    if not parsed.is_finite():
        raise PortfolioProviderError(f"Non-finite numeric portfolio value: {value!r}")
    return parsed


class ZerodhaPortfolioProvider(PortfolioProvider):
    """Uses one ADK MCP toolset so login/session state can be reused."""

    source = "zerodha"
    is_live = True

    def __init__(self, url: str, timeout_seconds: float = 15.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.allowed_tools = ZERODHA_READ_ONLY_TOOLS
        self.toolset = create_zerodha_toolset(url, timeout_seconds)
        self._tools: dict[str, BaseTool] | None = None
        self._tool_context: ToolContext | None = None
        self._context_lock = asyncio.Lock()

    async def _context(self) -> ToolContext:
        if self._tool_context is None:
            async with self._context_lock:
                if self._tool_context is None:
                    service = InMemorySessionService()
                    session = await service.create_session(
                        app_name="wealth_copilot_zerodha",
                        user_id="local_user",
                        session_id=str(uuid.uuid4()),
                    )
                    invocation = InvocationContext(
                        session_service=service,
                        invocation_id=str(uuid.uuid4()),
                        session=session,
                    )
                    self._tool_context = ToolContext(invocation_context=invocation)
        return self._tool_context

    async def discover_tools(self) -> list[str]:
        logger.info("Attempting Zerodha MCP tool discovery")
        discovered = await self.toolset.get_tools()
        self._tools = {tool.name: tool for tool in discovered}
        for name in sorted(self._tools):
            logger.info("Zerodha MCP tool discovered: %s", name)
        return sorted(self._tools)

    async def _call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if name not in self.allowed_tools:
            raise PortfolioToolUnavailable(f"MCP tool {name!r} is not on the read-only allowlist.")
        if self._tools is None:
            await self.discover_tools()
        tool = (self._tools or {}).get(name)
        if tool is None:
            raise PortfolioToolUnavailable(f"Zerodha MCP did not advertise {name!r}.")
        logger.info("Calling Zerodha MCP portfolio tool: %s", name)
        try:
            result = await tool.run_async(
                args=arguments or {}, tool_context=await self._context()
            )
        except (TimeoutError, ConnectionError) as exc:
            logger.warning("Zerodha MCP %s failed: %s", name, type(exc).__name__)
            raise PortfolioProviderError(
                f"Zerodha MCP is unavailable while calling {name}; switch PORTFOLIO_PROVIDER=demo to continue."
            ) from exc
        return self._unwrap_result(name, result)

    @staticmethod
    def _unwrap_result(name: str, result: Any) -> Any:
        if not isinstance(result, dict):
            return result
        contents = result.get("content", [])
        texts = [item.get("text", "") for item in contents if isinstance(item, dict)]
        text = "\n".join(value for value in texts if value)
        if result.get("isError"):
            if "login" in text.lower() or text == f"Failed to execute {name}":
                raise PortfolioAuthenticationRequired(
                    "Zerodha authentication is required or expired. Call login, complete the returned browser flow, then retry in the same process/session."
                )
            raise PortfolioProviderError(text or f"Zerodha MCP tool {name} failed.")
        if not text:
            return result
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    async def login(self) -> str:
        result = await self._call("login")
        return result if isinstance(result, str) else json.dumps(result, default=str)

    async def get_profile(self) -> Profile:
        data = await self._call("get_profile")
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            data = data["data"]
        if not isinstance(data, dict):
            raise PortfolioProviderError("Zerodha get_profile returned an unexpected payload.")
        return Profile(
            source="zerodha",
            provider="zerodha",
            user_id=str(data.get("user_id", "unknown")),
            user_name=str(data.get("user_name") or data.get("user_shortname") or "Zerodha user"),
            email=data.get("email"),
            broker=data.get("broker", "Zerodha"),
        )

    async def get_holdings(self) -> list[Holding]:
        data = await self._call("get_holdings")
        rows = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = rows.get("holdings", [])
        if not isinstance(rows, list):
            raise PortfolioProviderError("Zerodha get_holdings returned an unexpected payload.")
        values: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            quantity = _decimal(row.get("quantity"))
            current = _decimal(row.get("last_price") or row.get("current_price"))
            average = _decimal(row.get("average_price"))
            previous = _decimal(row.get("close_price"), "0") or None
            values.append(
                {
                    "symbol": str(row.get("tradingsymbol") or row.get("symbol") or "UNKNOWN"),
                    "exchange": str(row.get("exchange", "NSE")),
                    "quantity": quantity,
                    "average_price": average,
                    "current_price": current,
                    "previous_close": previous,
                    "market_value": quantity * current,
                    "invested_value": quantity * average,
                    "sector": row.get("sector"),
                }
            )
        total = sum((row["market_value"] for row in values), Decimal("0"))
        return [
            Holding(
                **row,
                unrealized_pnl=row["market_value"] - row["invested_value"],
                day_pnl=(row["quantity"] * (row["current_price"] - row["previous_close"]))
                if row["previous_close"] is not None
                else None,
                portfolio_weight=(row["market_value"] / total * 100).quantize(Decimal("0.01"))
                if total
                else Decimal("0"),
            )
            for row in values
        ]

    async def get_positions(self) -> list[Position]:
        data = await self._call("get_positions")
        rows = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = rows.get("net", rows.get("day", []))
        if not isinstance(rows, list):
            raise PortfolioProviderError("Zerodha get_positions returned an unexpected payload.")
        return [
            Position(
                symbol=str(row.get("tradingsymbol") or row.get("symbol") or "UNKNOWN"),
                exchange=str(row.get("exchange", "NSE")),
                product=row.get("product"),
                quantity=_decimal(row.get("quantity")),
                average_price=_decimal(row.get("average_price")),
                current_price=_decimal(row.get("last_price")),
                pnl=_decimal(row.get("pnl")),
            )
            for row in rows
            if isinstance(row, dict)
        ]

    async def get_quotes(self, instruments: list[str]) -> dict[str, Quote]:
        data = await self._call("get_quotes", {"instruments": instruments})
        rows = data.get("data", data) if isinstance(data, dict) else {}
        if not isinstance(rows, dict):
            raise PortfolioProviderError("Zerodha get_quotes returned an unexpected payload.")
        result: dict[str, Quote] = {}
        for instrument, row in rows.items():
            if not isinstance(row, dict):
                continue
            ohlc = row.get("ohlc") if isinstance(row.get("ohlc"), dict) else {}
            result[instrument] = Quote(
                instrument=instrument,
                last_price=_decimal(row.get("last_price")),
                ohlc_open=_decimal(ohlc.get("open")) if ohlc.get("open") is not None else None,
                ohlc_high=_decimal(ohlc.get("high")) if ohlc.get("high") is not None else None,
                ohlc_low=_decimal(ohlc.get("low")) if ohlc.get("low") is not None else None,
                ohlc_close=_decimal(ohlc.get("close")) if ohlc.get("close") is not None else None,
                timestamp=row.get("timestamp") or row.get("last_trade_time"),
            )
        return result

    async def get_ltp(self, instruments: list[str]) -> dict[str, Decimal]:
        data = await self._call("get_ltp", {"instruments": instruments})
        rows = data.get("data", data) if isinstance(data, dict) else {}
        return {
            instrument: _decimal(row.get("last_price") if isinstance(row, dict) else row)
            for instrument, row in rows.items()
        } if isinstance(rows, dict) else {}

    async def get_ohlc(self, instruments: list[str]) -> dict[str, Quote]:
        data = await self._call("get_ohlc", {"instruments": instruments})
        rows = data.get("data", data) if isinstance(data, dict) else {}
        if not isinstance(rows, dict):
            return {}
        result: dict[str, Quote] = {}
        for instrument, row in rows.items():
            if not isinstance(row, dict):
                continue
            ohlc = row.get("ohlc") if isinstance(row.get("ohlc"), dict) else row
            result[instrument] = Quote(
                instrument=instrument,
                last_price=_decimal(row.get("last_price") or ohlc.get("close")),
                ohlc_open=_decimal(ohlc.get("open")),
                ohlc_high=_decimal(ohlc.get("high")),
                ohlc_low=_decimal(ohlc.get("low")),
                ohlc_close=_decimal(ohlc.get("close")),
            )
        return result

    async def get_historical_data(
        self, symbol: str, from_date: date, to_date: date, interval: str = "day"
    ) -> list[HistoricalCandle]:
        search = await self._call(
            "search_instruments",
            {"query": symbol, "filter_on": "tradingsymbol", "limit": 10},
        )
        rows = search.get("data", search) if isinstance(search, dict) else search
        if isinstance(rows, dict):
            rows = rows.get("instruments", rows.get("results", []))
        if not isinstance(rows, list) or not rows:
            raise PortfolioProviderError(f"No Zerodha instrument found for {symbol!r}.")
        match = next(
            (row for row in rows if str(row.get("tradingsymbol", "")).upper() == symbol.upper()),
            rows[0],
        )
        token = match.get("instrument_token") or match.get("token")
        data = await self._call(
            "get_historical_data",
            {
                "instrument_token": token,
                "from_date": f"{from_date.isoformat()} 00:00:00",
                "to_date": f"{to_date.isoformat()} 23:59:59",
                "interval": interval,
                "continuous": False,
                "oi": False,
            },
        )
        rows = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = rows.get("candles", [])
        candles: list[HistoricalCandle] = []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, list) and len(row) >= 6:
                candles.append(
                    HistoricalCandle(
                        timestamp=datetime.fromisoformat(str(row[0]).replace("Z", "+00:00")),
                        open=_decimal(row[1]), high=_decimal(row[2]), low=_decimal(row[3]),
                        close=_decimal(row[4]), volume=int(row[5]),
                        open_interest=int(row[6]) if len(row) > 6 else None,
                    )
                )
        return candles

    async def close(self) -> None:
        await self.toolset.close()
