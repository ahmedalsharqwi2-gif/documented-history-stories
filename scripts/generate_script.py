"""
generate_script.py
يستدعي Gemini API عشان يولّد سيناريو القصة الدينية/التاريخية الإسلامية +
الترجمة الإنجليزية الموازية + كلمات البحث البصرية + مرجع التوثيق الشرعي.

=== نداء واحد للقصة كاملة + قبول طول "مقارب" بدل الإجبار ===
بدل تقسيم narration لمرحلتين مع توسيعات (كان بيرفع عدد نداءات الـ API
لكل محاولة كاملة لغاية 5-10 نداء، وبالتالي يكبّر احتمال إن أي نداء وسط
السلسلة يقابل مشكلة عرضية ويفشّل التشغيلة كلها)، دلوقتي:
  1) نطلب من الموديل يكتب القصة *كاملة* (تمهيد+تصعيد+ذروة+خاتمة) في
     نداء واحد بس، بهدف طول تقريبي (مش صارم) حوالي TARGET_WORDS كلمة.
  2) لو القصة طلعت "قصيرة شوية" عن الهدف لكنها متماسكة ومنتهية بخاتمة
     حقيقية — بنقبلها زي ما هي، من غير إعادة أو توسيع. الفشل الحقيقي
     الوحيد بخصوص الطول هو قصة قصيرة *جدًا* (أقل من ACCEPTABLE_MIN_WORDS).
  3) لو النداء اتقطع قبل خاتمة حقيقية، نداء واحد بس "إكمال خاتمة" (مش
     حلقة توسيعات).
النتيجة: نداءان بس في الغالب لكل محاولة كاملة (القصة + finalize).

=== إعادة محاولة تلقائية عند أخطاء السيرفر المؤقتة (503 وما شابه) ===
أي نداء API ممكن يفشل بسبب ضغط مؤقت على سيرفرات Gemini (503
UNAVAILABLE) أو مشاكل شبكة عابرة (500 INTERNAL). بنميّز هذه الأخطاء
(_is_transient_error) ونعيد نفس النداء بعد انتظار متصاعد (exponential
backoff) لغاية TRANSIENT_RETRIES مرة، قبل ما نعتبرها فشل حقيقي.

=== تعديل جديد: تمييز نفاد الحصة اليومية (429 RESOURCE_EXHAUSTED/PerDay) عن أي خطأ عابر ===
ظهر فعليًا في التشغيل: محاولة كاملة أولى فشلت (رد الموديل ناقص تنسيق)،
وبعدين المحاولة الكاملة الثانية ضربت 429 RESOURCE_EXHAUSTED بسبب انتهاء
الحصة اليومية المجانية (quotaId: GenerateRequestsPerDayPerProjectPerModel-
FreeTier). ده خطأ مختلف جوهريًا عن 503/500 العابر: الحصة اليومية مش
هترجع في ثواني ولا حتى دقايق، فإعادة المحاولة (سواء على مستوى النداء أو
على مستوى محاولة كاملة جديدة) مالهاش أي معنى ومجرد إضاعة وقت. دلوقتي
بنكتشف الحالة دي تحديدًا (_is_daily_quota_exhausted) ونرفع استثناء
منفصل (QuotaExhausted) بيوقف التشغيلة بالكامل فورًا من غير ما يستهلك
باقي المحاولات الكاملة (MAX_ATTEMPTS) على الفاضي.

=== تعديل جديد: تسجيل الرد الخام عند فشل تحليل الحقول ===
لو رد نداء القصة جه "ناقص حقل" (مش متبع لفورمات HOOK:/REGION:/... اللي
اتطلب)، كنا قبل كده بنرفض الرد ونعتبره فشل من غير أي طريقة نعرف بيها
*ليه* فشل التحليل (تنسيق مختلف؟ تسمية بلغة تانية؟ ناقص فعلاً؟). دلوقتي
بنطبع أول جزء من النص الخام في اللوج وقت الفشل عشان يبقى قابل للتشخيص.
كمان أضفنا جملة توضيح صريحة في نص البرومبت نفسه إن التسميات لازم تفضل
بالإنجليزية بالحروف الكبيرة زي ما هي بالظبط، تقليلاً لاحتمال حصول
المشكلة دي من الأول.

=== ملخص التعديل الأسبق: الانتقال من Groq إلى Gemini ===
بتستخدم Google Gemini عبر حزمة "google-genai" الرسمية (pip install -U
google-genai). مفتاح البيئة GEMINI_API_KEY، والـ JSON Schema بتتبع صيغة
Gemini (uppercase types) عبر to_gemini_schema()، والتحكم في مساحة
التفكير عبر GEMINI_THINKING_BUDGET (ThinkingConfig).

⚠️ تنويه مهم وصادق (باقٍ كما هو مع أي مزوّد API): الموديل مايقدرش
"يتحقق" فعليًا من صحة أي حديث أو نسبة رواية بشكل قاطع — مفيش أداة بحث
أو مطابقة أسانيد جوه السكريبت. حقل "source_type"/"source_reference"
بيجبر الموديل يصرّح بمرجعه تحديدًا لكل حلقة، عشان يبقى قابلاً للمراجعة
البشرية قبل النشر.
"""
import os
import re
import json
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

