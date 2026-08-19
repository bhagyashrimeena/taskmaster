"""Market Intelligence Agent: Search-only or deterministic fixture-only."""

from datetime import date, datetime, timezone
import logging
from typing import Any

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.genai import types

from ..config import get_settings
from ..market.demo_provider import SimulatedNewsProvider


logger = logging.getLogger(__name__)
settings = get_settings()
MARKET_RESULT_KEY = "daily_brief_market_result"


async def get_demo_news_candidates() -> dict[str, Any]:
    """Return sourced candidates from the active deterministic scenario."""

    logger.info("Market tool called: get_demo_news_candidates")
    batch = await SimulatedNewsProvider().get_candidates(limit=settings.news_candidate_count)
    return {"status": "ok", **batch.model_dump(mode="json")}


def create_market_agent(*, output_key: str | None = None) -> Agent:
    live = settings.news_provider == "google_search"
    tools = [google_search] if live else [get_demo_news_candidates]
    source_instruction = (
        "Use Google Search grounding for fresh public-web reporting. Search multiple queries and sources. "
        "For every candidate, copy the exact article URL surfaced by Search. A publisher homepage or "
        "section page is invalid; search for the headline and omit the candidate unless you can recover "
        "an article-specific URL with a non-root path."
        if live
        else "Call get_demo_news_candidates once and return its candidates unchanged."
    )
    return Agent(
        name="market_intelligence_agent",
        model=settings.adk_model,
        description=(
            "Collects 10–20 fresh, sourced market-news candidates relevant to supplied holdings "
            "and sectors. It does not rank or personalize them."
        ),
        instruction=(
            f"You are Wealth Copilot's Market Intelligence Agent. Today is {date.today().isoformat()}. "
            f"{source_instruction} Collect a portfolio-independent pool of "
            f"{settings.news_candidate_count} Indian financial stories, not five. Cover major listed companies, "
            "banking, information technology, energy, telecom, consumer, healthcare, regulators, macro events, "
            "and broad markets so downstream portfolio code can match and filter. Avoid overloading the pool with "
            "one company or one event. Ensure the pool spans major liquid index names across these sectors; when "
            "fresh sourced developments exist, include HDFC Bank, Reliance Industries, Infosys, TCS, ICICI Bank, "
            "Bharti Airtel, Wipro, ITC, and Sun Pharma among the wider market universe. Prefer sources in this "
            "order: exchange/regulator/company filings, established financial reporting, then secondary analysis. "
            "Prefer stories published in "
            "the last 72 hours, reputable primary/company/regulator sources or established financial news, "
            "and one canonical, article-specific source URL per story. Do not score relevance and do not make "
            "investment advice. "
            "Return JSON only as an object with source, is_live, generated_at, and candidates. Every candidate "
            "must have: id, headline, summary, source_name, source_url, published_at (ISO 8601 with timezone), "
            "companies (use NSE ticker symbols when known), sectors, event_type (earnings, corporate_action, "
            "regulatory, management, product, macro, sector, market_move, or other), and market_move_pct "
            "(number or null). Never invent a URL or publication time; omit a story if these cannot be sourced. "
            "Only put a ticker in companies when that company is explicitly named as a primary subject of the "
            "story; for broad market, macro, commodity, or sector stories leave companies empty and tag sectors. "
            "Do not infer company tags merely because a holding could be affected. In live mode, set source to "
            "google_search_grounding and is_live to true. Before returning JSON, verify every source_url has an "
            "article path and is not just a domain homepage. Do not pad the batch with stale stories: every live "
            "candidate must be no more than 72 hours old; if necessary return 10 rather than 15."
        ),
        tools=tools,
        output_key=output_key,
        generate_content_config=types.GenerateContentConfig(temperature=0),
    )


market_agent = create_market_agent(output_key=MARKET_RESULT_KEY)
