"""
generate_script.py
يستدعي Gemini API عشان يولّد سيناريو القصة التاريخية +
الترجمة العربية + كلمات البحث البصرية + مرجع التوثيق الشرعي.

=== نداء واحد للقصة كاملة + قبول طول "مقارب" بدل الإجبار ===
  1) نطلب من الموديل يكتب القصة *كاملة* في نداء واحد بهدف طول تقريبي.
  2) لو القصة متماسكة ومنتهية بخاتمة حقيقية وأطول من الحد الأدنى تتقبل زي ما هي.
  3) لو أقل من الحد الأدنى: جولات توسيع (MAX_EXPANSION_ROUNDS) بنحتفظ فيها
     دايمًا بأطول نسخة مكتملة.
  4) لو النداء اتقطع قبل خاتمة حقيقية: نداء "إكمال خاتمة" واحد.

=== إعادة محاولة تلقائية عند أخطاء السيرفر المؤقتة (503 وما شابه) ===
exponential backoff لغاية TRANSIENT_RETRIES مرة، وبعدها ننتقل للموديل التالي.

=== ترتيب التحويل بين الموديلات (تعديل جديد) ===
Gemini الأساسي  ->  موديلات Gemini الاحتياطية  ->  OpenRouter (آخر خطة).
قبل كده كان بيقفز لـ OpenRouter على طول من غير ما يجرّب موديل Gemini الاحتياطي.

=== حد أدنى للكلمات أخف مع OpenRouter (تعديل جديد) ===
الموديلات المجانية على OpenRouter أضعف في الطول العربي، فبنستخدم
OPENROUTER_MIN_WORDS (الافتراضي 500) بدل ACCEPTABLE_MIN_WORDS لما يكون
المزوّد الحالي OpenRouter.

=== تمييز نفاد الحصة اليومية (429/PerDay) عن أي خطأ عابر ===
بيوقف النموذج الحالي فورًا وينتقل للتالي.

⚠️ تنويه: الموديل مايقدرش "يتحقق" فعليًا من صحة أي حديث أو رواية —
حقول source_type/source_reference بتخلّي المراجعة البشرية ممكنة قبل النشر.
"""
import os
import re
import json
import sys
import time
import requests
from types import SimpleNamespace
from pathlib import Path

from google import genai

from arabic_guard import validate_narration
from google.genai import types

SCRIPT_DIR = Path(__file__).parent
PROMPT_PATH = SCRIPT_DIR.parent / "prompts" / "history_strategy_system_prompt.md"
OUTPUT_PATH = SCRIPT_DIR.parent / "state" / "current_episode.json"

# ─────────────────────────── الإعدادات ───────────────────────────

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODELS = [
    item.strip()
    for item in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",")
    if item.strip()
]
MODEL_CANDIDATES = list(dict.fromkeys([MODEL, *FALLBACK_MODELS]))
ACTIVE_MODEL_INDEX = 0
ACTIVE_MODEL = MODEL_CANDIDATES[ACTIVE_MODEL_INDEX]
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODELS = [
    item.strip() for item in os.getenv(
        "OPENROUTER_MODEL",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ).split(",") if item.strip()
]
OPENROUTER_MODEL = OPENROUTER_MODELS[0] if OPENROUTER_MODELS else ""
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "90"))
ACTIVE_PROVIDER = "gemini"
TEMPERATURE = 0.75

STORY_MAX_TOKENS = 8000
FINALIZE_MAX_TOKENS = 9000
# ⚠️ thinking_budget بياكل من نفس سقف max_output_tokens.
THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))

TARGET_WORDS = int(os.getenv("TARGET_WORDS", "900"))

# الحد الأدنى المقبول لـ Gemini. 0 = غير مفعّل.
ACCEPTABLE_MIN_WORDS = int(os.getenv("ACCEPTABLE_MIN_WORDS", os.getenv("MIN_NARRATION_WORDS", "0")))
# الحد الأدنى المقبول لما نكون على OpenRouter (موديلات مجانية أضعف في الطول).
OPENROUTER_MIN_WORDS = int(os.getenv("OPENROUTER_MIN_WORDS", "500"))

BUDGET_RETRIES = int(os.getenv("BUDGET_RETRIES", "2"))
LENGTH_ESCALATION = 1.5

# عدد جولات التوسعة للقصة المكتملة لكنها أقصر من الحد الأدنى.
MAX_EXPANSION_ROUNDS = int(os.getenv("MAX_EXPANSION_ROUNDS", "3"))
SINGLE_PASS_GENERATION = os.getenv("SINGLE_PASS_GENERATION", "false").lower() == "true"

# إعادات النداء الواحد عند 503/500. قللناها لـ 2 عشان منضيعش دقيقة ونص
# انتظار قبل التحويل للموديل الاحتياطي (3+6 = 9 ثواني بس).
TRANSIENT_RETRIES = int(os.getenv("TRANSIENT_RETRIES", "2"))
TRANSIENT_BACKOFF_BASE = 3  # ثواني

MAX_ATTEMPTS = int(os.getenv("MAX_FULL_ATTEMPTS", "2"))

HISTORY_LIMIT = 8
REGION_HISTORY_LIMIT = 6

EPISODE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "region": {"type": "string"},
        "narration": {"type": "string"},
        "visual_keywords": {"type": "array", "items": {"type": "string"}},
        "caption": {"type": "string"},
        "phonetic_hints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "phonetic": {"type": "string"},
                },
                "required": ["word", "phonetic"],
            },
        },
        "source_type": {"type": "string"},
        "source_reference": {"type": "string"},
    },
    "required": [
        "title", "hook", "region", "narration",
        "visual_keywords", "caption", "phonetic_hints",
        "source_type", "source_reference",
    ],
}
REQUIRED_KEYS = set(EPISODE_SCHEMA["required"])

FINALIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "visual_keywords": {"type": "array", "items": {"type": "string"}},
        "caption": {"type": "string"},
        "phonetic_hints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "phonetic": {"type": "string"},
                },
                "required": ["word", "phonetic"],
            },
        },
    },
    "required": ["title", "visual_keywords", "caption", "phonetic_hints"],
}