SCRIPT_DIR = Path(__file__).parent
PROMPT_PATH = SCRIPT_DIR.parent / "prompts" / "islamic_history_system_prompt.md"
OUTPUT_PATH = SCRIPT_DIR.parent / "state" / "current_episode.json"

# ─────────────────────────── الإعدادات ───────────────────────────

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE = 0.75

# سقف التوكنز لنداء القصة الكاملة (نداء واحد بس بيكتب narration من الهوك
# لحد الخاتمة). سخي عشان القصة كلها + مساحة تفكير في نفس النداء.
STORY_MAX_TOKENS = 8000
# سقف نداء finalize (JSON فيه narration_en كمصفوفة بعدد جمل القصة كاملة
# + باقي الحقول) — قصص طويلة (800+ كلمة) ممكن تبقى 50-80 جملة.
FINALIZE_MAX_TOKENS = 9000
# ⚠️ مهم: thinking_budget بياكل من نفس سقف max_output_tokens بتاع
# النداء (مش سقف منفصل). خليه منخفض (0-512) إلا لو محتاج تفكير أعمق.
THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))

# === فيديو كامل فوق 5 دقايق، ريل واحد بس (مقتطف من أول الفيديو) ===
# النسبة الموثقة تجريبيًا لسرعة نطق edge-tts (بعد وقفات الجمل): 300
# كلمة ≈ 94-150 ثانية. الهدف هنا تقريبي (مش صارم) — انظر ACCEPTABLE_MIN_WORDS
# تحت للحد الأدنى المقبول فعليًا.
TARGET_WORDS = int(os.getenv("TARGET_WORDS", "900"))

# الحد الأدنى المقبول فعليًا للطول النهائي. ده مش هدف نطمح له — ده خط
# دفاع بس ضد قصة قصيرة *جدًا* (علامة على مشكلة حقيقية في التوليد، زي
# قفل مبكر جدًا أو رفض جزئي). أي طول فوق الرقم ده بيتقبل زي ما هو من
# غير أي محاولة توسيع أو إعادة، حتى لو أقل من TARGET_WORDS.
ACCEPTABLE_MIN_WORDS = int(os.getenv("ACCEPTABLE_MIN_WORDS", "650"))

# لو نداء اتقطع فعليًا بسبب حد التوكنز (MAX_TOKENS)، نرفع السقف ونعيد
# نفس النداء (مش المحاولة كلها).
BUDGET_RETRIES = 2
LENGTH_ESCALATION = 1.5

# عدد إعادات المحاولة لنفس النداء عند خطأ سيرفر مؤقت (503 UNAVAILABLE،
# 500 INTERNAL، إلخ) قبل ما نعتبره فشل حقيقي. الانتظار بيتصاعد
# (TRANSIENT_BACKOFF_BASE * 2^المحاولة) عشان نديله فرصة الضغط يقل.
# ⚠️ ده منفصل تمامًا عن نفاد الحصة اليومية (429/PerDay) — شوف
# _is_daily_quota_exhausted تحت، ده بيوقف التشغيلة فورًا من غير إعادة.
TRANSIENT_RETRIES = 3
TRANSIENT_BACKOFF_BASE = 3  # ثواني

# بما إن كل محاولة كاملة بقت تستهلك نداءين (نادرًا 3) بدل 5-10، ممكن
# نسمح بمحاولة كاملة تانية من غير ما نخاطر باستهلاك الحصة اليومية كلها.
MAX_ATTEMPTS = int(os.getenv("MAX_FULL_ATTEMPTS", "2"))

HISTORY_LIMIT = 8
REGION_HISTORY_LIMIT = 6

