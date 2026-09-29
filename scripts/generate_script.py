"""Generate and validate a complete historical/Islamic episode as one JSON object."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from llm_gateway import (
    LLM_INITIAL_BUDGET,
    OutputError,
    _gemini_schema,
    build_providers,
    generate_valid_episode,
)
import llm_gateway
from language_guard import describe_letters, find_non_arabic_letters, has_decimal_digits
from religious_texts import resolve_religious_text_markers

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
PROMPT_PATH = ROOT_DIR / "prompts" / "history_strategy_system_prompt.md"
OUTPUT_PATH = ROOT_DIR / "state" / "current_episode.json"
HISTORY_PATH = ROOT_DIR / "state" / "used_clips.json"

TARGET_WORDS = max(100, int(os.getenv("TARGET_WORDS", "850")))
ACCEPTABLE_MIN_WORDS = max(
    0, int(os.getenv("ACCEPTABLE_MIN_WORDS", os.getenv("MIN_NARRATION_WORDS", "300")))
)
OPENROUTER_MIN_WORDS = max(
    0, int(os.getenv("OPENROUTER_MIN_WORDS", str(ACCEPTABLE_MIN_WORDS)))
)
positive_minima = [n for n in (ACCEPTABLE_MIN_WORDS, OPENROUTER_MIN_WORDS) if n > 0]
MIN_NARRATION_WORDS = min(positive_minima) if positive_minima else 0
MAX_NARRATION_WORDS = max(
    TARGET_WORDS,
    int(os.getenv("MAX_NARRATION_WORDS", str(max(TARGET_WORDS + 150, TARGET_WORDS * 5 // 4)))),
)
MAX_NARRATION_CHARS = max(8000, int(os.getenv("MAX_NARRATION_CHARS", "30000")))
HISTORY_LIMIT = max(1, int(os.getenv("HISTORY_LIMIT", "8")))
REGION_HISTORY_LIMIT = max(1, int(os.getenv("REGION_HISTORY_LIMIT", "6")))
MAX_PHONETIC_HINTS = max(1, int(os.getenv("MAX_PHONETIC_HINTS", "24")))

REQUIRED_KEYS = (
    "title", "hook", "region", "source_type", "source_reference", "narration",
    "visual_keywords", "caption", "phonetic_hints",
)
DEFAULT_VISUAL_KEYWORDS = [
    "historical documentary", "archival documents", "old map", "museum artifact",
    "ancient fortress", "desert landscape", "historic manuscript", "stone ruins",
]
FIELD_LIMITS = {
    "title": 100,
    "hook": 240,
    "region": 180,
    "source_type": 120,
    "source_reference": 700,
    "caption": 1000,
}

EPISODE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "region": {"type": "string"},
        "source_type": {"type": "string"},
        "source_reference": {"type": "string"},
        "narration": {"type": "string"},
        "visual_keywords": {"type": "array", "items": {"type": "string"}},
        "caption": {"type": "string"},
        "phonetic_hints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"word": {"type": "string"}, "phonetic": {"type": "string"}},
                "required": ["word", "phonetic"],
                "additionalProperties": False,
            },
        },
    },
    "required": list(REQUIRED_KEYS),
    "additionalProperties": False,
}

DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064A\u0671]")
SENTENCE_ENDERS = (".", "!", "؟", "?", "…")
TRAILING_WRAPPERS = ")\"'”’»」』﴾]"
TRAILING_PAREN_GROUP = re.compile(r"[\(（][^()（）]*[\)）]\s*$")
CONTENT_RED_FLAGS = ("السيلينس", "الشهرات الجوية", "المحتلة بالدقيق", "البركان الثلجي")


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_history_field(field: str, limit: int) -> list[str]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("history"), list):
        return []
    return [
        str(item.get(field, "")).strip()
        for item in data["history"]
        if isinstance(item, dict) and str(item.get(field, "")).strip()
    ][-limit:]


def load_used_history(limit: int = HISTORY_LIMIT) -> list[str]:
    return _load_history_field("title", limit)


def load_used_regions(limit: int = REGION_HISTORY_LIMIT) -> list[str]:
    return _load_history_field("region", limit)


def load_used_hooks(limit: int = HISTORY_LIMIT) -> list[str]:
    return _load_history_field("hook", limit)


def count_words(text: str) -> int:
    return len(text.split())


def looks_truncated(narration: str) -> bool:
    stripped = (narration or "").strip()
    if not stripped:
        return True
    match = TRAILING_PAREN_GROUP.search(stripped)
    if match and stripped[:match.start()].strip():
        stripped = stripped[:match.start()].rstrip()
    stripped = stripped.rstrip(TRAILING_WRAPPERS)
    return not stripped or not stripped.endswith(SENTENCE_ENDERS)


def strip_diacritics(text: str) -> str:
    return DIACRITICS_RE.sub("", text or "")


def _plain_arabic(text: str) -> str:
    return re.sub(r"\s+", " ", strip_diacritics(text)).strip()


def find_content_red_flag(text: str) -> str | None:
    plain = strip_diacritics(text or "")
    return next((flag for flag in CONTENT_RED_FLAGS if flag in plain), None)


def _hint_word_is_in_narration(word: str, narration: str) -> bool:
    plain_word = _plain_arabic(word)
    plain_narration = _plain_arabic(narration)
    if not plain_word:
        return False
    letters = r"[\u0621-\u064A\u0671]"
    pattern = rf"(?<!{letters}){re.escape(plain_word)}(?!{letters})"
    return re.search(pattern, plain_narration) is not None


def normalize_phonetic_hints(value, narration: str) -> list[dict[str, str]]:
    """Keep only short, exact, pronounceable hints that occur in the narration."""
    if not isinstance(value, list):
        if value not in (None, ""):
            print("⚠️ phonetic_hints ليست قائمة؛ سيتم تجاهلها وإخراج قائمة فارغة")
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        word, phonetic = item.get("word"), item.get("phonetic")
        if not isinstance(word, str) or not isinstance(phonetic, str):
            continue
        word, phonetic = re.sub(r"\s+", " ", word).strip(), re.sub(r"\s+", " ", phonetic).strip()
        if not word or not phonetic or len(word) > 80 or len(phonetic) > 120:
            continue
        for field_name, value in (("word", word), ("phonetic", phonetic)):
            foreign = find_non_arabic_letters(value)
            if foreign:
                raise OutputError(
                    f"phonetic_hints.{field_name} يحتوي أحرفًا غير عربية: "
                    f"{describe_letters(foreign)}"
                )
        if _plain_arabic(word) != _plain_arabic(phonetic):
            continue
        if not _hint_word_is_in_narration(word, narration):
            continue
        identity = _plain_arabic(word)
        if identity in seen:
            continue
        seen.add(identity)
        result.append({"word": word, "phonetic": phonetic})
        if len(result) >= MAX_PHONETIC_HINTS:
            break
    if isinstance(value, list) and len(result) != len(value):
        print(f"ℹ️ تم تجاهل {len(value) - len(result)} تلميح/تلميحات نطق غير صالحة")
    return result


def normalize_episode(raw: dict) -> dict:
    """Normalize harmless shape variation; reject missing/wrong core data and long fields."""
    if not isinstance(raw, dict):
        raise OutputError("جذر الرد يجب أن يكون كائن JSON")
    unknown = sorted(set(raw) - set(REQUIRED_KEYS))
    if unknown:
        print(f"ℹ️ تم تجاهل حقول زائدة من المزوّد: {unknown[:8]}")

    episode: dict = {}
    for key in REQUIRED_KEYS:
        value = raw.get(key)
        if key in ("visual_keywords", "phonetic_hints"):
            continue
        if value is None and key in ("title", "caption"):
            value = raw.get("hook", "")
        if not isinstance(value, str):
            if key not in raw:
                continue
            raise OutputError(f"الحقل {key} يجب أن يكون نصًا، لا {type(value).__name__}")
        value = re.sub(r"\s+", " ", value).strip()
        limit = MAX_NARRATION_CHARS if key == "narration" else FIELD_LIMITS[key]
        if len(value) > limit:
            raise OutputError(
                f"الحقل {key} أطول من الحد ({len(value)} حرفًا؛ الحد {limit})"
            )
        episode[key] = value

    narration = episode.get("narration", "")
    if len(narration) > MAX_NARRATION_CHARS:
        raise OutputError(
            f"حقل narration طويل جدًا ({len(narration)} حرفًا؛ الحد {MAX_NARRATION_CHARS})"
        )

    raw_keywords = raw.get("visual_keywords", [])
    if not isinstance(raw_keywords, list):
        print("⚠️ visual_keywords ليست قائمة؛ ستُستخدم الكلمات الاحتياطية")
        raw_keywords = []
    keywords: list[str] = []
    seen_keywords: set[str] = set()
    for value in raw_keywords:
        if not isinstance(value, str):
            continue
        value = re.sub(r"\s+", " ", value).strip()
        if not value:
            continue
        if len(value) > 120:
            raise OutputError(f"أحد عناصر visual_keywords طويل جدًا ({len(value)} حرفًا؛ الحد 120)")
        key = value.casefold()
        if key not in seen_keywords:
            seen_keywords.add(key)
            keywords.append(value)
    if not keywords:
        keywords = DEFAULT_VISUAL_KEYWORDS.copy()
    if len(keywords) > 12:
        raise OutputError(f"visual_keywords تحتوي {len(keywords)} عنصرًا؛ الحد الأقصى 12")
    episode["visual_keywords"] = keywords

    try:
        narration, religious_entries = resolve_religious_text_markers(narration)
    except ValueError as exc:
        raise OutputError(str(exc)) from exc
    episode["narration"] = narration
    if religious_entries:
        source_reference = episode.get("source_reference", "").strip()
        if not source_reference:
            raise OutputError("لا يمكن إدراج نص شرعي دون مرجع المصدر الأساسي")
        citation = "؛ نص شرعي: " + "، ".join(
            f"{entry.reference} ({entry.source_url})" for entry in religious_entries
        )
        episode["source_reference"] = source_reference.rstrip(" ؛،") + citation
        if len(episode["source_reference"]) > FIELD_LIMITS["source_reference"]:
            raise OutputError("إضافة مرجع النص الشرعي تجاوزت حد source_reference")
    episode["phonetic_hints"] = normalize_phonetic_hints(raw.get("phonetic_hints", []), narration)
    # Preserve the requested stable key order for artifacts and downstream consumers.
    return {key: episode[key] for key in REQUIRED_KEYS if key in episode}


def validate_episode(episode: dict) -> None:
    """Semantic validation after parsing/normalization; never trust schema alone."""
    if not isinstance(episode, dict):
        raise OutputError("الحلقة النهائية ليست كائن JSON")
    missing = [key for key in REQUIRED_KEYS if key not in episode]
    if missing:
        raise OutputError(f"حقول الحلقة المطلوبة ناقصة: {missing}")

    for key in ("title", "hook", "region", "source_type", "source_reference", "narration", "caption"):
        value = episode.get(key)
        if not isinstance(value, str) or not value.strip():
            raise OutputError(f"الحقل {key} فارغ أو ليس نصًا")
        if len(value) > FIELD_LIMITS.get(key, MAX_NARRATION_CHARS):
            raise OutputError(f"الحقل {key} يتجاوز حد الطول المسموح")

    for key in ("title", "hook", "region", "narration", "caption"):
        value = episode[key]
        foreign = find_non_arabic_letters(value)
        if foreign:
            raise OutputError(
                f"الحقل {key} يحتوي أحرفًا من لغات أخرى؛ عرّب الاسم أو المصطلح: "
                f"{describe_letters(foreign)}"
            )
        if has_decimal_digits(value):
            raise OutputError(f"اكتب الأعداد بالحروف في الحقل {key}، لا بالأرقام")

    hook = episode["hook"].strip()
    if count_words(hook) > 28:
        raise OutputError("hook أطول من اللازم (الحد الأقصى 28 كلمة)")
    narration = episode["narration"].strip()
    red_flag = find_content_red_flag(narration)
    if red_flag:
        raise OutputError(f"النص يحتوي مصطلحًا علميًا مرفوضًا أو مختلقًا: {red_flag}")
    if looks_truncated(narration):
        raise OutputError("نص narration يبدو مقطوعًا أو لا ينتهي بعلامة ترقيم")
    word_count = count_words(narration)
    if MIN_NARRATION_WORDS and word_count < MIN_NARRATION_WORDS:
        raise OutputError(
            f"narration قصيرة ({word_count} كلمة؛ الحد الأدنى {MIN_NARRATION_WORDS})"
        )
    if word_count > MAX_NARRATION_WORDS:
        raise OutputError(
            f"narration طويلة ({word_count} كلمة؛ الحد الأقصى {MAX_NARRATION_WORDS})"
        )

    keywords = episode["visual_keywords"]
    if not isinstance(keywords, list) or not (4 <= len(keywords) <= 12):
        raise OutputError("visual_keywords يجب أن تكون قائمة من 4 إلى 12 كلمة بحث")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 120 for item in keywords):
        raise OutputError("كل عنصر في visual_keywords يجب أن يكون نصًا قصيرًا غير فارغ")

    hints = episode["phonetic_hints"]
    if not isinstance(hints, list) or len(hints) > MAX_PHONETIC_HINTS:
        raise OutputError(f"phonetic_hints يجب أن تكون قائمة لا تتجاوز {MAX_PHONETIC_HINTS} عنصرًا")
    for hint in hints:
        if not isinstance(hint, dict) or set(hint) != {"word", "phonetic"}:
            raise OutputError("عنصر phonetic_hints يجب أن يحتوي word وphonetic فقط")
        if not _hint_word_is_in_narration(hint["word"], narration):
            raise OutputError(f"كلمة phonetic_hints غير موجودة في narration: {hint['word']}")
        if _plain_arabic(hint["word"]) != _plain_arabic(hint["phonetic"]):
            raise OutputError(f"phonetic يجب أن يضيف التشكيل فقط دون تغيير حروف: {hint['word']}")


def to_gemini_schema(schema: dict) -> dict:
    """Expose a module-level schema converter for compatibility and tests."""
    return _gemini_schema(schema)


def build_user_message(
    recent_titles: list[str], recent_regions: list[str], recent_hooks: list[str],
) -> str:
    message = (
        "اكتب حلقة تاريخية جديدة كاملة، مع الالتزام بموضوع وقواعد التوثيق "
        "واللغة والأمانة التاريخية في تعليمات النظام كما هي. لا تغيّر نطاق المحتوى "
        "ولا تضف موضوعات رعب. المطلوب تغيير طريقة الإخراج والتحقق فقط.\n\n"
        "أخرج كائن JSON واحدًا فقط وفق مخطط الإخراج المحدد، دون مقدمة أو Markdown. "
        "يجب أن يحتوي الحقول: title, hook, region, source_type, source_reference, "
        "narration, visual_keywords, caption, phonetic_hints.\n\n"
        f"اكتب narration بالعربية الفصحى، مكتملة من الخطاف إلى الخاتمة، بطول يقارب "
        f"{TARGET_WORDS} كلمة، ولا يقل عن {MIN_NARRATION_WORDS or 'الحد المعقول'} "
        f"ولا يزيد عن {MAX_NARRATION_WORDS} كلمة. لا تحشو ولا تخترع تفاصيل أو مراجع.\n\n"
        "اجعل title عنوانًا واضحًا موجزًا (100 حرف بحد أقصى)، وhook هو الخطاف "
        "المشوّق نفسه الذي يبدأ به narration. اجعل source_type وsource_reference "
        "محددين وقابلين للمراجعة، ولا تخترع أرقام صفحات أو بيانات مرجعية.\n\n"
        "اجعل visual_keywords قائمة من 8 إلى 10 عبارات بحث إنجليزية قصيرة وملموسة "
        "تطابق أحداث القصة ولا تجسّد شخصيات دينية أو تاريخية بأجسادها. اجعل caption "
        "وصفًا عربيًا موجزًا بلا حشو.\n\n"
        "اجعل phonetic_hints قائمة (أو [] عند عدم الحاجة) من كائنات بهذا الشكل فقط: "
        '{"word":"الكلمة كما ظهرت في narration","phonetic":"الكلمة نفسها مع التشكيل"}. '
        "كل word يجب أن تكون موجودة حرفيًا في narration بعد تجاهل التشكيل، وphonetic "
        "لا يغيّر أي حرف؛ يضيف الحركات فقط. لا تضع جملًا أو شروحًا داخل الحقل."
    )
    if recent_titles:
        message += "\n\nعناوين سابقة لتجنب التكرار:\n- " + "\n- ".join(recent_titles)
    if recent_hooks:
        message += "\n\nوقائع/هوكات سابقة لتجنب إعادة الواقعة نفسها:\n- " + "\n- ".join(recent_hooks)
    if recent_regions:
        message += "\n\nعصور أو أماكن الحلقات الأخيرة، اختر غيرها عند الإمكان:\n- " + "\n- ".join(recent_regions)
    return message


def generate_episode() -> dict:
    if not any((
        os.getenv("GEMINI_API_KEY", "").strip(),
        os.getenv("GROQ_API_KEY", "").strip(),
        os.getenv("OPENROUTER_API_KEY", "").strip(),
    )):
        raise SystemExit("خطأ: أضف GEMINI_API_KEY أو GROQ_API_KEY أو OPENROUTER_API_KEY إلى GitHub Secrets")

    system_prompt = load_system_prompt()
    user_message = build_user_message(
        load_used_history(), load_used_regions(), load_used_hooks()
    )
    providers = build_providers(EPISODE_SCHEMA, to_gemini_schema)
    print(
        f"🕌 بوابة التوليد: {len(providers)} مزوّد/نموذج مهيأ | "
        f"النداءات القصوى: {os.getenv('LLM_MAX_CALLS', '6')} | "
        f"الهدف: {TARGET_WORDS} كلمة | المقبول: {MIN_NARRATION_WORDS}–{MAX_NARRATION_WORDS}"
    )
    try:
        episode, provider = generate_valid_episode(
            system_prompt=system_prompt,
            user_message=user_message,
            budget=LLM_INITIAL_BUDGET,
            providers=providers,
            validate=validate_episode,
            normalize=normalize_episode,
        )
    except Exception as exc:  # noqa: BLE001 - command-line boundary
        raise SystemExit(f"❌ فشل توليد حلقة سليمة بعد {llm_gateway.MODEL_CALL_COUNT} نداءات: {exc}") from exc
    print(f"✅ المزوّد الناجح: {provider}")
    print(f"   عدد كلمات narration: {count_words(episode['narration'])}")
    print(f"   الهوك: {episode['hook'][:80]}")
    print(f"   المصدر: {episode['source_type']} — {episode['source_reference'][:200]}")
    print(f"   كلمات البحث: {len(episode['visual_keywords'])} | تلميحات النطق: {len(episode['phonetic_hints'])}")
    return episode


def write_episode(episode: dict) -> None:
    """Atomically replace the JSON artifact, so failed writes never leave a partial episode."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(episode, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(OUTPUT_PATH)


if __name__ == "__main__":
    write_episode(generate_episode())
    print(f"✅ اتكتبت الحلقة: {OUTPUT_PATH}")
