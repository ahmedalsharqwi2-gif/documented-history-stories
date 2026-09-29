"""Source-cited religious text bank and exact marker resolver.

Model output may contain at most one marker of the form
[[RELIGIOUS_TEXT:quran_baqarah_2_201]]. The application replaces it with the
verbatim local entry and appends its citation outside the spoken narration.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

try:
    from language_guard import find_non_arabic_letters
except ImportError:  # imported as scripts.religious_texts from tests/tools
    from scripts.language_guard import find_non_arabic_letters

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "religious_texts.json"
MARKER_RE = re.compile(r"\[\[RELIGIOUS_TEXT:([a-z0-9_]+)\]\]")


@dataclass(frozen=True, slots=True)
class ReligiousText:
    id: str
    kind: str
    reference: str
    text_ar: str
    source_url: str
    grading: str | None = None


def _load_catalog(path: Path = CATALOG_PATH) -> Mapping[str, ReligiousText]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("مكتبة النصوص الشرعية يجب أن تكون كائن JSON غير فارغ")
    entries: dict[str, ReligiousText] = {}
    for text_id, item in raw.items():
        if not re.fullmatch(r"[a-z0-9_]+", text_id) or not isinstance(item, dict):
            raise ValueError(f"معرّف/مدخل غير صالح في مكتبة النصوص: {text_id!r}")
        kind = item.get("kind")
        reference = item.get("reference")
        text_ar = item.get("text_ar")
        source_url = item.get("source_url")
        if kind not in {"quran", "hadith"}:
            raise ValueError(f"نوع النص غير صالح للمدخل {text_id}")
        if not all(isinstance(value, str) and value.strip()
                   for value in (reference, text_ar, source_url)):
            raise ValueError(f"مرجع أو نص أو رابط المصدر فارغ للمدخل {text_id}")
        if not source_url.startswith("https://"):
            raise ValueError(f"رابط المصدر يجب أن يستخدم HTTPS للمدخل {text_id}")
        foreign = find_non_arabic_letters(text_ar)
        if foreign:
            raise ValueError(f"النص الشرعي {text_id} يحتوي حروفًا غير عربية: {foreign}")
        grading = item.get("grading")
        if grading is not None and not isinstance(grading, str):
            raise ValueError(f"حقل grading غير صالح للمدخل {text_id}")
        entries[text_id] = ReligiousText(
            id=text_id,
            kind=kind,
            reference=reference.strip(),
            text_ar=text_ar.strip(),
            source_url=source_url.strip(),
            grading=grading.strip() if isinstance(grading, str) else None,
        )
    return MappingProxyType(entries)


RELIGIOUS_TEXTS = _load_catalog()


def get_religious_text(text_id: str) -> ReligiousText:
    """Return an immutable approved entry or raise a clear error for unknown IDs."""
    try:
        return RELIGIOUS_TEXTS[text_id]
    except KeyError as exc:
        raise ValueError(f"معرّف النص الشرعي غير موجود في المكتبة المعتمدة: {text_id}") from exc


def resolve_religious_text_markers(narration: str) -> tuple[str, list[ReligiousText]]:
    """Replace one approved marker verbatim and return the corresponding citation."""
    matches = list(MARKER_RE.finditer(narration))
    if len(matches) > 1:
        raise ValueError("يسمح بإدراج نص شرعي معتمد واحد فقط في الحلقة")
    if not matches:
        if "[[RELIGIOUS_TEXT:" in narration:
            raise ValueError("علامة نص شرعي غير مكتملة أو بصيغة غير معتمدة")
        return narration, []

    entry = get_religious_text(matches[0].group(1))
    resolved = MARKER_RE.sub(lambda _match: f"«{entry.text_ar}»", narration, count=1)
    return resolved, [entry]