# ⚠️ لو السكريبت اللي بيجيب الفيديوهات من Pexels بيتوقع visual_keywords
# كـ string مفصول بفواصل بدل list، غيّر "type": "array" لـ "type": "string"
# في الـ schema تحت (to_gemini_schema() هتحوّلها تلقائيًا لصيغة Gemini
# الصحيحة برضو).
EPISODE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "region": {"type": "string"},
        "narration": {"type": "string"},
        "narration_en": {"type": "array", "items": {"type": "string"}},
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
        "title", "hook", "region", "narration", "narration_en",
        "visual_keywords", "caption", "phonetic_hints",
        "source_type", "source_reference",
    ],
}
REQUIRED_KEYS = set(EPISODE_SCHEMA["required"])

# schema نداء finalize بس — من غير narration (بنحطها إحنا يدويًا من نص
# القصة النهائي) ومن غير hook/region/source_type/source_reference (بناخدها
# زي ما هي من رد نداء القصة، بدل ما نطلب من الموديل يعيدها تاني في
# الآخر، عشان نضمن تطابقها ومنعطيش الموديل فرصة يغيّرها لاحقًا).
FINALIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "narration_en": {"type": "array", "items": {"type": "string"}},
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
    "required": ["title", "narration_en", "visual_keywords", "caption", "phonetic_hints"],
}


def to_gemini_schema(schema: dict) -> dict:
    """يحوّل تعريف JSON Schema عادي (lowercase types) إلى صيغة Gemini
    (uppercase types، بدون additionalProperties)."""
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
    """فشل متوقّع داخل محاولة كاملة (مش خطأ برمجي) — بيدّي سبب واضح
    ويخلي الحلقة الخارجية تنتقل لمحاولة جديدة (محادثة من الصفر)."""


class QuotaExhausted(Exception):
    """نفاد الحصة اليومية المجانية بشكل نهائي (429 RESOURCE_EXHAUSTED +
    quotaId يحتوي PerDay). مختلف عن AttemptFailed: بيوقف التشغيلة كلها
    فورًا (مش بس المحاولة الحالية)، لأن إعادة المحاولة — سواء على مستوى
    النداء أو على مستوى محاولة كاملة جديدة — مالهاش أي معنى؛ الحصة مش
    هترجع في ثواني ولا حتى دقايق."""


# ─────────────────────────── مساعدات عامة ───────────────────────────

def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_history_field(field: str, limit: int) -> list[str]:
    """مساعد عام لقراءة آخر N قيمة لحقل معيّن (title/region/hook) من
    used_clips.json. آمن على الملفات القديمة اللي مفيهاش الحقل أصلاً."""
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


# علامات نهاية الجملة "الحقيقية" (بيتم البحث عنها بعد تجاهل أي أقواس/
# علامات اقتباس ختامية زايدة بعدها — انظر looks_truncated تحت).
_SENTENCE_ENDERS = (".", "!", "؟", "?", "…")
# أقواس وعلامات اقتباس شائعة ممكن الموديل يقفل بيها الجملة (نهاية
# اقتباس حديث زي "(رواه البخاري)"، أو قوس آية قرآنية "﴾")، وده سبب شائع
# لـ false positive في looks_truncated لو معاملناهاش كنهاية صالحة.
_TRAILING_WRAPPERS = ")\"'”’»」』﴾]"


# مجموعة قوسين ختامية كاملة زي "(رواه البخاري ومسلم)" ملحقة بآخر النص،
# عشان نميّز بين "القصة متقطوعة فعلاً" و"القصة كاملة ومعاها استشهاد
# ملحق بعد النقطة الأصلية بدون نقطة تانية بعده".
_TRAILING_PAREN_GROUP = re.compile(r"[\(（][^()（）]*[\)）]\s*$")


def looks_truncated(narration: str) -> bool:
    """بيعتبر النص متقطوع لو آخر جزء "حقيقي" فيه (بعد تجاهل أي ملحق
    استشهاد كامل بين قوسين في الآخر، وبعد تجاهل أي أقواس/علامات اقتباس
    ختامية مفردة) مش منتهي بعلامة نهاية جملة حقيقية."""
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
    """نفس منطق split_sentences() في generate_voice.py بالضبط، عشان
    التقسيم هنا يطابق التقسيم وقت المزامنة مع الصوت حرفيًا."""
    parts = re.split(r"(?<=[.!؟…])\s+", narration.strip())
    return [part.strip() for part in parts if part.strip()]


