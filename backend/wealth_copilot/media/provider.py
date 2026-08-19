"""Gemini TTS provider that converts approved text to browser-playable WAV."""

import asyncio
from io import BytesIO
import wave

from google import genai
from google.genai import types

from ..config import get_settings


settings = get_settings()


def pcm_to_wav(pcm: bytes, *, rate: int = 24000) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm)
    return buffer.getvalue()


class GeminiTtsProvider:
    sample_rate = 24000

    async def synthesize(self, script: str) -> bytes:
        return await asyncio.to_thread(self._synthesize, script)

    def _synthesize(self, script: str) -> bytes:
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        response = client.models.generate_content(
            model=settings.tts_model,
            contents=(
                "Speak in a calm, warm, professional Indian English voice. Use a measured news-brief pace, "
                "clear pronunciation of company names and percentages, and short natural pauses. Read exactly "
                f"the following approved transcript without adding commentary: {script}"
            ),
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    language_code=settings.tts_language_code,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=settings.tts_voice
                        )
                    ),
                ),
            ),
        )
        try:
            pcm = response.candidates[0].content.parts[0].inline_data.data
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini TTS returned no audio data") from exc
        if not pcm:
            raise RuntimeError("Gemini TTS returned empty audio data")
        return pcm_to_wav(pcm, rate=self.sample_rate)


gemini_tts_provider = GeminiTtsProvider()

