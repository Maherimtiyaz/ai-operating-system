"""
Language support for speech recognition
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class LanguageInfo:
    """Language information"""
    code: str
    name: str
    native_name: str
    whisper_code: str  # Code used by Whisper
    is_rtl: bool = False


# Language database
LANGUAGES: Dict[str, LanguageInfo] = {
    "en": LanguageInfo(
        code="en",
        name="English",
        native_name="English",
        whisper_code="en",
        is_rtl=False,
    ),
    "zh": LanguageInfo(
        code="zh",
        name="Chinese",
        native_name="中文",
        whisper_code="zh",
        is_rtl=False,
    ),
    "de": LanguageInfo(
        code="de",
        name="German",
        native_name="Deutsch",
        whisper_code="de",
        is_rtl=False,
    ),
    "es": LanguageInfo(
        code="es",
        name="Spanish",
        native_name="Español",
        whisper_code="es",
        is_rtl=False,
    ),
    "ru": LanguageInfo(
        code="ru",
        name="Russian",
        native_name="Русский",
        whisper_code="ru",
        is_rtl=False,
    ),
    "fr": LanguageInfo(
        code="fr",
        name="French",
        native_name="Français",
        whisper_code="fr",
        is_rtl=False,
    ),
    "ja": LanguageInfo(
        code="ja",
        name="Japanese",
        native_name="日本語",
        whisper_code="ja",
        is_rtl=False,
    ),
    "pt": LanguageInfo(
        code="pt",
        name="Portuguese",
        native_name="Português",
        whisper_code="pt",
        is_rtl=False,
    ),
    "ar": LanguageInfo(
        code="ar",
        name="Arabic",
        native_name="العربية",
        whisper_code="ar",
        is_rtl=True,
    ),
    "hi": LanguageInfo(
        code="hi",
        name="Hindi",
        native_name="हिन्दी",
        whisper_code="hi",
        is_rtl=False,
    ),
    "ko": LanguageInfo(
        code="ko",
        name="Korean",
        native_name="한국어",
        whisper_code="ko",
        is_rtl=False,
    ),
    "it": LanguageInfo(
        code="it",
        name="Italian",
        native_name="Italiano",
        whisper_code="it",
        is_rtl=False,
    ),
    "nl": LanguageInfo(
        code="nl",
        name="Dutch",
        native_name="Nederlands",
        whisper_code="nl",
        is_rtl=False,
    ),
    "pl": LanguageInfo(
        code="pl",
        name="Polish",
        native_name="Polski",
        whisper_code="pl",
        is_rtl=False,
    ),
    "sv": LanguageInfo(
        code="sv",
        name="Swedish",
        native_name="Svenska",
        whisper_code="sv",
        is_rtl=False,
    ),
    "fi": LanguageInfo(
        code="fi",
        name="Finnish",
        native_name="Suomi",
        whisper_code="fi",
        is_rtl=False,
    ),
    "da": LanguageInfo(
        code="da",
        name="Danish",
        native_name="Dansk",
        whisper_code="da",
        is_rtl=False,
    ),
    "no": LanguageInfo(
        code="no",
        name="Norwegian",
        native_name="Norsk",
        whisper_code="no",
        is_rtl=False,
    ),
    "he": LanguageInfo(
        code="he",
        name="Hebrew",
        native_name="עברית",
        whisper_code="he",
        is_rtl=True,
    ),
    "tr": LanguageInfo(
        code="tr",
        name="Turkish",
        native_name="Türkçe",
        whisper_code="tr",
        is_rtl=False,
    ),
    "th": LanguageInfo(
        code="th",
        name="Thai",
        native_name="ไทย",
        whisper_code="th",
        is_rtl=False,
    ),
    "vi": LanguageInfo(
        code="vi",
        name="Vietnamese",
        native_name="Tiếng Việt",
        whisper_code="vi",
        is_rtl=False,
    ),
    "id": LanguageInfo(
        code="id",
        name="Indonesian",
        native_name="Bahasa Indonesia",
        whisper_code="id",
        is_rtl=False,
    ),
    "hu": LanguageInfo(
        code="hu",
        name="Hungarian",
        native_name="Magyar",
        whisper_code="hu",
        is_rtl=False,
    ),
    "el": LanguageInfo(
        code="el",
        name="Greek",
        native_name="Ελληνικά",
        whisper_code="el",
        is_rtl=False,
    ),
    "cs": LanguageInfo(
        code="cs",
        name="Czech",
        native_name="Čeština",
        whisper_code="cs",
        is_rtl=False,
    ),
    "ro": LanguageInfo(
        code="ro",
        name="Romanian",
        native_name="Română",
        whisper_code="ro",
        is_rtl=False,
    ),
    "uk": LanguageInfo(
        code="uk",
        name="Ukrainian",
        native_name="Українська",
        whisper_code="uk",
        is_rtl=False,
    ),
}


def get_language(language_code: str) -> Optional[LanguageInfo]:
    """Get language information by code"""
    return LANGUAGES.get(language_code.lower())


def get_language_by_whisper_code(whisper_code: str) -> Optional[LanguageInfo]:
    """Get language information by Whisper code"""
    for lang in LANGUAGES.values():
        if lang.whisper_code == whisper_code:
            return lang
    return None


def list_languages() -> List[LanguageInfo]:
    """List all supported languages"""
    return list(LANGUAGES.values())


def get_language_name(language_code: str) -> str:
    """Get language name by code"""
    lang = get_language(language_code)
    return lang.name if lang else "Unknown"


def get_native_language_name(language_code: str) -> str:
    """Get native language name by code"""
    lang = get_language(language_code)
    return lang.native_name if lang else "Unknown"


def is_rtl_language(language_code: str) -> bool:
    """Check if language is right-to-left"""
    lang = get_language(language_code)
    return lang.is_rtl if lang else False


# Common language codes
LANGUAGE_ENGLISH = "en"
LANGUAGE_CHINESE = "zh"
LANGUAGE_SPANISH = "es"
LANGUAGE_FRENCH = "fr"
LANGUAGE_GERMAN = "de"
LANGUAGE_RUSSIAN = "ru"
LANGUAGE_JAPANESE = "ja"
LANGUAGE_ARABIC = "ar"
LANGUAGE_HINDI = "hi"
LANGUAGE_PORTUGUESE = "pt"
LANGUAGE_ITALIAN = "it"