TASHKEEL_SCHEMA = {
    "type": "object",
    "properties": {"corrected_narration": {"type": "string"}},
    "required": ["corrected_narration"],
    "additionalProperties": False,
}

STORY_REQUIRED_FIELDS = ("hook", "region", "source_type", "source_reference", "narration")

DEFAULT_VISUAL_KEYWORDS = [
    "historical documentary",
    "archival documents",
    "old map",
    "museum artifact",
]


def to_gemini_schema(schema: dict) -> dict:
    """يحوّل JSON Schema عادي إلى صيغة Gemini (uppercase types)."""
    gemini_type = schema["type"].upper()
    result: dict = {"type": gemini_type}
    if gemini_type == "OBJECT":
        result["properties"] = {
            key: to_gemini_schema(value)
            for key, value in schema.get("properties", {}).items()
        }
        if "required" in schema:
            result["required"] = schema["required"]
    elif gemini_type == "ARRAY":
        result["items"] = to_gemini_schema(schema["items"])
    return result


class AttemptFailed(Exception):
    """فشل متوقّع داخل محاولة كاملة."""


class QuotaExhausted(Exception):
    """نفاد الحصة اليومية (أو تعذّر النموذج الحالي) — يستدعي التحويل للنموذج التالي."""


class ModelUnavailable(Exception):
    """النموذج غير موجود أو لم يعد متاحًا (404 NOT_FOUND)."""


# ─────────────────────────── مساعدات عامة ───────────────────────────

def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_history_field(field: str, limit: int) -> list[str]:
    history_path = SCRIPT_DIR.parent / "state" / "used_clips.json"
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    values = [h.get(field, "") for h in data.get("history", []) if h.get(field)]
    return values[-limit:]


def load_used_history(limit: int = HISTORY_LIMIT) -> list[str]:
    return _load_history_field("title", limit)


def load_used_regions(limit: int = REGION_HISTORY_LIMIT) -> list[str]:
    return _load_history_field("region", limit)


def load_used_hooks(limit: int = HISTORY_LIMIT) -> list[str]:
    return _load_history_field("hook", limit)


def count_words(text: str) -> int:
    return len(text.split())


def effective_min_words() -> int:
    """الحد الأدنى المطبّق فعليًا حسب المزوّد الحالي."""
    if ACTIVE_PROVIDER == "openrouter" and ACCEPTABLE_MIN_WORDS > 0:
        return min(ACCEPTABLE_MIN_WORDS, OPENROUTER_MIN_WORDS)
    return ACCEPTABLE_MIN_WORDS


_SENTENCE_ENDERS = (".", "!", "؟", "?", "…")
_TRAILING_WRAPPERS = ")\"'”’»」』﴾]"
_TRAILING_PAREN_GROUP = re.compile(r"[\(（][^()（）]*[\)）]\s*$")


def looks_truncated(narration: str) -> bool:
    stripped = narration.strip()
    if not stripped:
        return True

    match = _TRAILING_PAREN_GROUP.search(stripped)
    if match:
        without_paren = stripped[: match.start()].rstrip()
        if without_paren:
            stripped = without_paren

    trimmed = stripped.rstrip(_TRAILING_WRAPPERS)
    if not trimmed:
        return True
    return not trimmed.endswith(_SENTENCE_ENDERS)


def split_arabic_sentences(narration: str) -> list[str]:
    """نفس منطق split_sentences() في generate_voice.py بالضبط."""
    parts = re.split(r"(?<=[.!؟…])\s+", narration.strip())
    return [part.strip() for part in parts if part.strip()]


def count_arabic_sentences(narration: str) -> int:
    return len(split_arabic_sentences(narration))


def clean_continuation_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    cleaned = re.sub(r"^(NARRATION|narration)\s*:\s*", "", cleaned).strip()
    cleaned = cleaned.replace("**", "").replace("__", "").strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "”", "'"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _strip_label_markup(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "")
    cleaned = re.sub(r"(?m)^[ \t]*[#>\-*]+[ \t]*", "", cleaned)
    return cleaned


