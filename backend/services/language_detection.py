"""
Language Detection Service.
Detects language from text using multiple strategies:
1. LLM-based detection (most accurate for short texts)
2. langdetect library (fast fallback)
3. Script-based detection (Unicode range analysis for Indian scripts)

Supports: English (en), Hindi (hi), Tamil (ta), Telugu (te)
"""
import logging
import re
from typing import Optional, Tuple
import asyncio

from config import settings

logger = logging.getLogger(__name__)

# Unicode ranges for Indian scripts
DEVANAGARI_RANGE = (0x0900, 0x097F)   # Hindi
TAMIL_RANGE = (0x0B80, 0x0BFF)         # Tamil
TELUGU_RANGE = (0x0C00, 0x0C7F)        # Telugu

SUPPORTED_LANGUAGES = ["en", "hi", "ta", "te"]

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
}

# Common words/phrases for each language (for rule-based detection)
LANGUAGE_KEYWORDS = {
    "hi": [
        "मुझे", "आप", "कल", "डॉक्टर", "अपॉइंटमेंट", "बुक", "रद्द", "समय",
        "नमस्ते", "धन्यवाद", "हाँ", "नहीं", "ठीक", "मैं", "है", "हूँ"
    ],
    "ta": [
        "நான்", "நாளை", "மருத்துவர்", "சந்திப்பு", "வேண்டும்", "நன்றி",
        "ஆம்", "இல்லை", "சரி", "பார்க்க", "வருகிறேன்", "என்னால்"
    ],
    "te": [
        "నాకు", "రేపు", "డాక్టర్", "అపాయింట్మెంట్", "కావాలి", "ధన్యవాదాలు",
        "అవును", "కాదు", "సరే", "చూడాలి", "వస్తాను", "నేను", "మీరు"
    ],
}


class LanguageDetectionService:
    """
    Multi-strategy language detection service.
    Prioritizes accuracy for Indian languages.
    """

    def __init__(self):
        self._langdetect_available = self._check_langdetect()
        logger.info(
            f"Language Detection Service initialized. "
            f"langdetect available: {self._langdetect_available}"
        )

    def _check_langdetect(self) -> bool:
        """Check if langdetect library is available."""
        try:
            import langdetect
            return True
        except ImportError:
            logger.warning("langdetect not available, using fallback detection")
            return False

    async def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect language of input text.

        Args:
            text: Input text to detect language for

        Returns:
            Tuple of (language_code, confidence_score)
        """
        if not text or not text.strip():
            return settings.default_language, 0.0

        text = text.strip()

        # Strategy 1: Script-based detection (fastest, most reliable for Indian scripts)
        script_lang, script_confidence = self._detect_by_script(text)
        if script_confidence > 0.8:
            logger.debug(f"Script detection: {script_lang} ({script_confidence:.2f})")
            return script_lang, script_confidence

        # Strategy 2: Keyword-based detection
        keyword_lang, keyword_confidence = self._detect_by_keywords(text)
        if keyword_confidence > 0.7:
            logger.debug(f"Keyword detection: {keyword_lang} ({keyword_confidence:.2f})")
            return keyword_lang, keyword_confidence

        # Strategy 3: langdetect library
        if self._langdetect_available:
            lib_lang, lib_confidence = await self._detect_by_library(text)
            if lib_confidence > 0.5:
                logger.debug(f"Library detection: {lib_lang} ({lib_confidence:.2f})")
                return lib_lang, lib_confidence

        # Default to English if all strategies fail
        logger.debug(f"Defaulting to English for text: '{text[:30]}...'")
        return "en", 0.3

    def _detect_by_script(self, text: str) -> Tuple[str, float]:
        """
        Detect language by Unicode script analysis.
        Very reliable for distinguishing Indian scripts.
        """
        char_counts = {"hi": 0, "ta": 0, "te": 0, "latin": 0, "other": 0}
        total_chars = 0

        for char in text:
            code_point = ord(char)
            if char.isspace() or char in ".,!?;:\"'()[]{}":
                continue

            total_chars += 1

            if DEVANAGARI_RANGE[0] <= code_point <= DEVANAGARI_RANGE[1]:
                char_counts["hi"] += 1
            elif TAMIL_RANGE[0] <= code_point <= TAMIL_RANGE[1]:
                char_counts["ta"] += 1
            elif TELUGU_RANGE[0] <= code_point <= TELUGU_RANGE[1]:
                char_counts["te"] += 1
            elif char.isascii():
                char_counts["latin"] += 1
            else:
                char_counts["other"] += 1

        if total_chars == 0:
            return "en", 0.0

        # Find dominant script
        max_lang = max(char_counts, key=char_counts.get)
        max_count = char_counts[max_lang]
        confidence = max_count / total_chars

        if max_lang == "latin" and confidence > 0.7:
            return "en", confidence
        elif max_lang in ["hi", "ta", "te"] and confidence > 0.3:
            return max_lang, min(confidence + 0.3, 1.0)  # Boost confidence for clear scripts

        return "en", 0.0

    def _detect_by_keywords(self, text: str) -> Tuple[str, float]:
        """
        Detect language by matching known keywords.
        """
        text_lower = text.lower()
        scores = {}

        for lang, keywords in LANGUAGE_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > 0:
                scores[lang] = matches / len(keywords)

        if not scores:
            return "en", 0.0

        best_lang = max(scores, key=scores.get)
        confidence = min(scores[best_lang] * 5, 1.0)  # Scale up

        return best_lang, confidence

    async def _detect_by_library(self, text: str) -> Tuple[str, float]:
        """
        Use langdetect library for detection.
        Runs in thread pool to avoid blocking.
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._langdetect_sync, text)
            return result
        except Exception as e:
            logger.warning(f"langdetect error: {e}")
            return "en", 0.0

    def _langdetect_sync(self, text: str) -> Tuple[str, float]:
        """Synchronous langdetect call."""
        try:
            from langdetect import detect_langs
            results = detect_langs(text)

            for result in results:
                lang_code = result.lang
                confidence = result.prob

                # Map to our supported languages
                if lang_code == "en":
                    return "en", confidence
                elif lang_code == "hi":
                    return "hi", confidence
                elif lang_code == "ta":
                    return "ta", confidence
                elif lang_code == "te":
                    return "te", confidence

            return "en", 0.3

        except Exception as e:
            logger.warning(f"langdetect sync error: {e}")
            return "en", 0.0

    def get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name."""
        return LANGUAGE_NAMES.get(lang_code, "English")

    def is_supported(self, lang_code: str) -> bool:
        """Check if language is supported."""
        return lang_code in SUPPORTED_LANGUAGES

    async def detect_and_validate(self, text: str, expected_lang: Optional[str] = None) -> dict:
        """
        Detect language and return detailed result.

        Returns:
            Dict with language, confidence, name, and validation info
        """
        detected_lang, confidence = await self.detect(text)

        result = {
            "detected_language": detected_lang,
            "language_name": self.get_language_name(detected_lang),
            "confidence": confidence,
            "is_supported": self.is_supported(detected_lang),
        }

        if expected_lang:
            result["matches_expected"] = detected_lang == expected_lang
            result["expected_language"] = expected_lang

        return result


# Singleton instance
_language_detection_service: Optional[LanguageDetectionService] = None


def get_language_detection_service() -> LanguageDetectionService:
    """Get or create the language detection service singleton."""
    global _language_detection_service
    if _language_detection_service is None:
        _language_detection_service = LanguageDetectionService()
    return _language_detection_service