def count_arabic_sentences(narration: str) -> int:
    return len(split_arabic_sentences(narration))


def clean_continuation_text(text: str) -> str:
    """بينضّف رد النداءات (نص حر) من أي تسمية أو تنسيق زايد لو الموديل
    حط حاجة زي 'NARRATION:' أو أسوار markdown بالغلط، ومن أي علامات
    اقتباس محيطة بالنص كله."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    cleaned = re.sub(r"^(NARRATION|narration)\s*:\s*", "", cleaned).strip()
    cleaned = cleaned.replace("**", "").replace("__", "").strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "”", "'"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _strip_label_markup(text: str) -> str:
    """يشيل زخرفة markdown شائعة ممكن الموديل يحطها حوالين تسميات
    الحقول رغم إننا مطلبناهاش (زي **HOOK:** أو ### HOOK: أو - HOOK:)."""
    cleaned = text.replace("**", "").replace("__", "")
    cleaned = re.sub(r"(?m)^[ \t]*[#>\-*]+[ \t]*", "", cleaned)
    return cleaned


def parse_labeled_response(text: str) -> dict:
    """يحلّل رد نداء القصة (نص حر بصيغة HOOK:/REGION:/SOURCE_TYPE:/
    SOURCE_REFERENCE:/NARRATION: كل حقل في سطر بعنوانه) لقاموس بمفاتيح
    lowercase. بيرجع قاموس فاضي لو مقدرش يلاقي أي حقل."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    cleaned = _strip_label_markup(cleaned)
    labels = "HOOK|REGION|SOURCE_TYPE|SOURCE_REFERENCE|NARRATION"
    pattern = re.compile(
        rf"(?:^|\n)\s*({labels})\s*:\s*(.*?)(?=\n\s*(?:{labels})\s*:|\Z)",
        re.DOTALL,
    )
    result: dict = {}
    for match in pattern.finditer(cleaned):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        result[key] = value
    return result


def validate_episode(episode: dict) -> str | None:
    """يرجّع رسالة الخطأ لو الحلقة النهائية (بعد الدمج) فيها مشكلة، أو
    None لو سليمة. خط دفاع أخير حتى لو المفروض كل حقل اتبنى صح لوحده."""
    if not REQUIRED_KEYS.issubset(episode.keys()):
        return f"الحلقة النهائية ناقصة حقول مطلوبة: {sorted(episode.keys())}"

    narration = str(episode.get("narration", "")).strip()
    if looks_truncated(narration):
        return "نص narration النهائي شكله متقطوع (مش منتهي بعلامة ترقيم واضحة)"

    word_count = count_words(narration)
    if word_count < ACCEPTABLE_MIN_WORDS:
        return (
            f"نص narration النهائي قصير جدًا ({word_count} كلمة، "
            f"الحد الأدنى المقبول {ACCEPTABLE_MIN_WORDS})"
        )

    if not episode.get("visual_keywords"):
        return "حقل visual_keywords فاضي"
    if not str(episode.get("hook", "")).strip():
        return "حقل hook فاضي"
    if not str(episode.get("source_type", "")).strip():
        return "حقل source_type فاضي — كل حلقة دينية لازم توثيق لنوع المصدر"
    if not str(episode.get("source_reference", "")).strip():
        return "حقل source_reference فاضي — كل حلقة دينية لازم مرجع دقيق"

    narration_en = episode.get("narration_en")
    if not isinstance(narration_en, list) or not narration_en:
        return "حقل narration_en فاضي أو مش قائمة (array)"
    if any(not str(item).strip() for item in narration_en):
        return "حقل narration_en فيه عنصر فاضي"

    expected_sentences = count_arabic_sentences(narration)
    if len(narration_en) != expected_sentences:
        return (
            f"عدد جمل narration_en ({len(narration_en)}) لا يطابق عدد "
            f"جمل narration الفعلي ({expected_sentences}) — لازم يتطابقوا "
            "بالظبط عشان تزامن الترجمة على الشاشة"
        )

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
    """بيحدّد لو الاستثناء ده مشكلة عرضية (ضغط مؤقت على السيرفر/شبكة)
    يستاهل إعادة محاولة سريعة. مهم: نفاد الحصة اليومية (429/PerDay)
    مستبعد من هنا عمدًا حتى لو ظاهريًا فيه رقم "retry in Ns" — انظر
    _is_daily_quota_exhausted تحت، ده بيتعامل معاه بشكل مختلف تمامًا."""
    if _is_daily_quota_exhausted(exc):
        return False
    text = str(exc).upper()
    transient_markers = ("503", "UNAVAILABLE", "500", "INTERNAL", "OVERLOADED", "DEADLINE_EXCEEDED", "TIMEOUT")
    return any(marker in text for marker in transient_markers)


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """بيحدّد لو الاستثناء ده تحديدًا نفاد الحصة اليومية المجانية (429
    RESOURCE_EXHAUSTED مع quotaId فيه "PerDay"). ده الفرق الجوهري عن أي
    429 تاني (زي حد الطلبات بالدقيقة اللي ممكن فعلاً يستفيد من إعادة
    محاولة قصيرة) — نفاد الحصة اليومية مفيش داعي نحاول تاني بعده خالص
    في نفس التشغيلة."""
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


def call_model(
    client: genai.Client,
    history: list[types.Content],
    prompt_text: str,
    config_builder,
    system_prompt: str,
    budget: int,
    label: str,
):
    """بيبعت prompt_text كدور مستخدم جديد فوق الـ history الحالي.
    بيعالج ثلاث مشاكل بشكل منفصل:
      - MAX_TOKENS (النداء اتقطع بسبب سقف التوكنز): بيرفع السقف ويعيد
        نفس النداء (BUDGET_RETRIES مرة).
      - خطأ سيرفر مؤقت (503/500/إلخ): بينتظر فترة متصاعدة ويعيد نفس
        النداء بنفس السقف (TRANSIENT_RETRIES مرة) قبل ما يستسلم.
      - نفاد الحصة اليومية (429/PerDay): بيرفع QuotaExhausted فورًا من
        غير أي إعادة محاولة (مفيش فايدة منها).
    بيضيف الدور (مستخدم + رد الموديل) للـ history مرة واحدة بس، بعد ما
    يستقر على رد نهائي. بيرجّع (نص الرد, finish_reason)."""
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
                    model=MODEL, contents=contents,
                    config=config_builder(system_prompt, attempt_budget),
                )
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 — أخطاء شبكة/حصة/حجب أمان
                last_exc = exc
                if _is_daily_quota_exhausted(exc):
                    raise QuotaExhausted(
                        f"نفدت الحصة اليومية المجانية لموديل {MODEL} أثناء {label} ({exc})"
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
            raise AttemptFailed(f"فشل استدعاء Gemini API في {label} ({last_exc})") from last_exc

        log_usage(response, label)
        candidates = getattr(response, "candidates", None) or []
        finish_reason = str(candidates[0].finish_reason) if candidates else ""

        if "MAX_TOKENS" in finish_reason and length_retry < BUDGET_RETRIES:
            attempt_budget = int(attempt_budget * LENGTH_ESCALATION)
            print(f"   ⚠️ {label}: اتقطع بسبب حد التوكنز — هرفع السقف لـ {attempt_budget} وأعيد نفس النداء...")
            continue
        break

    if "SAFETY" in finish_reason or "PROHIBITED" in finish_reason or "BLOCKLIST" in finish_reason:
        raise AttemptFailed(f"الرد اتحجب من Gemini في {label} (finish_reason={finish_reason})")

    reply_text = response.text or ""
    history.append(make_content("user", prompt_text))
    history.append(make_content("model", reply_text))
    return reply_text, finish_reason


# ─────────────────────────── نصوص البرومبت ───────────────────────────

def build_story_prompt(
    recent_titles: list[str], recent_regions: list[str], recent_hooks: list[str],
    target_words: int,
) -> str:
    message = (
        "اكتب حلقة جديدة تمامًا — قصة دينية/تاريخية إسلامية كاملة من "
        "الهوك للتمهيد للتصعيد للذروة للخاتمة، في رد واحد.\n\n"
        "⚠️ اللغة: narration بالكامل باللغة العربية الفصحى المبسّطة "
        "(Modern Standard Arabic) فقط، ممنوع أي لهجة عامية.\n\n"
        "⚠️ التوثيق الشرعي/التاريخي: الواقعة لازم تكون ثابتة من القرآن "
        "الكريم، أو حديث نبوي صحيح أو حسن، أو مصدر تاريخي إسلامي معتمد "
        "ومتفق عليه عند عامة أهل العلم. ممنوع اختلاق أي حوار أو تفصيلة "
        "أو اسم لم يرد في المصدر الأصلي، وممنوع أي رواية إسرائيلية غير "
        "موافقة لما ثبت بالقرآن والسنة الصحيحة، أو حديث ضعيف جدًا أو "
        "موضوع حتى لو منتشر شعبيًا. لو لست متأكدًا من ثبوت تفصيلة، لا "
        "تكتبها كحقيقة قطعية — اختر واقعة أخرى متأكد من ثبوتها.\n\n"
        "⚠️ عدم التكرار: ممنوع نفس الواقعة اللي اتستخدمت في حلقة سابقة "
        "حتى بعنوان أو صياغة مختلفة تمامًا. راجع الهوكات تحت (بيوصفوا "
        "الواقعة نفسها بدقة أكتر من العنوان) — لو الواقعة في بالك بتوصف "
        "نفس حادثة أي هوك منهم، ارفضها واختار واقعة مختلفة.\n\n"
        "⚠️ الهوك: أول جملة في narration لازم تكون هي نفسها حقل hook "
        "(أو صياغة قريبة جدًا منه) — مشوّقة ومباشرة تخلق فضول فوري (سؤال "
        "مثير، أو تفصيلة تاريخية مدهشة وحقيقية، أو مشهد لحظة الذروة قبل "
        "ما تُروى)، من غير أي تهويل يخالف وقار الموضوع الديني.\n\n"
        "⚠️ التنويع: اختار عصرًا/شخصية محورية مختلفة عن اللي اتذكرت تحت.\n\n"
        f"⚠️ الطول: اكتب narration كاملة (تمهيد+تصعيد+ذروة+خاتمة) في حدود "
        f"{target_words} كلمة عربية تقريبًا. لو المصدر مش فيه تفاصيل كافية "
        "توصلك للرقم ده بالظبط، اقفل القصة بخاتمة حقيقية بدل ما تحشو "
        "تفاصيل غير موثقة — القصة الكاملة والمتماسكة أهم من الوصول لرقم "
        "كلمات بعينه. لازم آخر جملة تنتهي بعلامة ترقيم واضحة (نقطة أو "
        "علامة تعجب أو علامة استفهام أو علامات حذف) تدل فعليًا على اكتمال "
        "القصة.\n\n"
        "⚠️ مهم جدًا بخصوص آخر حرف في ردك: لو ختمت القصة باستشهاد بحديث "
        "بين قوسين مثل (رواه البخاري) أو بآية قرآنية بين قوسين مزخرفين "
        "﴿...﴾، لازم تحط نقطة \".\" فورًا بعد القوس الختامي مباشرة (من "
        "غير مسافة قبلها). آخر حرف حرفيًا في ردك يجب أن يكون واحدًا من: "
        "نقطة (.) أو علامة تعجب (!) أو علامة استفهام (؟) — ولا شيء بعده.\n\n"
        "⚠️ الفورمات: التزم بالضبط بالشكل تحت. اكتب كل تسمية حرفيًا "
        "بالإنجليزية بالحروف الكبيرة كما هي (HOOK: بدون أي ترجمة أو "
        "تغيير أو زخرفة markdown حواليها)، كل تسمية في بداية سطر جديد، "
        "ومفيش أي نص أو مقدمة أو تعليق خارج الحقول دي:\n\n"
        "HOOK: <جملة الهوك>\n"
        "REGION: <وصف العصر/المكان>\n"
        "SOURCE_TYPE: <نوع المصدر (قرآن/حديث صحيح/حديث حسن/مصدر تاريخي "
        "معتمد)>\n"
        "SOURCE_REFERENCE: <المرجع الدقيق>\n"
        "NARRATION:\n<نص القصة الكاملة من الهوك للخاتمة>"
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


def build_finish_ending_prompt() -> str:
    """نداء واحد بس (مش حلقة) لو القصة اتقطعت قبل خاتمة حقيقية بعد كل
    محاولات رفع سقف التوكنز في نداء القصة الأساسي."""
    return (
        "النص اتقطع قبل ما يوصل لخاتمة حقيقية. اكتب دلوقتي فقط الجملة "
        "أو الجمل الختامية اللي تقفل القصة بعبرة أو حكمة واضحة مبنية "
        "على المصدر نفسه، من غير أي حدث جديد ومن غير تكرار أي جملة "
        "سابقة. لا تستشهد بآية أو حديث في هذا الرد تحديدًا (تفاديًا لأي "
        "التباس في علامة النهاية) — اكتب جملة ختامية عادية بأسلوبك، "
        "وتأكد إن آخر حرف حرفيًا في ردك هو نقطة (.) أو علامة تعجب (!) "
        "أو علامة استفهام (؟) مباشرة، من غير أي قوس أو علامة اقتباس أو "
        "أي حرف آخر بعدها."
    )


def build_finalize_prompt(final_narration: str, recent_titles: list[str]) -> str:
    # نقسّم narration بأنفسنا (بنفس منطق التقسيم اللي هيُستخدم لاحقًا في
    # المزامنة مع الصوت) بدل ما نسيب الموديل يخمّن تقسيمه بنفسه.
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
        "2) narration_en: مصفوفة (array) تحتوي على "
        f"{sentence_count} عنصرًا بالضبط لا أكثر ولا أقل — عنصر واحد "
        "لكل جملة مرقّمة أعلاه، بنفس ترتيب الأرقام (العنصر الأول هو "
        "ترجمة الجملة رقم 1، والعنصر الثاني ترجمة الجملة رقم 2، وهكذا). "
        "كل عنصر هو الترجمة الإنجليزية الأمينة لجملته المقابلة فقط. "
        "ممنوع دمج جملتين مرقّمتين في عنصر واحد، وممنوع تقسيم جملة "
        f"مرقّمة واحدة لعنصرين. عدّ الجمل المرقّمة أعلاه بنفسك ({sentence_count} "
        "جملة) وتأكد إن طول مصفوفة narration_en يساويه بالضبط قبل ما "
        "تُنهي ردك.\n\n"
        "3) visual_keywords: كل كلمة بحث لازم تكون مشتقة من تفصيلة "
        "ملموسة ومحددة مذكورة فعليًا في narration أعلاه، وممنوع منعًا "
        "باتًا أي كلمة بحث ممكن تنتج لقطة فيها تجسيد بشري لنبي أو خليفة "
        "راشد أو صحابي بعينه — طبيعة/عمارة إسلامية تاريخية/مخطوطات وخط "
        "عربي/أشخاص مجهولي الهوية بس.\n\n"
        "4) caption: وصف قصير جذّاب للفيديو (لمنصات التواصل).\n\n"
        "5) phonetic_hints: تلميحات نطق للكلمات الصعبة أو غير الشائعة "
        "الواردة في narration (لو وجدت).\n\n"
        "اكتب الرد بصيغة JSON فقط حسب الـ schema المحدد، من غير أي نص "
        "خارج الـ JSON."
    )
    if recent_titles:
        message += "\n\nالعناوين اللي اتستخدمت قبل كده (تجنب أي تشابه معاها):\n- " + "\n- ".join(recent_titles)
    return message


# ─────────────────────────── تنفيذ محاولة واحدة ───────────────────────────

def run_single_attempt(
    client: genai.Client,
    system_prompt: str,
    recent_titles: list[str],
    recent_regions: list[str],
    recent_hooks: list[str],
    target_words: int,
    attempt_label: str,
) -> dict:
    history: list[types.Content] = []

    # ── نداء القصة الكاملة (هوك + تمهيد + تصعيد + ذروة + خاتمة) ──
    reply, _ = call_model(
        client, history,
        build_story_prompt(recent_titles, recent_regions, recent_hooks, target_words),
        free_text_config, system_prompt, STORY_MAX_TOKENS,
        f"{attempt_label} | القصة",
    )
    fields = parse_labeled_response(reply)
    for key in ("hook", "region", "source_type", "source_reference", "narration"):
        if not fields.get(key, "").strip():
            # مهم للتشخيص: من غير الطباعة دي، فشل "ناقص حقل" كان بيبقى
            # عمياني تمامًا (منعرفش الموديل رد بإيه فعليًا). بنطبع أول
            # جزء بس (500 حرف) عشان اللوج ميتملّاش برد طويل.
            print(f"   🔎 رد {attempt_label} | القصة الخام (أول 500 حرف):\n{reply[:500]!r}")
            raise AttemptFailed(f"رد نداء القصة ناقص حقل '{key}' أو فاضي")

    hook = fields["hook"].replace("**", "").replace("__", "").strip()
    region = fields["region"].replace("**", "").replace("__", "").strip()
    source_type = fields["source_type"].replace("**", "").replace("__", "").strip()
    source_reference = fields["source_reference"].replace("**", "").replace("__", "").strip()
    narration = clean_continuation_text(fields["narration"])

    print(f"   📝 القصة: {count_words(narration)} كلمة (هدف تقريبي {target_words})")

    # لو اتقطعت قبل خاتمة حقيقية، نداء واحد بس يكمّل الخاتمة (مش حلقة
    # توسيعات) — لو لسه متقطوعة بعده، نعتبرها فشل حقيقي للمحاولة.
    if looks_truncated(narration):
        reply, _ = call_model(
            client, history, build_finish_ending_prompt(),
            free_text_config, system_prompt, STORY_MAX_TOKENS,
            f"{attempt_label} | إكمال الخاتمة",
        )
        narration += " " + clean_continuation_text(reply)
        print(f"   📝 بعد إكمال الخاتمة: {count_words(narration)} كلمة")

    if looks_truncated(narration):
        raise AttemptFailed("narration لسه متقطوعة بعد محاولة إكمال الخاتمة (مش منتهية بعلامة ترقيم واضحة)")

    final_word_count = count_words(narration)
    if final_word_count < ACCEPTABLE_MIN_WORDS:
        raise AttemptFailed(
            f"narration قصيرة جدًا ({final_word_count} كلمة، "
            f"الحد الأدنى المقبول {ACCEPTABLE_MIN_WORDS})"
        )
    if final_word_count < target_words:
        print(
            f"   ℹ️ الطول ({final_word_count} كلمة) أقل من الهدف "
            f"({target_words}) لكنه فوق الحد الأدنى المقبول — هيتقبل من غير إعادة."
        )

    # ── نداء finalize: باقي الحقول بناءً على narration النهائي ──
    reply, _ = call_model(
        client, history, build_finalize_prompt(narration, recent_titles),
        finalize_json_config, system_prompt, FINALIZE_MAX_TOKENS,
        f"{attempt_label} | finalize",
    )
    try:
        finalize_data = json.loads(reply)
    except json.JSONDecodeError as exc:
        raise AttemptFailed(f"رد finalize غير صالح JSON ({exc})") from exc

    episode = {
        "title": finalize_data.get("title", ""),
        "hook": hook,
        "region": region,
        "narration": narration,
        "narration_en": finalize_data.get("narration_en", []),
        "visual_keywords": finalize_data.get("visual_keywords", []),
        "caption": finalize_data.get("caption", ""),
        "phonetic_hints": finalize_data.get("phonetic_hints", []),
        "source_type": source_type,
        "source_reference": source_reference,
    }

    error = validate_episode(episode)
    if error:
        raise AttemptFailed(error)

    return episode


def generate_episode() -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("خطأ: لازم تضيف GEMINI_API_KEY في GitHub Secrets")

    client = genai.Client(api_key=api_key)
    system_prompt = load_system_prompt()
    recent_titles = load_used_history()
    recent_regions = load_used_regions()
    recent_hooks = load_used_hooks()

    print(
        f"🕌 الموديل: {MODEL} | thinking_budget: {THINKING_BUDGET} | "
        f"هدف الطول: {TARGET_WORDS} كلمة | الحد الأدنى المقبول: {ACCEPTABLE_MIN_WORDS} كلمة"
    )

    last_error = "لا يوجد"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n===== محاولة كاملة {attempt}/{MAX_ATTEMPTS} (محادثة جديدة) =====")
        try:
            return run_single_attempt(
                client, system_prompt, recent_titles, recent_regions, recent_hooks,
                TARGET_WORDS, f"محاولة {attempt}",
            )
        except QuotaExhausted as exc:
            # مفيش أي فايدة من محاولة كاملة تانية — الحصة اليومية نفدت.
            sys.exit(f"❌ توقف فوري: {exc}")
        except AttemptFailed as exc:
            last_error = str(exc)
            print(f"⚠️ فشلت المحاولة الكاملة {attempt}/{MAX_ATTEMPTS}: {last_error}")
        except Exception as exc:  # noqa: BLE001 — أي خطأ غير متوقع تاني
            last_error = f"خطأ غير متوقع: {exc}"
            print(f"⚠️ فشلت المحاولة الكاملة {attempt}/{MAX_ATTEMPTS}: {last_error}")

    sys.exit(f"❌ فشل توليد حلقة سليمة بعد {MAX_ATTEMPTS} محاولات كاملة. آخر خطأ: {last_error}")


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
    print(f"   عدد جمل narration_en: {len(episode.get('narration_en', []))}")
    print(f"   كلمات البحث: {episode['visual_keywords']}")
    print(f"   تلميحات النطق: {episode.get('phonetic_hints', [])}")