def parse_labeled_response(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    cleaned = _strip_label_markup(cleaned)
    labels = "HOOK|REGION|SOURCE_SOURCE_TYPE|SOURCE_TYPE|SOURCE_REFERENCE|NARRATION"
    pattern = re.compile(
        rf"(?:^|\n)\s*({labels})\s*:\s*(.*?)(?=\n\s*(?:{labels})\s*:|\Z)",
        re.DOTALL,
    )
    result: dict = {}
    for match in pattern.finditer(cleaned):
        key = match.group(1).strip().lower()
        if key == "source_source_type":
            key = "source_type"
            print("   ⚠️ تم تصحيح تسمية SOURCE_SOURCE_TYPE إلى SOURCE_TYPE تلقائيًا.")
        value = match.group(2).strip()
        result[key] = value
    return result


def try_parse_json_episode(text: str) -> dict | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    result: dict = {}
    for key in STORY_REQUIRED_FIELDS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result or None


def parse_story_reply(reply: str, attempt_label: str, step_label: str) -> dict:
    fields = parse_labeled_response(reply)
    if any(not fields.get(key, "").strip() for key in STORY_REQUIRED_FIELDS):
        json_fields = try_parse_json_episode(reply)
        if json_fields and all(json_fields.get(key, "").strip() for key in STORY_REQUIRED_FIELDS):
            print(f"   ℹ️ {attempt_label} | {step_label}: الرد جه JSON بدل الفورمات المسمّى — اتقبل عن طريق الخطة البديلة.")
            fields = json_fields

    missing = [key for key in STORY_REQUIRED_FIELDS if not fields.get(key, "").strip()]
    if missing:
        print(f"   🔎 رد {attempt_label} | {step_label} الخام (أول 500 حرف):\n{reply[:500]!r}")
        raise AttemptFailed(f"رد {step_label} ناقص حقل '{missing[0]}' أو فاضي (بكل الطرق المتاحة للتحليل)")

    return {
        "hook": fields["hook"].replace("**", "").replace("__", "").strip(),
        "region": fields["region"].replace("**", "").replace("__", "").strip(),
        "source_type": fields["source_type"].replace("**", "").replace("__", "").strip(),
        "source_reference": fields["source_reference"].replace("**", "").replace("__", "").strip(),
        "narration": clean_continuation_text(fields["narration"]),
    }


def ensure_complete_ending(
    client,
    history: list,
    narration: str,
    system_prompt: str,
    attempt_label: str,
) -> str:
    if not looks_truncated(narration):
        return narration
    reply, _ = call_model(
        client, history, build_finish_ending_prompt(),
        free_text_config, system_prompt, STORY_MAX_TOKENS,
        f"{attempt_label} | إكمال الخاتمة",
    )
    narration = narration + " " + clean_continuation_text(reply)
    print(f"   📝 بعد إكمال الخاتمة: {count_words(narration)} كلمة")
    return narration


CONTENT_RED_FLAGS = ("السيلينس", "الشهرات الجوية", "المحتلة بالدقيق", "البركان الثلجي")


def find_content_red_flag(text: str) -> str | None:
    plain = re.sub(r"[\u064B-\u065F\u0670]", "", text or "")
    return next((flag for flag in CONTENT_RED_FLAGS if flag in plain), None)


def normalize_phonetic_hints(value) -> list[dict[str, str]]:
    """Keep only usable pronunciation hints from an optional model field."""
    if not isinstance(value, list):
        return []
    normalized = []
    for hint in value:
        if not isinstance(hint, dict):
            continue
        word = str(hint.get("word", "")).strip()
        phonetic = str(hint.get("phonetic", "")).strip()
        if word and phonetic:
            normalized.append({"word": word, "phonetic": phonetic})
    return normalized


def validate_episode(episode: dict) -> str | None:
    if not REQUIRED_KEYS.issubset(episode.keys()):
        return f"الحلقة النهائية ناقصة حقول مطلوبة: {sorted(episode.keys())}"

    narration = str(episode.get("narration", "")).strip()
    arabic_issues = validate_narration(narration)
    if arabic_issues:
        return "بوابة العربية رفضت narration: " + "; ".join(f"{i.kind}: {i.sample}" for i in arabic_issues)
    red_flag = find_content_red_flag(narration)
    if red_flag:
        return f"النص يحتوي مصطلحًا علميًا مرفوضًا أو مختلقًا: {red_flag}"
    if looks_truncated(narration):
        return "نص narration النهائي شكله متقطوع (مش منتهي بعلامة ترقيم واضحة)"

    word_count = count_words(narration)
    min_words = effective_min_words()
    if min_words > 0 and word_count < min_words:
        return (
            f"نص narration النهائي قصير جدًا ({word_count} كلمة، "
            f"الحد الأدنى المقبول {min_words})"
        )

    if not episode.get("visual_keywords"):
        return "حقل visual_keywords فاضي"
    if not str(episode.get("hook", "")).strip():
        return "حقل hook فاضي"
    if not str(episode.get("source_type", "")).strip():
        return "حقل source_type فاضي — كل حلقة تاريخية لازم توثيق لنوع المصدر"
    if not str(episode.get("source_reference", "")).strip():
        return "حقل source_reference فاضي — كل حلقة تاريخية لازم مرجع دقيق"

    phonetic_hints = episode.get("phonetic_hints")
    if not isinstance(phonetic_hints, list):
        return "حقل phonetic_hints لازم يكون قائمة"
    for hint in phonetic_hints:
        if not isinstance(hint, dict):
            return "كل عنصر في phonetic_hints لازم يكون كائنًا فيه word وphonetic"
        if not str(hint.get("word", "")).strip() or not str(hint.get("phonetic", "")).strip():
            return "كل عنصر في phonetic_hints لازم يحتوي word وphonetic غير فارغين"

    return None


def log_usage(response, label: str) -> None:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return
    print(
        f"   🔢 {label} | مدخل: {usage.prompt_token_count} "
        f"| مخرج: {usage.candidates_token_count} "
        f"| إجمالي: {usage.total_token_count}"
    )


def _is_transient_error(exc: Exception) -> bool:
    if _is_daily_quota_exhausted(exc):
        return False
    text = str(exc).upper()
    transient_markers = ("503", "UNAVAILABLE", "500", "INTERNAL", "OVERLOADED", "DEADLINE_EXCEEDED", "TIMEOUT")
    return any(marker in text for marker in transient_markers)


class OpenRouterModels:
    def generate_content(self, *, model: str, contents, config):
        messages = []
        system = getattr(config, "system_instruction", None)
        if system:
            messages.append({"role": "system", "content": str(system)})
        for content in contents:
            text = "".join(getattr(part, "text", "") for part in (content.parts or []))
            messages.append({
                "role": "assistant" if content.role == "model" else "user",
                "content": text,
            })
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "temperature": getattr(config, "temperature", TEMPERATURE),
            "max_tokens": getattr(config, "max_output_tokens", STORY_MAX_TOKENS),
            "reasoning": {"effort": "none", "exclude": True},
        }
        if getattr(config, "response_mime_type", "") == "application/json":
            payload["response_format"] = {"type": "json_object"}
        errors = []
        for router_model in OPENROUTER_MODELS:
            payload["model"] = router_model
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/ahmedalsharqwi2-gif/islamic-reminder1",
                        "X-Title": "Islamic Reminder Auto Publisher",
                    },
                    json=payload,
                    timeout=OPENROUTER_TIMEOUT,
                )
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
                data = response.json()
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                content = message.get("content") or ""
                if isinstance(content, list):
                    content = "".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in content
                    )
                text = str(content).strip()
                if not text:
                    raise RuntimeError("empty answer content")
                print(f"🔀 OpenRouter: using model {router_model}")
                finish_reason = str(choice.get("finish_reason") or "STOP")
                usage = data.get("usage") or {}
                usage_metadata = SimpleNamespace(
                    prompt_token_count=usage.get("prompt_tokens", 0),
                    candidates_token_count=usage.get("completion_tokens", 0),
                    total_token_count=usage.get("total_tokens", 0),
                )
                return SimpleNamespace(
                    text=text,
                    usage_metadata=usage_metadata,
                    candidates=[SimpleNamespace(finish_reason=finish_reason)],
                )
            except Exception as exc:  # noqa: BLE001 - try the next router model
                errors.append(f"{router_model}: {exc}")
        raise RuntimeError("All OpenRouter models failed: " + " | ".join(errors))


