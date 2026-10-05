#!/usr/bin/env python3
"""Fail-closed historical verification and pre-production gate.

The generator may propose material, but it cannot approve its own claims unless
an auditable verification bundle is present in the episode JSON.  This gate is
intentionally deterministic and does not pretend that a source marker proves a
claim.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

LEGACY_TERMS = (
    "قصص إسلامية", "السيرة النبوية", "الأنبياء", "الصحابة", "الفتاوى",
    "prophet", "companions", "islamic reminders",
)
REQUIRED_REPORT_FIELDS = {
    "event_name", "period", "location", "main_figures", "key_events",
    "sources", "confirmed_information", "disputed_information",
    "excluded_information", "verified_quotes", "verified_dates",
    "period_technology", "verified_places", "decision",
}
REQUIRED_IDENTITY_FIELDS = {"event_name", "date", "location", "figures", "parties", "cause", "outcome", "result"}
REQUIRED_PRE_FIELDS = {
    "title", "period", "location", "characters", "primary_sources",
    "claim_count", "confirmed_claim_count", "disputed_claim_count",
    "excluded_claim_count", "quotes", "timeline_check", "source_check",
    "event_check", "people_check", "visual_check", "decision",
}
CHECKS = ("factual", "source", "quote", "timeline", "location", "people", "weapons", "visual", "audio", "subtitles", "story")


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(text(item) for item in value)


def check_source(source: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(source, dict):
        return ["كل مصدر يجب أن يكون كائنًا يحتوي title/author/date/url/level/reliability/claim_support"]
    for field in ("title", "author", "date", "url", "level", "reliability", "claim_support"):
        if not text(source.get(field)):
            errors.append(f"مصدر بلا حقل موثق: {field}")
    if text(source.get("level")) not in {"1", "2", "3", "4", "I", "II", "III", "IV"}:
        errors.append("مستوى المصدر يجب أن يكون 1/2/3/4")
    if not re.match(r"^https?://", text(source.get("url"))):
        errors.append("كل مصدر أساسي يجب أن يحتوي رابط تحقق http(s)")
    return errors


def validate_episode(episode: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    report = episode.get("historical_verification_report")
    if not isinstance(report, dict):
        return ["HISTORICAL VERIFICATION REPORT مفقود أو ليس كائنًا"]
    missing = REQUIRED_REPORT_FIELDS - set(report)
    errors.extend(f"تقرير التحقق ناقص: {field}" for field in sorted(missing))
    if text(report.get("decision")) != "APPROVED":
        errors.append("قرار HISTORICAL VERIFICATION REPORT يجب أن يكون APPROVED")
    for field in ("main_figures", "key_events", "sources", "confirmed_information", "verified_dates", "period_technology", "verified_places"):
        if not nonempty_list(report.get(field)):
            errors.append(f"تقرير التحقق يحتاج قائمة غير فارغة: {field}")
    sources = report.get("sources")
    if isinstance(sources, list):
        for source in sources:
            errors.extend(check_source(source))
    else:
        sources = []
    source_names = {text(source.get(field)) for source in sources if isinstance(source, dict)
                    for field in ("title", "url") if text(source.get(field))}
    if sources and not any(isinstance(source, dict) and text(source.get("level")) in {"1", "2", "3", "I", "II", "III"} for source in sources):
        errors.append("لا يجوز الاعتماد على مصادر المستوى الرابع وحدها")
    for field in ("event_name", "period", "location"):
        if not text(report.get(field)):
            errors.append(f"تقرير التحقق يحتاج قيمة موثقة: {field}")
    if not isinstance(report.get("disputed_information"), list):
        errors.append("disputed_information يجب أن يكون قائمة")
    if not isinstance(report.get("excluded_information"), list):
        errors.append("excluded_information يجب أن يكون قائمة")
    if not isinstance(report.get("verified_quotes"), list):
        errors.append("verified_quotes يجب أن يكون قائمة")

    identity = episode.get("event_identity_check")
    if not isinstance(identity, dict):
        errors.append("EVENT IDENTITY CHECK مفقود")
    else:
        errors.extend(f"EVENT IDENTITY CHECK ناقص: {field}" for field in sorted(REQUIRED_IDENTITY_FIELDS - set(identity)))
        if text(identity.get("result")) != "PASS":
            errors.append("EVENT IDENTITY CHECK يجب أن تكون نتيجته PASS")

    facts = episode.get("fact_table")
    if not isinstance(facts, list) or not facts:
        errors.append("جدول الحقائق FACT TABLE مفقود أو فارغ")
    else:
        for index, fact in enumerate(facts, 1):
            if not isinstance(fact, dict):
                errors.append(f"FACT TABLE #{index} ليس كائنًا")
                continue
            for field in ("claim", "source", "confidence", "verified", "decision"):
                if field not in fact:
                    errors.append(f"FACT TABLE #{index} ناقص: {field}")
            confidence = text(fact.get("confidence")).upper()
            decision = text(fact.get("decision")).lower()
            if confidence not in {"A", "B", "C", "D", "E"}:
                errors.append(f"FACT TABLE #{index}: درجة ثقة غير صالحة")
            if not text(fact.get("claim")) or not text(fact.get("source")):
                errors.append(f"FACT TABLE #{index}: ادعاء أو مصدر فارغ")
            if text(fact.get("source")) not in source_names:
                errors.append(f"FACT TABLE #{index}: المصدر غير موجود في تقرير التحقق")
            if confidence == "C" and decision not in {"disputed", "use with qualification", "exclude", "حذف", "استخدام مع توضيح"}:
                errors.append(f"FACT TABLE #{index}: يجب توضيح الخلاف أو حذف ادعاء C")
            if confidence in {"D", "E"} and decision in {"use", "استخدام", "fact", "حقيقة"}:
                errors.append(f"FACT TABLE #{index}: لا يجوز استخدام ادعاء بدرجة {confidence}")
            if confidence in {"A", "B"} and fact.get("verified") is not True:
                errors.append(f"FACT TABLE #{index}: ادعاء A/B يجب أن يكون verified=true")

    pre = episode.get("pre_production_report")
    if not isinstance(pre, dict):
        errors.append("PRE-PRODUCTION REPORT مفقود")
    else:
        errors.extend(f"PRE-PRODUCTION REPORT ناقص: {field}" for field in sorted(REQUIRED_PRE_FIELDS - set(pre)))
        if text(pre.get("decision")) != "APPROVED — PROCEED":
            errors.append("PRE-PRODUCTION REPORT يجب أن ينتهي بـ APPROVED — PROCEED")
        for field in ("timeline_check", "source_check", "event_check", "people_check", "visual_check"):
            if text(pre.get(field)).upper() != "PASS":
                errors.append(f"PRE-PRODUCTION REPORT: {field} يجب أن يكون PASS")

    final = episode.get("final_fact_check")
    if not isinstance(final, dict):
        errors.append("الفحص المستقل النهائي FINAL FACT CHECK مفقود")
    else:
        for field in CHECKS:
            if final.get(field) is not True:
                errors.append(f"FINAL FACT CHECK فشل أو غاب: {field.upper()}")
        if text(final.get("result")).upper() != "PASS":
            errors.append("FINAL FACT CHECK يجب أن تكون نتيجته PASS")

    haystack = " ".join(text(episode.get(key)) for key in ("title", "narration", "region"))
    for term in LEGACY_TERMS:
        if term.casefold() in haystack.casefold():
            errors.append(f"تسريب من الهوية الملغاة: {term}")
    if text(report.get("decision")) == "REJECTED":
        errors.append("الإنتاج مرفوض: لا يجوز متابعة الحلقة")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate historical verification bundle")
    parser.add_argument("--episode", type=Path, required=True)
    args = parser.parse_args()
    try:
        episode = json.loads(args.episode.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"HISTORICAL_GATE: تعذر قراءة الحلقة: {exc}", file=sys.stderr)
        return 1
    errors = validate_episode(episode) if isinstance(episode, dict) else ["ملف الحلقة يجب أن يكون JSON object"]
    if errors:
        print("⚠️ PRODUCTION HALTED — HISTORICAL VERIFICATION FAILURE", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("HISTORICAL_GATE: APPROVED — verification bundle, source claims, identity, and final checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
