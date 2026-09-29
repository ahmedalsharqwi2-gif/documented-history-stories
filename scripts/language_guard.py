"""Deterministic Arabic-script and TTS-input guards; intentionally no LLM calls."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable


def find_non_arabic_letters(text: str) -> list[str]:
    """Return distinct Unicode letters that do not belong to Arabic script."""
    return sorted({
        char
        for char in str(text or "")
        if unicodedata.category(char).startswith("L")
        and not unicodedata.name(char, "").startswith("ARABIC ")
    })


def describe_letters(characters: list[str]) -> str:
    return ", ".join(
        f"{char!r} (U+{ord(char):04X} {unicodedata.name(char, 'UNKNOWN')})"
        for char in characters[:8]
    )


def has_decimal_digits(text: str) -> bool:
    return any(char.isdecimal() for char in str(text or ""))


def validate_phonetic_hints(
    narration: str,
    hints: object,
    strip_diacritics: Callable[[str], str],
) -> None:
    """Fail closed on malformed/stale hints before synthesis consumes them."""
    if hints is None:
        return
    if not isinstance(hints, list):
        raise ValueError("phonetic_hints يجب أن تكون قائمة")

    plain_narration = re.sub(r"\s+", " ", strip_diacritics(narration)).strip()
    for index, hint in enumerate(hints):
        if not isinstance(hint, dict) or set(hint) != {"word", "phonetic"}:
            raise ValueError(f"phonetic_hints[{index}] يجب أن يحتوي word وphonetic فقط")
        word, phonetic = hint["word"], hint["phonetic"]
        if not isinstance(word, str) or not isinstance(phonetic, str):
            raise ValueError(f"phonetic_hints[{index}] يجب أن تكون قيمتاه نصّين")
        if not word.strip() or not phonetic.strip():
            raise ValueError(f"phonetic_hints[{index}] فارغ")
        for field_name, value in (("word", word), ("phonetic", phonetic)):
            foreign = find_non_arabic_letters(value)
            if foreign:
                raise ValueError(
                    f"phonetic_hints[{index}].{field_name} يحتوي أحرفًا غير عربية: "
                    f"{describe_letters(foreign)}"
                )
        plain_word = re.sub(r"\s+", " ", strip_diacritics(word)).strip()
        plain_phonetic = re.sub(r"\s+", " ", strip_diacritics(phonetic)).strip()
        if not plain_word or plain_word != plain_phonetic:
            raise ValueError(
                f"phonetic_hints[{index}] يجب أن يضيف التشكيل فقط دون تغيير الحروف"
            )
        if plain_word not in plain_narration:
            raise ValueError(
                f"phonetic_hints[{index}].word غير موجودة في narration: {word}"
            )