class ProviderClient:
    def __init__(self, gemini_client):
        self._gemini_client = gemini_client
        self._openrouter_models = OpenRouterModels()

    @property
    def models(self):
        return self._openrouter_models if ACTIVE_PROVIDER == "openrouter" else self._gemini_client.models


def has_next_model() -> bool:
    """هل فيه موديل تاني نقدر نتحول له؟ (Gemini احتياطي أو OpenRouter)"""
    if ACTIVE_PROVIDER != "gemini":
        return False
    return ACTIVE_MODEL_INDEX + 1 < len(MODEL_CANDIDATES) or bool(OPENROUTER_API_KEY)


def switch_to_next_model() -> bool:
    """الترتيب: Gemini الأساسي -> موديلات Gemini الاحتياطية -> OpenRouter."""
    global ACTIVE_MODEL_INDEX, ACTIVE_MODEL, ACTIVE_PROVIDER
    if ACTIVE_PROVIDER == "gemini":
        if ACTIVE_MODEL_INDEX + 1 < len(MODEL_CANDIDATES):
            ACTIVE_MODEL_INDEX += 1
            ACTIVE_MODEL = MODEL_CANDIDATES[ACTIVE_MODEL_INDEX]
            print(f"🔁 انتقلت إلى موديل Gemini الاحتياطي: {ACTIVE_MODEL}")
            return True
        if OPENROUTER_API_KEY:
            ACTIVE_PROVIDER = "openrouter"
            ACTIVE_MODEL = OPENROUTER_MODEL
            print(f"🔁 انتقلت إلى OpenRouter كخطة احتياطية: {OPENROUTER_MODEL}")
            return True
    return False


def _is_model_unavailable(exc: Exception) -> bool:
    text = str(exc).upper()
    return "404" in text and "NOT_FOUND" in text


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    text = str(exc).upper()
    if "RESOURCE_EXHAUSTED" not in text and "429" not in text:
        return False
    return "PERDAY" in text.replace("_", "").replace(" ", "")


# ─────────────────────── إدارة المحادثة يدويًا ───────────────────────

def make_content(role: str, text: str) -> types.Content:
    return types.Content(role=role, parts=[types.Part(text=text)])


def free_text_config(system_prompt: str, budget: int) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=TEMPERATURE,
        max_output_tokens=budget,
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
    )


def finalize_json_config(system_prompt: str, budget: int) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=TEMPERATURE,
        max_output_tokens=budget,
        response_mime_type="application/json",
        response_schema=to_gemini_schema(FINALIZE_SCHEMA),
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
    )


def tashkeel_json_config(system_prompt: str, budget: int) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
        max_output_tokens=budget,
        response_mime_type="application/json",
        response_schema=to_gemini_schema(TASHKEEL_SCHEMA),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def call_model(
    client,
    history: list,
    prompt_text: str,
    config_builder,
    system_prompt: str,
    budget: int,
    label: str,
):
    """بيبعت prompt_text كدور مستخدم جديد فوق الـ history الحالي.
      - MAX_TOKENS: يرفع السقف ويعيد نفس النداء.
      - خطأ سيرفر مؤقت (503/500): backoff متصاعد، وبعد ما يخلص الإعادات
        بنتحوّل للموديل التالي (Gemini احتياطي ثم OpenRouter).
      - نفاد الحصة اليومية: تحويل فوري بدون إعادة."""
    attempt_budget = budget
    response = None
    finish_reason = ""
    for length_retry in range(BUDGET_RETRIES + 1):
        contents = history + [make_content("user", prompt_text)]
        last_exc: Exception | None = None
        response = None
        for transient_retry in range(TRANSIENT_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=ACTIVE_MODEL, contents=contents,
                    config=config_builder(system_prompt, attempt_budget),
                )
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if _is_daily_quota_exhausted(exc):
                    raise QuotaExhausted(
                        f"نفدت الحصة اليومية المجانية لموديل {ACTIVE_MODEL} أثناء {label} ({exc})"
                    ) from exc
                if _is_model_unavailable(exc):
                    raise ModelUnavailable(
                        f"الموديل {ACTIVE_MODEL} غير متاح أو لم يعد موجودًا أثناء {label} ({exc})"
                    ) from exc
                if _is_transient_error(exc) and transient_retry < TRANSIENT_RETRIES:
                    wait = TRANSIENT_BACKOFF_BASE * (2 ** transient_retry)
                    print(
                        f"   ⏳ {label}: خطأ مؤقت من السيرفر ({exc}) — "
                        f"إعادة المحاولة بعد {wait} ثانية..."
                    )
                    time.sleep(wait)
                    continue
                break

        if response is None:
            if has_next_model():
                raise QuotaExhausted(
                    f"تعذر إكمال نداء {ACTIVE_MODEL} في {label}؛ سيتم التحويل للموديل التالي ({last_exc})"
                ) from last_exc
            raise AttemptFailed(f"فشل استدعاء الـ API في {label} ({last_exc})") from last_exc

        log_usage(response, label)
        candidates = getattr(response, "candidates", None) or []
        finish_reason = str(candidates[0].finish_reason) if candidates else ""

        if "MAX_TOKENS" in finish_reason and length_retry < BUDGET_RETRIES:
            attempt_budget = int(attempt_budget * LENGTH_ESCALATION)
            print(f"   ⚠️ {label}: اتقطع بسبب حد التوكنز — هرفع السقف لـ {attempt_budget} وأعيد نفس النداء...")
            continue
        break

    if "SAFETY" in finish_reason or "PROHIBITED" in finish_reason or "BLOCKLIST" in finish_reason:
        raise AttemptFailed(f"الرد اتحجب في {label} (finish_reason={finish_reason})")

    reply_text = response.text or ""
    history.append(make_content("user", prompt_text))
    history.append(make_content("model", reply_text))
    return reply_text, finish_reason


