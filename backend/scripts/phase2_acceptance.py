"""Run the HDFC hero event through the real TaskMaster ADK route."""

import asyncio
import json
from pathlib import Path
import time

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from wealth_copilot.agent import root_agent  # noqa: E402
from wealth_copilot.events import daily_event_store  # noqa: E402


async def main() -> None:
    daily_event_store.clear()
    runner = InMemoryRunner(agent=root_agent, app_name="phase2_acceptance")
    await runner.session_service.create_session(
        app_name="phase2_acceptance",
        user_id="acceptance-user",
        session_id="acceptance-session",
    )
    calls: list[str] = []
    tool_result: dict = {}
    final_text = ""
    started = time.perf_counter()
    try:
        async for event in runner.run_async(
            user_id="acceptance-user",
            session_id="acceptance-session",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="Run the HDFC Bank hero Event Watcher scenario.")],
            ),
        ):
            if not event.content:
                continue
            for part in event.content.parts or []:
                if part.function_call:
                    calls.append(part.function_call.name)
                if part.function_response and part.function_response.name == "run_event_watcher":
                    tool_result = part.function_response.response or {}
                if part.text:
                    final_text = part.text
    finally:
        await runner.close()

    data = tool_result.get("data", {})
    report = {
        "status": "PASS",
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "tool_calls": calls,
        "decision": data.get("decision"),
        "notification_required": data.get("notification_required"),
        "relevance_score": data.get("relevance_score"),
        "affected_portfolio_percentage": data.get("affected_portfolio_percentage"),
        "trace_stages": [step.get("stage") for step in data.get("trace", [])],
        "response_length": len(final_text),
    }
    assert "run_event_watcher" in calls, report
    assert report["decision"] == "ALERT", report
    assert report["notification_required"] is True, report
    assert report["affected_portfolio_percentage"] == 18.01, report
    assert len(report["trace_stages"]) == 5, report
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())

