"""Warm, low-latency LLM presenter for TaskMaster-owned voice context."""

from collections.abc import AsyncIterator
import asyncio
import logging

from google import genai
from google.genai import types

from ..config import get_settings


logger = logging.getLogger(__name__)


def _client() -> genai.Client:
    settings = get_settings()
    if settings.vertex_ai_enabled:
        if not settings.google_cloud_project:
            raise RuntimeError("Voice LLM requires GOOGLE_CLOUD_PROJECT for Vertex AI")
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    api_key = settings.gemini_api_key or settings.google_api_key
    if not api_key:
        raise RuntimeError("Voice LLM requires Gemini or Vertex AI credentials")
    return genai.Client(api_key=api_key)


class VoicePresentationLLM:
    """Streams spoken phrasing only; all facts arrive in the TaskMaster context packet."""

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def warm(self) -> None:
        if self._client is None:
            self._client = _client()

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        settings = get_settings()
        self.warm()
        assert self._client is not None
        responses = await self._client.aio.models.generate_content_stream(
            model=settings.voice_llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.25,
                max_output_tokens=180,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        iterator = responses.__aiter__()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.voice_llm_timeout_seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError("Voice presentation LLM timed out")
            try:
                response = await asyncio.wait_for(anext(iterator), timeout=remaining)
            except StopAsyncIteration:
                break
            text = response.text or ""
            if text:
                yield text


voice_presentation_llm = VoicePresentationLLM()