# ─────────────────────────── نصوص البرومبت ───────────────────────────

_STORY_FORMAT_BLOCK = (
    "HOOK: <جملة الهوك>\n"
    "REGION: <وصف العصر/المكان>\n"
    "SOURCE_TYPE: <نوع المصدر (أرشيف/متحف/موسوعة/كتاب تاريخي موثوق)>\n"
    "SOURCE_REFERENCE: <المرجع الدقيق>\n"
    "NARRATION:\n<نص القصة الكاملة من الهوك للخاتمة>"
)


def build_story_prompt(
    recent_titles: list[str], recent_regions: list[str], recent_hooks: list[str],
    target_words: int,
) -> str:
    message = (
        "اكتب حلقة جديدة تمامًا — قصة تاريخية كاملة من "
        "الهوك للتمهيد للتصعيد للذروة للخاتمة، في رد واحد.\n\n"
        "⚠️ نطاق القناة: اختر قصة تاريخية موثقة، ويُرحب بقصص الفتوحات الإسلامية والغزوات والمعارك والانتصارات الإسلامية عبر العصور، إلى جانب القصص العسكرية والإنسانية العالمية. عند اختيار واقعة إسلامية، لا تختلق تفاصيل أو حوارًا، واذكر مصدرًا تاريخيًا محددًا، واحترم الشخصيات والمذاهب وتجنب التحقير والتحريض.\n\n"
        "⚠️ اللغة: narration بالكامل باللغة العربية الفصحى المبسّطة "
        "(Modern Standard Arabic) فقط، ممنوع أي لهجة عامية. شكّل النص كاملًا "
        "لتوجيه النطق، وراجع مطابقة الضمائر والأفعال والتذكير والتأنيث قبل الرد.\n\n"
        "⚠️ التوثيق التاريخي: اختر واقعة قابلة للمراجعة من أرشيف أو متحف "
        "أو موسوعة أو كتاب تاريخي موثوق. ممنوع اختلاق أي حوار أو تفصيلة أو "
        "اسم أو رقم أو نتيجة. إذا اختلفت الروايات، اذكر ذلك بوضوح ولا تقدم "
        "المختلف عليه كحقيقة قطعية.\n\n"
        "⚠️ عدم التكرار: ممنوع نفس الواقعة اللي اتستخدمت في حلقة سابقة "
        "حتى بعنوان أو صياغة مختلفة تمامًا. راجع الهوكات تحت (بيوصفوا "
        "الواقعة نفسها بدقة أكتر من العنوان) — لو الواقعة في بالك بتوصف "
        "نفس حادثة أي هوك منهم، ارفضها واختار واقعة مختلفة.\n\n"
        "⚠️ الهوك: أول جملة في narration لازم تكون هي نفسها حقل hook "
        "(أو صياغة قريبة جدًا منه) — مشوّقة ومباشرة تخلق فضول فوري (سؤال "
        "مثير، أو تفصيلة تاريخية مدهشة وحقيقية، أو مشهد لحظة الذروة قبل "
        "ما تُروى)، من غير أي تهويل يخالف الأمانة التاريخية.\n\n"
        "⚠️ التنويع: اختار عصرًا/شخصية محورية مختلفة عن اللي اتذكرت تحت.\n\n"
        f"⚠️ الطول: اكتب narration كاملة (تمهيد+تصعيد+ذروة+خاتمة) في حدود "
        f"{target_words} كلمة عربية تقريبًا. لو المصدر مش فيه تفاصيل كافية "
        "توصلك للرقم ده بالظبط، اقفل القصة بخاتمة حقيقية بدل ما تحشو "
        "تفاصيل غير موثقة — القصة الكاملة والمتماسكة أهم من الوصول لرقم "
        "كلمات بعينه. لازم آخر جملة تنتهي بعلامة ترقيم واضحة (نقطة أو "
        "علامة تعجب أو علامة استفهام أو علامات حذف) تدل فعليًا على اكتمال "
        "القصة.\n\n"
        "⚠️ مهم جدًا بخصوص آخر حرف في ردك: إذا انتهت القصة باقتباس أو "
        "مرجع بين قوسين، ضع نقطة \".\" فورًا بعد القوس الختامي مباشرة (من "
        "غير مسافة قبلها). آخر حرف حرفيًا في ردك يجب أن يكون واحدًا من: "
        "نقطة (.) أو علامة تعجب (!) أو علامة استفهام (؟) — ولا شيء بعده.\n\n"
        "⚠️ الفورمات — التزم بيه حرفيًا: ردك كله لازم يكون نص عادي "
        "(plain text) وليس JSON، بالشكل بالضبط تحت. اكتب كل تسمية "
        "حرفيًا بالرموز الكبيرة كما هي (HOOK: بدون أي ترجمة "
        "أو تغيير أو زخرفة markdown حواليها، ومن غير أقواس {} أو علامات "
        "اقتباس \" حوالين القيم)، كل تسمية في بداية سطر جديد، ومفيش أي "
        "نص أو مقدمة أو أسوار كود ```json أو تعليق خارج الحقول دي:\n\n"
        f"{_STORY_FORMAT_BLOCK}"
    )
    if recent_titles:
        message += "\n\nالعناوين اللي اتستخدمت قبل كده (تجنب أي تشابه معاها):\n- " + "\n- ".join(recent_titles)
    if recent_hooks:
        message += (
            "\n\nالهوكات (ومن ثم الوقائع الفعلية) اللي اتستخدمت قبل كده — "
            "ممنوع اختيار نفس الواقعة حتى بهوك أو عنوان مختلف:\n- " + "\n- ".join(recent_hooks)
        )
    if recent_regions:
        message += "\n\nالعصور/الأماكن اللي اتستخدمت قبل كده (اختار عصرًا مختلفًا):\n- " + "\n- ".join(recent_regions)
    return message


