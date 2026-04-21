"""
Speech-to-Text Service using OpenAI Whisper API.
Supports multilingual transcription: English, Hindi, Tamil, Telugu.
Measures and logs STT latency for performance monitoring.
"""
import time
import logging
import asyncio
import tempfile
import os
from typing import Optional, Tuple
from pathlib import Path
import openai
from pydub import AudioSegment
import io

from config import settings

logger = logging.getLogger(__name__)

# Language code to Whisper language mapping
LANGUAGE_MAP = {
    "en": "english",
    "hi": "hindi",
    "ta": "tamil",
    "te": "telugu",
}

# Whisper supported language hints
WHISPER_LANGUAGE_HINTS = {
    "en": "en",
    "hi": "hi",
    "ta": "ta",
    "te": "te",
}


class SpeechToTextService:
    """
    Handles audio transcription using OpenAI Whisper.
    Supports streaming and batch transcription with latency tracking.
    """

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_whisper_model
        self.target_latency_ms = settings.target_stt_latency
        logger.info(f"STT Service initialized with model: {self.model}")

    async def transcribe(
        self,
        audio_data: bytes,
        language_hint: Optional[str] = None,
        audio_format: str = "webm"
    ) -> Tuple[str, str, int]:
        """
        Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio bytes
            language_hint: Optional language code hint (en/hi/ta/te)
            audio_format: Audio format (webm, wav, mp3, ogg)

        Returns:
            Tuple of (transcribed_text, detected_language, latency_ms)
        """
        start_time = time.time()

        try:
            # Convert audio to proper format if needed
            audio_bytes = await self._prepare_audio(audio_data, audio_format)

            # Prepare Whisper API call parameters
            whisper_params = {
                "model": self.model,
                "response_format": "verbose_json",
                "temperature": 0.0,
            }

            # Add language hint if provided
            if language_hint and language_hint in WHISPER_LANGUAGE_HINTS:
                whisper_params["language"] = WHISPER_LANGUAGE_HINTS[language_hint]

            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(
                suffix=f".{audio_format}",
                delete=False
            ) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_file_path = tmp_file.name

            try:
                # Call Whisper API
                with open(tmp_file_path, "rb") as audio_file:
                    response = await self.client.audio.transcriptions.create(
                        file=audio_file,
                        **whisper_params
                    )

                transcribed_text = response.text.strip()
                detected_language = getattr(response, "language", language_hint or "en")

                # Normalize language code
                detected_language = self._normalize_language_code(detected_language)

            finally:
                # Clean up temp file
                os.unlink(tmp_file_path)

            latency_ms = int((time.time() - start_time) * 1000)

            # Log latency performance
            self._log_latency(latency_ms, detected_language)

            logger.info(
                f"STT completed: '{transcribed_text[:50]}...' "
                f"lang={detected_language} latency={latency_ms}ms"
            )

            return transcribed_text, detected_language, latency_ms

        except openai.APIError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"OpenAI STT API error: {e}")
            raise STTException(f"Speech recognition failed: {str(e)}")

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"STT error: {e}")
            raise STTException(f"Speech recognition error: {str(e)}")

    async def transcribe_with_fallback(
        self,
        audio_data: bytes,
        language_hint: Optional[str] = None,
        audio_format: str = "webm"
    ) -> Tuple[str, str, int]:
        """
        Transcribe with automatic retry and fallback.
        First tries with language hint, then without if it fails.
        """
        try:
            return await self.transcribe(audio_data, language_hint, audio_format)
        except STTException:
            logger.warning("STT failed with language hint, retrying without hint")
            try:
                return await self.transcribe(audio_data, None, audio_format)
            except STTException as e:
                logger.error(f"STT fallback also failed: {e}")
                raise

    async def _prepare_audio(self, audio_data: bytes, audio_format: str) -> bytes:
        """
        Prepare audio data for Whisper API.
        Converts to supported format if necessary.
        """
        try:
            # If already in a supported format, return as-is
            if audio_format in ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]:
                return audio_data

            # Convert using pydub
            audio_segment = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=audio_format
            )

            # Export as mp3
            output_buffer = io.BytesIO()
            audio_segment.export(output_buffer, format="mp3")
            return output_buffer.getvalue()

        except Exception as e:
            logger.warning(f"Audio conversion failed, using raw data: {e}")
            return audio_data

    def _normalize_language_code(self, language: str) -> str:
        """Normalize Whisper language output to our language codes."""
        language_lower = language.lower()

        # Direct mapping
        if language_lower in ["en", "english"]:
            return "en"
        elif language_lower in ["hi", "hindi"]:
            return "hi"
        elif language_lower in ["ta", "tamil"]:
            return "ta"
        elif language_lower in ["te", "telugu"]:
            return "te"

        # Default to English if unknown
        logger.warning(f"Unknown language code: {language}, defaulting to 'en'")
        return "en"

    def _log_latency(self, latency_ms: int, language: str):
        """Log latency metrics and warn if target exceeded."""
        if latency_ms > self.target_latency_ms:
            logger.warning(
                f"STT latency {latency_ms}ms exceeded target {self.target_latency_ms}ms "
                f"for language={language}"
            )
        else:
            logger.debug(
                f"STT latency {latency_ms}ms within target {self.target_latency_ms}ms"
            )

    async def get_audio_duration(self, audio_data: bytes, audio_format: str = "webm") -> float:
        """Get duration of audio in milliseconds."""
        try:
            audio_segment = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=audio_format
            )
            return len(audio_segment)  # pydub returns duration in ms
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0


class STTException(Exception):
    """Custom exception for Speech-to-Text errors."""
    pass


# Singleton instance
_stt_service: Optional[SpeechToTextService] = None


def get_stt_service() -> SpeechToTextService:
    """Get or create the STT service singleton."""
    global _stt_service
    if _stt_service is None:
        _stt_service = SpeechToTextService()
    return _stt_service