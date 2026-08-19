"""Source-first Research Agent used only for explicit deeper investigation."""

from datetime import date
from typing import Any

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.genai import types

from ..config import get_settings


settings = get_settings()


async def get_demo_research_packet(topic: str) -> dict[str, Any]:
    """Return a deterministic, sourced packet when live Search is disabled."""

    normalized = topic.lower()
    if "hdfc" in normalized:
        return {
            "status": "ok",
            "facts": [
                "The retained event recorded a 5.4% HDFC Bank decline versus a 0.8% decline for its sector.",
                "The event investigation retained a regulatory-review development and unusually large block-trade activity.",
            ],
            "context": [
                "The much larger company move is why the event was treated as company-specific attention rather than broad banking noise.",
                "The retained evidence does not prove one definitive cause, so the causal explanation remains uncertain.",
            ],
            "sources": [
                {"name": "Demo Market Feed", "url": "https://events.example/hdfc-bank-sudden-fall", "authority": "event_feed"},
                {"name": "Demo Regulator Investigation", "url": "https://investigation.example/hdfc-regulatory-review", "authority": "supporting"},
            ],
        }
    return {
        "status": "ok",
        "facts": ["The retained daily brief is the current evidence base for this demo investigation."],
        "context": ["More specific conclusions require an official disclosure or corroborating report."],
        "sources": [],
    }


def create_research_agent() -> Agent:
    live = settings.news_provider == "google_search"
    tool = google_search if live else get_demo_research_packet
    method = (
        "Use Google Search to investigate the exact subject."
        if live
        else "Call get_demo_research_packet once with the exact subject."
    )
    return Agent(
        name="research_agent",
        model=settings.adk_model,
        description="Performs an explicit, deeper, source-first investigation for Learn More.",
        instruction=(
            f"You are Wealth Copilot's Research Agent. Today is {date.today().isoformat()}. {method} "
            "Prioritize sources in this order: company or exchange disclosures; RBI, SEBI, or another "
            "official authority; established financial reporting; secondary analysis. Separate the answer "
            "into Facts, Context / interpretation, What remains uncertain, and Sources. Every source must "
            "include its exact article or filing URL. Clearly label inference and disagreement. Do not invent "
            "facts or URLs. Explain relevance and context only; never give an investment recommendation, "
            "predict a security's future price, or instruct the user to transact."
        ),
        tools=[tool],
        generate_content_config=types.GenerateContentConfig(temperature=0),
    )


research_agent = create_research_agent()