def build_expand_story_prompt(current_word_count: int, target_words: int, min_words: int = 0) -> str:
    """نداء توسيع: بيحدد بالظبط كام كلمة ناقصة عشان الموديل الضعيف مايعيدش
    نفس الطول. بيطلب إعادة كتابة القصة كاملة بدون حذف أي جزء موجود."""
    floor = max(min_words, int(target_words * 0.75))
    missing = max(floor - current_word_count, 0) + 100
    return (
        f"القصة الحالية {current_word_count} كلمة فقط، وهذا قصير. "
        f"الحد الأدنى المطلوب {floor} كلمة والهدف حوالي {target_words}. "
        "أعد كتابة نفس القصة كاملة من جديد (نفس الواقعة ونفس الهوك ونفس "
        f"المصدر) مع إضافة حوالي {missing} كلمة من تفاصيل حسّية ووصفية "
        "وسياقية واردة في المصدر نفسه (الأصوات، المشاعر، المكان والزمان، "
        "ردود الأفعال، خلفية الأحداث). لا تحذف أو تختصر أي جزء موجود، "
        "ولا تخترع أحداثًا أو تفاصيل غير موثقة. "
        f"ممنوع أن يقل الناتج عن {floor} كلمة، وتأكد أن آخر حرف نقطة أو "
        "علامة تعجب أو استفهام. "
        "اكتب الرد بنفس الفورمات بالضبط من الأول (نص عادي وليس JSON):\n\n"
        f"{_STORY_FORMAT_BLOCK}"
    )


def build_finish_ending_prompt() -> str:
    return (
        "النص اتقطع قبل ما يوصل لخاتمة حقيقية. اكتب دلوقتي فقط الجملة "
        "أو الجمل الختامية اللي تقفل القصة بعبرة أو حكمة واضحة مبنية "
        "على المصدر نفسه، من غير أي حدث جديد ومن غير تكرار أي جملة "
        "سابقة. لا تضف مصدراً جديداً في هذا الرد تحديداً (تفاديًا لأي "
        "التباس في علامة النهاية) — اكتب جملة ختامية عادية بأسلوبك، "
        "وتأكد إن آخر حرف حرفيًا في ردك هو نقطة (.) أو علامة تعجب (!) "
        "أو علامة استفهام (؟) مباشرة، من غير أي قوس أو علامة اقتباس أو "
        "أي حرف آخر بعدها."
    )


def build_finalize_prompt(final_narration: str, recent_titles: list[str]) -> str:
    sentences = split_arabic_sentences(final_narration)
    numbered_sentences = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
    sentence_count = len(sentences)

    message = (
        "هذا هو نص narration النهائي والمعتمد بالكامل للحلقة. لا تُعدّل "
        "فيه أو تُعِد صياغته أو تختصره أو تُطِله بأي شكل — دورك الآن بس "
        "إنك تبني باقي حقول الحلقة بناءً عليه:\n\n"
        f"--- بداية narration النهائي ---\n{final_narration}\n"
        "--- نهاية narration النهائي ---\n\n"
        f"⚠️ narration أعلاه مقسّم يدويًا وبشكل نهائي إلى {sentence_count} "
        "جملة مرقّمة بالضبط كما هو موضّح تحت. هذا التقسيم ثابت ولن "
        "يتغير مهما كان رأيك في التقسيم اللغوي الصحيح:\n\n"
        f"{numbered_sentences}\n\n"
        "المطلوب منك الآن:\n\n"
        "1) title: عنوان جذّاب ومختصر للحلقة، غير مكرر مع العناوين "
        "السابقة المذكورة تحت.\n\n"
        "2) visual_keywords: كلمات بحث بصرية (بالإنجليزية) "
        "ملموسة ومحددة مذكورة فعليًا في narration أعلاه، وممنوع أي كلمة "
        "بحث تنتج لقطة تجسد أشخاصًا حقيقيين أو مشاهد غير مذكورة في القصة. "
        "استخدم مواقع وأدوات ومخطوطات وخرائط ومناظر طبيعية وأشخاصًا مجهولي "
        "الهوية عند الحاجة.\n\n"
        "3) caption: وصف قصير جذّاب للفيديو (لمنصات التواصل).\n\n"
        "4) phonetic_hints: تلميحات نطق للكلمات الصعبة أو غير الشائعة "
        "الواردة في narration (لو وجدت). يجب أن تكون قائمة كائنات فقط، "
        "وكل كائن بهذا الشكل: {\"word\": \"الكلمة كما وردت\", "
        "\"phonetic\": \"نفس الكلمة مع التشكيل\"}. إذا لم توجد كلمات "
        "صعبة فأعد قائمة فارغة []، ولا تضع كلمات نصية مباشرة داخل القائمة.\n\n"
        "المطلوب فيديو وصوت وترجمة عربية فقط. "
        "اكتب الرد بصيغة JSON فقط حسب الـ schema المحدد، من غير أي نص "
        "خارج الـ JSON."
    )
    if recent_titles:
        message += "\n\nالعناوين اللي اتستخدمت قبل كده (تجنب أي تشابه معاها):\n- " + "\n- ".join(recent_titles)
    return message


TASHKEEL_SYSTEM_PROMPT = (
    "أنت مدقق لغوي عربي متخصص في ضبط نصوص النطق. صحح النص المرسل دون حذف "
    "أو إضافة معلومة أو تغيير ترتيب الكلمات. راجع الفاعل والمفعول وعائد كل ضمير، "
    "وطابق الأفعال مع الفاعل في التذكير والتأنيث والإفراد والتثنية والجمع، واضبط "
    "زمن الفعل. أضف التشكيل الكامل للكلمات، خصوصًا الأفعال والضمائر وأواخر الكلمات "
    "والكلمات التي تحتمل قراءتين. حافظ على علامات الوقف، وأعد JSON فقط بالمفتاح "
    "corrected_narration."
)


