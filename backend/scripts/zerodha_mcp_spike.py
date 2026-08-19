"""Manual ADK/Zerodha MCP diagnostic. Writes no credentials or session tokens."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import re
from typing import Any

from wealth_copilot.config import get_settings
from wealth_copilot.mcp.zerodha import (
    ZERODHA_BLOCKED_TRADING_TOOLS,
    ZERODHA_READ_ONLY_TOOLS,
)
from wealth_copilot.portfolio.provider import PortfolioAuthenticationRequired
from wealth_copilot.portfolio.zerodha_provider import ZerodhaPortfolioProvider


logger = logging.getLogger("zerodha_mcp_spike")
_LOGIN_URL = re.compile(r"https://mcp\.kite\.trade/authorize\?[^\s)]+")


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


async def _attempt(label: str, operation: Any) -> dict[str, Any]:
    try:
        value = await operation()
        logger.info("%s: PASS", label)
        return {"status": "PASS", "detail": value}
    except PortfolioAuthenticationRequired as exc:
        logger.warning("%s: FAIL (authentication required)", label)
        return {"status": "FAIL", "detail": _safe_error(exc)}
    except Exception as exc:  # diagnostic must continue through every check
        logger.warning("%s: FAIL (%s)", label, type(exc).__name__)
        return {"status": "FAIL", "detail": _safe_error(exc)}


async def run(wait_for_login: bool) -> dict[str, Any]:
    settings = get_settings()
    provider = ZerodhaPortfolioProvider(
        settings.zerodha_mcp_url, settings.zerodha_mcp_timeout_seconds
    )
    report: dict[str, Any] = {}
    try:
        discovery = await _attempt("Tool discovery", provider.discover_tools)
        report["connection"] = {
            "status": discovery["status"],
            "detail": "ADK reached the MCP endpoint" if discovery["status"] == "PASS" else discovery["detail"],
        }
        report["tool_discovery"] = discovery
        names = set(discovery.get("detail", [])) if discovery["status"] == "PASS" else set()
        report["login_available"] = {"status": "PASS" if "login" in names else "FAIL"}
        report["read_only_filtering"] = {
            "status": "PASS" if names.issubset(set(ZERODHA_READ_ONLY_TOOLS)) and not names.intersection(ZERODHA_BLOCKED_TRADING_TOOLS) else "FAIL",
            "exposed_tools": sorted(names),
        }

        login = await _attempt("Login", provider.login)
        if login["status"] == "PASS" and isinstance(login.get("detail"), str):
            match = _LOGIN_URL.search(login["detail"])
            # Do not persist the signed session URL.
            login["detail"] = "Browser authorization URL returned" if match else "Login response returned"
            if match:
                print("\nZerodha requires a user action. Open this URL now:\n")
                print(match.group(0))
                print("\nDo not share or commit this temporary URL.\n")
                if wait_for_login:
                    input("After authorizing in the browser, press Enter to continue... ")
        report["login"] = login
        report["get_profile"] = await _attempt("get_profile", provider.get_profile)
        report["get_holdings"] = await _attempt("get_holdings", provider.get_holdings)
        report["second_tool_call_same_session"] = await _attempt(
            "Second get_profile in same session", provider.get_profile
        )
        return report
    finally:
        await provider.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wait-for-login",
        action="store_true",
        help="Pause after printing the browser URL so authenticated calls can be tested.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional sanitized JSON output path (signed login URLs are never written).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = asyncio.run(run(args.wait_for_login))
    serialized = json.dumps(report, indent=2, default=str)
    print(serialized)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

