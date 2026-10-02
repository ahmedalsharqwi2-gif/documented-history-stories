"""Safe Arabic ASS caption rendering shared by the speech pipeline."""
from __future__ import annotations

import re

# Bidi controls are presentation metadata, not word content.  Passing them
# through to libass can split an Arabic shaping run in some renderers.
BIDI_CONTROLS = re.compile(r"[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]")
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08FF]")
DISPLAY_PUNCTUATION = str.maketrans(".,،؛:!?؟…-—_()[]{}\"«»/\\", " " * 23)


def display_word(word: str) -> str:
    """Return a clean display token while preserving Arabic joining."""
    word = BIDI_CONTROLS.sub("", str(word or ""))
    return ARABIC_DIACRITICS.sub("", word).translate(DISPLAY_PUNCTUATION).strip()


def render_arabic_caption(words: list[str]) -> str:
    """Render a short Arabic caption using ASS ``\\N`` for the line break.

    Direction controls are deliberately omitted: libass shapes the Arabic
    text, and hidden U+200F markers can split joining on some renderers.
    """
    clean_words = [display_word(word) for word in words]
    clean_words = [word for word in clean_words if word]
    if len(clean_words) <= 3:
        return " ".join(clean_words)
    midpoint = (len(clean_words) + 1) // 2
    return " ".join(clean_words[:midpoint]) + r"\N" + " ".join(clean_words[midpoint:])