def _word_signature(text: str) -> list[str]:
    plain = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    return re.findall(r"[\u0621-\u064A\u0671]+", plain)


def proofread_narration_for_tts(
    client,
    history: list,
    narration: str,
    attempt_label: str,
) -> str:
    prompt = (
        "راجع النص التالي للنطق العربي. لا تغيّر الكلمات أو المعلومات أو ترتيبها؛ "
        "أصلح التشكيل والنحو فقط. إذا كان الضمير أو الفعل ملتبسًا فاضبطه بما يوافق "
        "السياق. النص:\n\n" + narration
    )
    reply, _ = call_model(
        client, history, prompt, tashkeel_json_config, TASHKEEL_SYSTEM_PROMPT,
        max(FINALIZE_MAX_TOKENS, count_words(narration) * 8),
        f"{attempt_label} | التدقيق النحوي والتشكيل",
    )
    try:
        corrected = str(json.loads(reply).get("corrected_narration", "")).strip()
    except (json.JSONDecodeError, AttributeError) as exc:
        raise AttemptFailed("رد التدقيق النحوي ليس JSON صالحًا") from exc
    original_words = _word_signature(narration)
    corrected_words = _word_signature(corrected)
    if not corrected or len(corrected_words) < max(20, int(len(original_words) * 0.85)):
        raise AttemptFailed("التدقيق النحوي أعاد نصًا فارغًا أو مختصرًا بشدة")
    if corrected_words != original_words:
        print("   ⚠️ التدقيق غيّر بعض صيغ الكلمات؛ تم قبول التصحيح لأنه حافظ على معظم النص")
    return corrected


# ─────────────────────────── تنفيذ محاولة واحدة ───────────────────────────

