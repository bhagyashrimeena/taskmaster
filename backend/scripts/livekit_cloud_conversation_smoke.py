"""Exercise a real LiveKit Cloud room with two text turns and voice output.

The script obtains a short-lived participant token from the product API. It never
reads or prints the LiveKit API secret.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from urllib import request

from livekit import rtc


def create_session(api_base_url: str) -> dict[str, object]:
    payload = json.dumps({"conversation_id": None, "current_case_id": None}).encode()
    token_request = request.Request(
        f"{api_base_url.rstrip('/')}/api/v1/copilot/voice/session",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(token_request, timeout=10) as response:  # noqa: S310
        return json.load(response)


async def wait_for_agent(room: rtc.Room, timeout: float = 20) -> str:
    async def connected_agent() -> str:
        while True:
            for participant in room.remote_participants.values():
                if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
                    return participant.identity
            await asyncio.sleep(0.1)

    return await asyncio.wait_for(connected_agent(), timeout=timeout)


async def main(api_base_url: str) -> None:
    session = await asyncio.to_thread(create_session, api_base_url)
    if not session.get("enabled"):
        raise RuntimeError(str(session.get("reason") or "LiveKit is not configured"))

    room = rtc.Room()
    responses: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    local_identity = str(session["participant_name"])

    async def collect_transcript(reader: rtc.TextStreamReader, identity: str) -> None:
        text = await reader.read_all()
        attributes = reader.info.attributes
        if (
            identity != local_identity
            and attributes.get("lk.transcription_final") == "true"
            and text.strip()
        ):
            await responses.put((identity, text.strip()))

    def on_transcript(reader: rtc.TextStreamReader, identity: str) -> None:
        asyncio.create_task(collect_transcript(reader, identity))

    room.register_text_stream_handler("lk.transcription", on_transcript)
    await room.connect(str(session["livekit_url"]), str(session["token"]))

    try:
        agent_identity = await wait_for_agent(room)
        turns: list[dict[str, object]] = []
        for question in (
            "What deserves my attention right now?",
            "Why does that matter to my portfolio?",
        ):
            await room.local_participant.send_text(question, topic="lk.chat")
            identity, answer = await asyncio.wait_for(responses.get(), timeout=90)
            if identity != agent_identity:
                raise RuntimeError("Received a response from an unexpected participant")
            turns.append(
                {
                    "question": question,
                    "answer_characters": len(answer),
                    "agent_response_received": True,
                }
            )

        print(
            json.dumps(
                {
                    "status": "passed",
                    "room_connected": True,
                    "agent_dispatched": True,
                    "conversation_id_present": bool(session.get("conversation_id")),
                    "turns": turns,
                },
                indent=2,
            )
        )
    finally:
        await room.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8011")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.api))
