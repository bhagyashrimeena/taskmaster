"""Gemini TTS provider that converts approved text to browser-playable WAV."""

from contextlib import suppress
from io import BytesIO
import wave

from google import genai
from google.genai import types

from ..config import get_settings


def pcm_to_wav(pcm: bytes, *, rate: int = 24000) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm)
    return buffer.getvalue()


class GeminiTtsConfigurationError(RuntimeError):
    """Raised when neither Gemini Developer API nor Vertex credentials exist."""


def _create_client(config):
    """Create exactly one Gemini client using the configured authentication mode."""

    vertex_enabled = bool(
        getattr(config, "vertex_ai_enabled", False)
        or getattr(config, "google_genai_use_vertexai", False)
        or getattr(config, "google_genai_use_enterprise", False)
    )
    if vertex_enabled:
        if not config.google_cloud_project:
            raise GeminiTtsConfigurationError(
                "Gemini TTS requires GOOGLE_CLOUD_PROJECT and Application Default Credentials "
                "when Vertex AI is enabled"
            )
        return genai.Client(
            vertexai=True,
            project=config.google_cloud_project,
            location=config.google_cloud_location,
        )

    api_key = getattr(config, "gemini_api_key", None) or config.google_api_key
    if api_key:
        return genai.Client(api_key=api_key)
    raise GeminiTtsConfigurationError(
        "Gemini TTS requires GEMINI_API_KEY (or GOOGLE_API_KEY), or Vertex AI with "
        "GOOGLE_GENAI_USE_VERTEXAI=true and GOOGLE_CLOUD_PROJECT"
    )


class GeminiTtsProvider:
    sample_rate = 24000

    async def synthesize(self, script: str) -> bytes:
        settings = get_settings()
        client = _create_client(settings)
        try:
            response = await client.aio.models.generate_content(
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
            pcm = response.candidates[0].content.parts[0].inline_data.data
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini TTS returned no audio data") from exc
        finally:
            with suppress(AttributeError):
                await client.aio.aclose()
            with suppress(AttributeError):
                client.close()
        if not pcm:
            raise RuntimeError("Gemini TTS returned empty audio data")
        return pcm_to_wav(pcm, rate=self.sample_rate)


gemini_tts_provider = GeminiTtsProvider()