def run_single_attempt(
    client,
    system_prompt: str,
    recent_titles: list[str],
    recent_regions: list[str],
    recent_hooks: list[str],
    target_words: int,
    attempt_label: str,
) -> dict:
    history: list = []

    # ── نداء القصة الكاملة ──
    reply, _ = call_model(
        client, history,
        build_story_prompt(recent_titles, recent_regions, recent_hooks, target_words),
        free_text_config, system_prompt, STORY_MAX_TOKENS,
        f"{attempt_label} | القصة",
    )
    story = parse_story_reply(reply, attempt_label, "القصة")
    hook, region = story["hook"], story["region"]
    source_type, source_reference = story["source_type"], story["source_reference"]
    narration = story["narration"]

    print(f"   📝 القصة: {count_words(narration)} كلمة (هدف تقريبي {target_words})")

    if SINGLE_PASS_GENERATION:
        if looks_truncated(narration):
            raise AttemptFailed("النص ذو المرور الواحد انتهى قبل خاتمة واضحة")
        actual_words = count_words(narration)
        if actual_words < target_words:
            print(
                f"   ⚠️ النص المكتمل أقصر من الهدف ({actual_words}/{target_words} كلمة)؛ "
                "سيُقبل بدون نداء توسعة لتوفير التوكنز"
            )
        episode = {
            "title": hook[:80].strip(" .؟!،"),
            "hook": hook,
            "region": region,
            "narration": narration,
            "visual_keywords": DEFAULT_VISUAL_KEYWORDS.copy(),
            "caption": hook,
            "phonetic_hints": [],
            "source_type": source_type,
            "source_reference": source_reference,
        }
        error = validate_episode(episode)
        if error:
            raise AttemptFailed(error)
        print("   ⚡ وضع المرور الواحد: تم تخطي التوسيع والتدقيق وfinalize لتوفير التوكنز")
        return episode

    narration = ensure_complete_ending(client, history, narration, system_prompt, attempt_label)
    if looks_truncated(narration):
        raise AttemptFailed("narration لسه متقطوعة بعد محاولة إكمال الخاتمة (مش منتهية بعلامة ترقيم واضحة)")

    # ── جولات التوسيع: بنحتفظ دايمًا بأطول نسخة مكتملة ──
    min_words = effective_min_words()
    for expansion_round in range(1, MAX_EXPANSION_ROUNDS + 1):
        if count_words(narration) >= min_words:
            break
        current_count = count_words(narration)
        print(
            f"   ℹ️ الطول ({current_count} كلمة) أقل من الحد الأدنى المقبول "
            f"({min_words}) — توسعة {expansion_round}/{MAX_EXPANSION_ROUNDS}."
        )
        reply, _ = call_model(
            client, history,
            build_expand_story_prompt(current_count, target_words, min_words),
            free_text_config, system_prompt, STORY_MAX_TOKENS,
            f"{attempt_label} | توسيع القصة {expansion_round}",
        )
        expanded = parse_story_reply(reply, attempt_label, "توسيع القصة")
        new_narration = ensure_complete_ending(
            client, history, expanded["narration"], system_prompt, attempt_label
        )
        # نقبل النسخة الجديدة بس لو أطول ومكتملة.
        if count_words(new_narration) > current_count and not looks_truncated(new_narration):
            hook, region = expanded["hook"], expanded["region"]
            source_type, source_reference = expanded["source_type"], expanded["source_reference"]
            narration = new_narration
        else:
            print("   ⚠️ نسخة التوسيع مش أطول أو مش مكتملة — الاحتفاظ بالنسخة السابقة.")
        print(f"   📝 بعد التوسيع {expansion_round}: {count_words(narration)} كلمة")

    final_word_count = count_words(narration)
    if min_words > 0 and final_word_count < min_words:
        raise AttemptFailed(
            f"narration قصيرة جدًا حتى بعد التوسيع ({final_word_count} كلمة، "
            f"الحد الأدنى المقبول {min_words})"
        )
    if final_word_count < target_words:
        print(
            f"   ℹ️ الطول ({final_word_count} كلمة) أقل من الهدف "
            f"({target_words}) لكنه فوق الحد الأدنى المقبول — هيتقبل من غير إعادة."
        )

    narration = proofread_narration_for_tts(client, history, narration, attempt_label)

    # ── نداء finalize ──
    try:
        reply, _ = call_model(
            client, history, build_finalize_prompt(narration, recent_titles),
            finalize_json_config, system_prompt, FINALIZE_MAX_TOKENS,
            f"{attempt_label} | finalize",
        )
        finalize_data = json.loads(reply)
    except (QuotaExhausted, ModelUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001 - metadata is optional, narration is not
        print(f"   ⚠️ تعذر finalize الاختياري ({exc})؛ استخدام بيانات الحلقة الأساسية")
        finalize_data = {
            "title": hook[:80].strip(" .؟!،"),
            "visual_keywords": DEFAULT_VISUAL_KEYWORDS.copy(),
            "caption": hook,
            "phonetic_hints": [],
        }

    visual_keywords = finalize_data.get("visual_keywords")
    if not isinstance(visual_keywords, list):
        visual_keywords = []
    visual_keywords = [str(item).strip() for item in visual_keywords if str(item).strip()]
    if not visual_keywords:
        print("   ⚠️ finalize أعاد visual_keywords فارغة؛ استخدام كلمات بحث احتياطية")
        visual_keywords = DEFAULT_VISUAL_KEYWORDS.copy()

    episode = {
        "title": finalize_data.get("title", "") or hook[:80].strip(" .؟!،"),
        "hook": hook,
        "region": region,
        "narration": narration,
        "visual_keywords": visual_keywords,
        "caption": finalize_data.get("caption", ""),
        "phonetic_hints": normalize_phonetic_hints(finalize_data.get("phonetic_hints", [])),
        "source_type": source_type,
        "source_reference": source_reference,
    }

    error = validate_episode(episode)
    if error:
        raise AttemptFailed(error)

    return episode


def generate_episode() -> dict:
    global ACTIVE_PROVIDER, ACTIVE_MODEL
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key and not OPENROUTER_API_KEY:
        sys.exit("خطأ: أضف GEMINI_API_KEY أو OPENROUTER_API_KEY إلى GitHub Secrets")
    if api_key:
        client = ProviderClient(genai.Client(api_key=api_key))
    else:
        ACTIVE_PROVIDER = "openrouter"
        ACTIVE_MODEL = OPENROUTER_MODEL
        client = ProviderClient(None)
    system_prompt = load_system_prompt()
    recent_titles = load_used_history()
    recent_regions = load_used_regions()
    recent_hooks = load_used_hooks()

    print(
        f"🕌 المزود الأساسي: {ACTIVE_PROVIDER} | Gemini: {MODEL} "
        f"(احتياطي: {FALLBACK_MODELS or 'لا يوجد'}) | OpenRouter: {OPENROUTER_MODEL} | "
        f"thinking_budget: {THINKING_BUDGET} | "
        f"هدف الطول التقريبي: {TARGET_WORDS} كلمة | "
        f"الحد الأدنى: {ACCEPTABLE_MIN_WORDS or 'غير محدد'} "
        f"(OpenRouter: {OPENROUTER_MIN_WORDS}) | جولات التوسيع: {MAX_EXPANSION_ROUNDS}"
    )

    last_error = "لم تبدأ أي محاولة"
    quota_errors: list[str] = []
    # كل تحويل بين موديلات بياخد محاولة كاملة إضافية، عشان التحويل ما ياكلش
    # من محاولات التوليد الأصلية.
    extra = 0
    if api_key:
        extra += len(MODEL_CANDIDATES) - 1
        if OPENROUTER_API_KEY:
            extra += 1
    attempt_limit = MAX_ATTEMPTS + extra
    for attempt in range(1, attempt_limit + 1):
        print(f"\n===== محاولة كاملة {attempt}/{attempt_limit} (محادثة جديدة) =====")
        try:
            return run_single_attempt(
                client, system_prompt, recent_titles, recent_regions, recent_hooks,
                TARGET_WORDS, f"محاولة {attempt}",
            )
        except (QuotaExhausted, ModelUnavailable) as exc:
            last_error = str(exc)
            if isinstance(exc, QuotaExhausted):
                quota_errors.append(last_error)
            if switch_to_next_model():
                print(
                    f"⚠️ {exc}\n"
                    f"🔁 الموديل الحالي دلوقتي: {ACTIVE_MODEL} ({ACTIVE_PROVIDER}). "
                    "سيُعاد تشغيل المحاولة الكاملة من البداية.",
                    flush=True,
                )
                continue
            details = "\n".join(f"- {item}" for item in quota_errors)
            sys.exit(
                f"❌ توقف: لا يوجد نموذج متاح في القائمة الحالية.\n"
                f"النماذج التي جُرّبت: {MODEL_CANDIDATES}\n"
                f"آخر خطأ: {last_error}\n"
                + (f"تفاصيل:\n{details}\n" if details else "")
                + "الحل: انتظر تجدد الحصة/استقرار السيرفر، أو حدّث GEMINI_FALLBACK_MODELS "
                "إلى نموذج متاح فعليًا."
            )
        except AttemptFailed as exc:
            last_error = str(exc)
            print(f"⚠️ فشلت المحاولة الكاملة {attempt}/{attempt_limit}: {last_error}")
        except Exception as exc:  # noqa: BLE001
            last_error = f"خطأ غير متوقع: {exc}"
            print(f"⚠️ فشلت المحاولة الكاملة {attempt}/{attempt_limit}: {last_error}")

    sys.exit(f"❌ فشل توليد حلقة سليمة بعد {attempt_limit} محاولات كاملة. آخر خطأ: {last_error}")


if __name__ == "__main__":
    episode = generate_episode()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ اتكتبت الحلقة: {episode['title']}")
    print(f"   العصر/المكان: {episode.get('region', 'غير محدد')}")
    print(f"   عدد كلمات narration: {count_words(episode.get('narration', ''))}")
    print(f"   الهوك: {episode.get('hook', '')[:80]}")
    print(f"   المصدر: {episode.get('source_type', '')} — {episode.get('source_reference', '')}")
    print(f"   كلمات البحث: {episode['visual_keywords']}")
    print(f"   تلميحات النطق: {episode.get('phonetic_hints', [])}")
