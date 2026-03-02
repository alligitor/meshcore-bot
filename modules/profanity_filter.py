#!/usr/bin/env python3
"""
Shared profanity filter for bridge services (Discord, Telegram).

Uses better-profanity when available; gracefully falls back to no-op if not installed.
Uses unidecode when available to normalize Unicode (e.g. homoglyphs) to ASCII so
better-profanity can detect them.
"""

from typing import Optional

_profanity_available = False
_profanity_initialized = False
_warned_unavailable = False
_unidecode_available = False

try:
    from better_profanity import profanity  # type: ignore
    _profanity_available = True
except ImportError:
    profanity = None  # type: ignore

try:
    from unidecode import unidecode  # type: ignore
    _unidecode_available = True
except ImportError:
    unidecode = None  # type: ignore


def _normalize_for_profanity(text: str) -> str:
    """Convert Unicode to ASCII when unidecode is available (catches homoglyph slurs)."""
    if _unidecode_available and unidecode is not None:
        return unidecode(text)
    return text


def _ensure_initialized(logger: Optional[object] = None) -> bool:
    """Load censor wordlist on first use. Returns True if filtering is available."""
    global _profanity_initialized, _warned_unavailable
    if not _profanity_available:
        if not _warned_unavailable:
            _warned_unavailable = True
            if logger is not None and hasattr(logger, "warning"):
                logger.warning(
                    "better-profanity not installed; profanity filter disabled. "
                    "Install with: pip install better-profanity"
                )
        return False
    if not _profanity_initialized:
        _profanity_initialized = True
        profanity.load_censor_words()
    return True


def censor(text: Optional[str], logger: Optional[object] = None) -> str:
    """
    Replace profanity in text with ****. Returns original text if library unavailable.

    Args:
        text: Input string (message or username).
        logger: Optional logger for one-time warning when better_profanity is not installed.

    Returns:
        Censored string, or original if filtering unavailable / text is None or not str.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        return str(text)
    if not text.strip():
        return text
    if not _ensure_initialized(logger):
        return text
    normalized = _normalize_for_profanity(text)
    return profanity.censor(normalized)


def contains_profanity(text: Optional[str], logger: Optional[object] = None) -> bool:
    """
    Return True if text contains any word from the profanity wordlist.

    Args:
        text: Input string to check.
        logger: Optional logger for one-time warning when better_profanity is not installed.

    Returns:
        True if profanity detected, False otherwise or if library unavailable.
    """
    if text is None or not isinstance(text, str) or not text.strip():
        return False
    if not _ensure_initialized(logger):
        return False
    normalized = _normalize_for_profanity(text)
    return profanity.contains_profanity(normalized)
