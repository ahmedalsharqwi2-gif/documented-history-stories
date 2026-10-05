#!/usr/bin/env python3
"""Fail-closed source and historical-claim gate for the new channel identity."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Legacy identity must not leak back into the new editorial pipeline.
LEGACY_IDENTITY_TERMS = (
    "قصص إسلامية", "التاريخ الإسلامي", "السيرة النبوية", "الأنبياء", "الصحابة",
    "النبي محمد", "القرآن", "صحيح البخاري", "صحيح مسلم", "غزوة", "فتوحات إسلامية",
)
SOCIAL_OR_UNVERIFIED = (
    "فيسبوك", "انستغرام", "إنستغرام", "تيك توك", "تويتر", "واتساب",
    "منشور", "مواقع التواصل", "مصدر مجهول", "رواية متداولة", "قصة متناقلة",
)
# These terms are high-risk unless the episode has a verified primary source
# and a human-reviewed exception. Keeping them blocked is safer than guessing.
UNSUPPORTED_FORMULATIONS = (
    "أعظم سر في التاريخ", "لا يصدق", "بلا أي دليل", "قال الملك",
    "قال القائد", "آخر كلماته كانت", "المؤامرة التي لا يعرفها أحد",
)
RECOGNIZED_SOURCE_MARKERS = (
    "أرشيف", "وثيقة", "سجل", "مخطوط", "متحف", "جامعة", "مؤسسة أثرية",
    "دراسة محكمة", "مجلة علمية", "كتاب", "موسوعة", "المكتبة الوطنية",
    "archive", "museum", "university", "journal", "book", "encyclopedia",
    "primary source", "official record",
)
VISUAL_RED_FLAGS = (
    "stock footage generic",
)


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    args = parser.parse_args()
    try:
        episode = json.loads(args.episode.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"SOURCE_GATE: تعذر قراءة ملف الحلقة: {exc}", file=sys.stderr)
        return 1
    if not isinstance(episode, dict):
        print("SOURCE_GATE: ملف الحلقة ليس كائن JSON", file=sys.stderr)
        return 1

    title = normalize(episode.get("title"))
    narration = normalize(episode.get("narration"))
    source_type = normalize(episode.get("source_type"))
    source = normalize(episode.get("source_reference"))
    keywords = [normalize(x) for x in episode.get("visual_keywords", [])]
    haystack = " ".join((title, narration, source_type, source, *keywords))
    haystack_folded = haystack.casefold()
    errors: list[str] = []

    if len(narration.split()) < 180:
        errors.append("النص قصير أو مفقود")
    if not source_type:
        errors.append("نوع المصدر مفقود")
    if not source:
        errors.append("المصدر مفقود")
    elif not any(marker.casefold() in source.casefold() for marker in RECOGNIZED_SOURCE_MARKERS):
        errors.append(f"المصدر غير قابل للتعرف والتحقق: {source}")
    if any(term.casefold() in haystack_folded for term in SOCIAL_OR_UNVERIFIED):
        errors.append("المصدر أو السرد يعتمد على مادة اجتماعية/مجهولة")
    for term in LEGACY_IDENTITY_TERMS:
        if term.casefold() in haystack_folded:
            errors.append(f"تسريب من الهوية القديمة: {term}")
    for phrase in UNSUPPORTED_FORMULATIONS:
        if phrase.casefold() in haystack_folded:
            errors.append(f"صياغة إثارة غير موثقة: {phrase}")

    if len(keywords) < 8:
        errors.append("عدد الكلمات البصرية أقل من ثمانية")
    # Weapons and transport are era-dependent; the actual-video review gate
    # checks them against the verification report rather than banning all eras.
    for keyword in keywords:
        lowered = keyword.casefold()
        if any(flag in lowered for flag in VISUAL_RED_FLAGS):
            errors.append(f"كلمة بصرية أنكرونية أو عامة: {keyword}")

    # Quoted dialogue is not accepted unless the episode explicitly labels a
    # source location. This conservative rule blocks invented cinematic speech.
    quoted = re.findall(r"[«\"].{3,}?[»\"]", narration)
    if quoted and not re.search(r"(ص\.?\s*\d+|صفحة|page\s*\d+|document|archive|سجل|وثيقة)", source, re.I):
        errors.append("يوجد اقتباس مباشر بلا موضع توثيق واضح")

    if errors:
        print("SOURCE_GATE: فشل التحقق — أُوقف المسار قبل الإنتاج أو النشر.", file=sys.stderr)
        for error in dict.fromkeys(errors):
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"SOURCE_GATE: passed ({title})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
