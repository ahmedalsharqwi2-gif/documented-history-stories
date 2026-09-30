"""Arabic TTS preprocessing: pronunciation dictionary plus optional Mantoq."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ARABIC_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
ARABIC_LETTERS = r"\u0621-\u064A\u0671"


def strip_marks(text: str) -> str:
    return ARABIC_MARKS.sub("", text or "")


def load_pronunciation_dictionary(path: str | Path) -> dict[str, str]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    data = json.loads(file_path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for source, value in data.items():
        spoken = value.get("spoken", "") if isinstance(value, dict) else value
        if isinstance(spoken, str) and spoken.strip():
            result[str(source).strip()] = spoken.strip()
    return result


def apply_pronunciation_dictionary(text: str, pronunciation_map: dict[str, str]) -> str:
    result = text
    for source in sorted(pronunciation_map, key=len, reverse=True):
        spoken = pronunciation_map[source]
        pattern = rf"(?<![{ARABIC_LETTERS}]){re.escape(source)}(?![{ARABIC_LETTERS}])"
        result = re.sub(pattern, spoken, result)
    return result


def _validate_same_words(original: str, processed: str) -> None:
    if strip_marks(original).split() != strip_marks(processed).split():
        raise ValueError("Pronunciation preprocessing changed the Arabic word sequence")


def mantoq_vocalize(text: str) -> tuple[str, list[str]]:
    try:
        import mantoq
    except ImportError:
        if os.getenv("MANTOQ_REQUIRED", "false").lower() == "true":
            raise RuntimeError("Mantoq is required but not installed")
        return text, []
    normalized, phonemes = mantoq.g2p(
        text, add_tashkeel=True, process_numbers=True, append_eos=False
    )
    return normalized, phonemes


def prepare_tts_text(
    text: str,
    dictionary_path: str | Path = "config/arabic_pronunciation.json",
) -> tuple[str, list[str]]:
    mapped = apply_pronunciation_dictionary(
        text, load_pronunciation_dictionary(dictionary_path)
    )
    _validate_same_words(text, mapped)
    vocalized, phonemes = mantoq_vocalize(mapped)
    _validate_same_words(mapped, vocalized)
    return vocalized, phonemes
