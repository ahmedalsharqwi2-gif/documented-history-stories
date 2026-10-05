#!/usr/bin/env python3
"""Fail-closed source and claim gate for Islamic historical episodes.

This gate is intentionally conservative: it blocks publication when the
source is not independently identifiable or when the narration contains
high-risk anachronistic/unsupported claims. It does not replace scholarly
review; it prevents an unreviewed model output from reaching a platform.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# These terms are known red flags for the current production failure and for
# claims that require an explicit, source-verified editorial exception.
FORBIDDEN_CLAIMS = (
    "القنابل",
    "قنابل",
    "المتفجرات",
    "متفجرات",
    "البارود",
    "تفجير جدار",
    "تفجير سور",
    "سور مكة",
    "حائط مكة",
    "غزوة حمص",
    "خالية من القتلى",
    "لن نرى عدوًا يقف أمامنا",
    "التاريخ الإسلامي للأحمد بن حنبل",
)

# A source must identify a real, checkable primary or recognized secondary
# source. Generic labels and invented bibliographic strings are rejected.
APPROVED_SOURCE_MARKERS = (
    "القرآن الكريم",
    "صحيح البخاري",
    "صحيح مسلم",
    "سنن أبي داود",
    "سنن الترمذي",
    "سنن النسائي",
    "سنن ابن ماجه",
    "السيرة النبوية لابن هشام",
    "البداية والنهاية",
    "تاريخ الطبري",
    "وزارة الأوقاف",
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

    narration = normalize(episode.get("narration"))
    title = normalize(episode.get("title"))
    source = normalize(episode.get("source_reference"))
    keywords = [normalize(x) for x in episode.get("visual_keywords", [])]
    haystack = " ".join((title, narration, source, *keywords))

    errors: list[str] = []
    if len(narration) < 200:
        errors.append("النص قصير أو مفقود")
    if not source:
        errors.append("المصدر مفقود")
    elif not any(marker in source for marker in APPROVED_SOURCE_MARKERS):
        errors.append(f"المصدر غير قابل للتحقق أو غير معتمد: {source}")

    for claim in FORBIDDEN_CLAIMS:
        if claim in haystack:
            errors.append(f"ادعاء محظور يحتاج مراجعة بشرية ومصدرًا صريحًا: {claim}")

    # Reject visual prompts that directly request modern or anachronistic
    # military imagery for early Islamic history.
    visual_red_flags = ("cannon", "musket", "modern", "fortress wall")
    for keyword in keywords:
        lowered = keyword.lower()
        if any(flag in lowered for flag in visual_red_flags) or re.search(r"\bcar\b|\bcars\b", lowered):
            errors.append(f"كلمة بصرية غير مناسبة/أنكرونية: {keyword}")

    if errors:
        print("SOURCE_GATE: فشل التحقق — أُوقف المسار قبل النشر.", file=sys.stderr)
        for error in dict.fromkeys(errors):
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"SOURCE_GATE: passed ({title})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
