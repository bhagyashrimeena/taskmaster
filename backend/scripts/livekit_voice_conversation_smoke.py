"""Run two real TaskMaster turns through the LiveKit agent's transcript adapter."""

import asyncio
import json

from wealth_copilot.voice.agent import TaskMasterVoiceAgent


async def main() -> None:
    agent = TaskMasterVoiceAgent(conversation_id=None)
    turns = []
    for question in (
        "What deserves my attention right now?",
        "Why does the latest alert matter to my portfolio?",
    ):
        response = await agent.respond_to_transcript(question)
        turns.append(
            {
                "question": question,
                "answer": response.answer,
                "conversation_id": response.conversation_id,
                "mode": response.mode.value,
                "route": response.route,
                "fallback_used": response.fallback_used,
            }
        )
    print(json.dumps({"status": "passed", "turns": turns}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
