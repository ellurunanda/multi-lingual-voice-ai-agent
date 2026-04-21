"""
Text-to-Speech Service using OpenAI TTS API.
Converts agent text responses to audio for multilingual voice output.
Supports: English, Hindi, Tamil, Telugu.
Measures and logs TTS latency for performance monitoring.
"""
import time
import logging
import asyncio
import io
from typing import Optional, Tuple
import openai

from config import settings

logger = logging.getLogger(__name__)

# Voice configurations per language for natural-sounding output
# OpenAI TTS voices: alloy, echo, fable, onyx, nova, shimmer
LANGUAGE_VOICE_MAP = {
    "en": "alloy",    # Clear, neutral English
    "hi": "nova",     # Warm voice for Hindi
    "ta": "shimmer",  # Expressive for Tamil
    "te": "nova",     # Warm voice for Telugu
}

# TTS speed adjustments per language
LANGUAGE_SPEED_MAP = {
    "en": 1.0,
    "hi": 0.95,   # Slightly slower for Hindi clarity
    "ta": 0.95,   # Slightly slower for Tamil clarity
    "te": 0.95,   # Slightly slower for Telugu clarity
}


class TextToSpeechService:
    """
    Handles text-to-speech conversion using OpenAI TTS API.
    Optimized for low latency with streaming support.
    """

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_tts_model
        self.default_voice = settings.openai_tts_voice
        self.target_latency_ms = settings.target_tts_latency
        logger.info(f"TTS Service initialized with model: {self.model}")

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        output_format: str = "mp3"
    ) -> Tuple[bytes, int]:
        """
        Convert text to speech audio.

        Args:
            text: Text to convert to speech
            language: Language code (en/hi/ta/te)
            voice: Optional voice override
            output_format: Audio output format (mp3, opus, aac, flac)

        Returns:
            Tuple of (audio_bytes, latency_ms)
        """
        start_time = time.time()

        try:
            # Select appropriate voice for language
            selected_voice = voice or LANGUAGE_VOICE_MAP.get(language, self.default_voice)
            speed = LANGUAGE_SPEED_MAP.get(language, 1.0)

            # Prepare text (add language-specific preprocessing)
            processed_text = self._preprocess_text(text, language)

            # Call OpenAI TTS API
            response = await self.client.audio.speech.create(
                model=self.model,
                voice=selected_voice,
                input=processed_text,
                response_format=output_format,
                speed=speed,
            )

            # Read audio bytes
            audio_bytes = response.content

            latency_ms = int((time.time() - start_time) * 1000)

            # Log latency
            self._log_latency(latency_ms, language)

            logger.info(
                f"TTS completed: {len(text)} chars -> {len(audio_bytes)} bytes "
                f"lang={language} voice={selected_voice} latency={latency_ms}ms"
            )

            return audio_bytes, latency_ms

        except openai.APIError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"OpenAI TTS API error: {e}")
            raise TTSException(f"Speech synthesis failed: {str(e)}")

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"TTS error: {e}")
            raise TTSException(f"Speech synthesis error: {str(e)}")

    async def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        chunk_size: int = 4096
    ):
        """
        Stream TTS audio for lower perceived latency.
        Yields audio chunks as they become available.

        Args:
            text: Text to convert
            language: Language code
            voice: Optional voice override
            chunk_size: Size of each audio chunk in bytes

        Yields:
            Audio bytes chunks
        """
        start_time = time.time()
        first_chunk = True

        try:
            selected_voice = voice or LANGUAGE_VOICE_MAP.get(language, self.default_voice)
            speed = LANGUAGE_SPEED_MAP.get(language, 1.0)
            processed_text = self._preprocess_text(text, language)

            async with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=selected_voice,
                input=processed_text,
                response_format="mp3",
                speed=speed,
            ) as response:
                async for chunk in response.iter_bytes(chunk_size=chunk_size):
                    if first_chunk:
                        first_chunk_latency = int((time.time() - start_time) * 1000)
                        logger.info(f"TTS first chunk latency: {first_chunk_latency}ms")
                        first_chunk = False
                    yield chunk

            total_latency = int((time.time() - start_time) * 1000)
            self._log_latency(total_latency, language)

        except Exception as e:
            logger.error(f"TTS streaming error: {e}")
            raise TTSException(f"Speech synthesis streaming error: {str(e)}")

    def _preprocess_text(self, text: str, language: str) -> str:
        """
        Preprocess text for better TTS output.
        Handles language-specific formatting.
        """
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Limit text length (OpenAI TTS has 4096 char limit)
        if len(text) > 4000:
            text = text[:4000] + "..."
            logger.warning("Text truncated to 4000 chars for TTS")

        # Language-specific preprocessing
        if language == "hi":
            text = self._preprocess_hindi(text)
        elif language == "ta":
            text = self._preprocess_tamil(text)
        elif language == "te":
            text = self._preprocess_telugu(text)

        return text

    def _preprocess_hindi(self, text: str) -> str:
        """Hindi-specific text preprocessing."""
        # Add pauses after punctuation for natural speech
        text = text.replace("।", "। ")
        text = text.replace("॥", "॥ ")
        return text

    def _preprocess_tamil(self, text: str) -> str:
        """Tamil-specific text preprocessing."""
        return text

    def _preprocess_telugu(self, text: str) -> str:
        """Telugu-specific text preprocessing."""
        return text

    def _log_latency(self, latency_ms: int, language: str):
        """Log latency metrics."""
        if latency_ms > self.target_latency_ms:
            logger.warning(
                f"TTS latency {latency_ms}ms exceeded target {self.target_latency_ms}ms "
                f"for language={language}"
            )
        else:
            logger.debug(
                f"TTS latency {latency_ms}ms within target {self.target_latency_ms}ms"
            )

    async def get_available_voices(self) -> dict:
        """Return available voices per language."""
        return {
            "en": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            "hi": ["nova", "alloy", "shimmer"],
            "ta": ["shimmer", "nova", "alloy"],
            "te": ["nova", "shimmer", "alloy"],
        }

    async def synthesize_with_fallback(
        self,
        text: str,
        language: str = "en"
    ) -> Tuple[bytes, int]:
        """
        Synthesize with fallback to English if language-specific fails.
        """
        try:
            return await self.synthesize(text, language)
        except TTSException:
            logger.warning(f"TTS failed for {language}, falling back to English")
            try:
                return await self.synthesize(text, "en")
            except TTSException as e:
                logger.error(f"TTS fallback also failed: {e}")
                raise


class TTSException(Exception):
    """Custom exception for Text-to-Speech errors."""
    pass


# Singleton instance
_tts_service: Optional[TextToSpeechService] = None


def get_tts_service() -> TextToSpeechService:
    """Get or create the TTS service singleton."""
    global _tts_service
    if _tts_service is None:
        _tts_service = TextToSpeechService()
    return _tts_service