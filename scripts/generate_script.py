"""
generate_script.py
يستدعي Gemini API عشان يولّد سيناريو القصة الدينية/التاريخية الإسلامية +
الترجمة الإنجليزية الموازية + كلمات البحث البصرية + مرجع التوثيق الشرعي.

=== تعديل جديد: توليد narration على مرحلتين داخل محادثة واحدة (حل مشكلة القفل المبكر) ===
المشكلة اللي ظهرت في التشغيل الفعلي: أربع محاولات متتالية طلعت كلها
narration أقصر من الحد الأدنى (639-875 كلمة بدل 970+)، رغم إن
finish_reason في كل المحاولات كان طبيعي (مش MAX_TOKENS) — يعني الموديل
معاه مساحة توكنز فاضية كتير (استخدم أقل من نص MAX_OUTPUT_TOKENS في كل
مرة) ومع ذلك اختار يقفل القصة بنفسه. السبب: البرومبت القديم كان فيه
تعليمتين بيتصادموا مع بعض داخل نفس الرسالة — "لازم 970+ كلمة" مقابل
"لازم تقفل بخاتمة حقيقية تنتهي بعلامة ترقيم واضحة" — والموديل كان بيفضّل
الاكتمال السردي على الطول كل مرة، وإعادة المحاولة القديمة كانت بتبدأ
القصة من الصفر تاني (بنفس الصراع الداخلي)، فمكانش في تراكم حقيقي.

الحل الجديد: تقسيم كتابة narration لمرحلتين منفصلتين داخل نفس المحادثة
(نفس الـ conversation history)، بحيث الموديل في كل رسالة يركّز على مهمة
واحدة بس ومفيش تصادم بين تعليمتين:

  المرحلة 1 (الهوك + التمهيد + تصعيد أول): تعليمة صريحة إنه *ممنوع* يقفل
  القصة أو يكتب الذروة أو الخاتمة دلوقتي — بس يوصف لحد نقطة تصعيد قوية.
  هدف تقريبي: PHASE1_TARGET_RATIO من الحد الأدنى الكلي.

  المرحلة 2 (الذروة + الخاتمة): بعد ما المرحلة 1 توصل لطول كافٍ، نطلب من
  الموديل يكمل *بالظبط* من حيث وقف (نفس المحادثة، فشايف نص نفسه الفعلي)
  ويكتب الذروة والخاتمة الحقيقية.

لو أي مرحلة طلعت قصيرة عن هدفها، بنبعت رسالة "توسيع" إضافية (حد أقصى
MAX_PHASE_EXPANSIONS لكل مرحلة) تطلب تفاصيل حسية إضافية من نفس الأحداث
(مش أحداث جديدة)، من غير ما نطلب منه يعيد القصة من الأول.

بعد ما narration الكاملة (تمهيد+تصعيد+ذروة+خاتمة) تتجمّع وتكون سليمة
(طول كافٍ + منتهية بعلامة ترقيم واضحة)، بنعمل نداء أخير "finalize" بس
عشان يبني باقي الحقول (title/narration_en/visual_keywords/caption/
phonetic_hints) بناءً على نص narration النهائي المُعطى له حرفيًا —
وممنوع عليه يعدّل فيه حرف واحد. الحقول hook/region/source_type/
source_reference بناخدها زي ما هي من رد المرحلة 1 (مش بنطلب منه يعيدها
تاني في الآخر، عشان نضمن تطابقها ومنعطيش الموديل فرصة يغيّرها لاحقًا).

⚠️ ملاحظة SDK مهمة: جلسة client.chats.create() في مكتبة google-genai
لبايثون (بعكس نسخة JavaScript) بتثبّت الـ config وقت إنشاء الجلسة ومفيش
override لكل رسالة — يعني معندناش طريقة نطلب بيها نص حر في رسايل
ونطلب JSON schema في رسالة تانية جوه نفس الـ chat session. البديل
(المستخدم هنا) هو إدارة الـ history يدويًا: قائمة من types.Content
بنمررها كاملة في contents= مع كل نداء client.models.generate_content،
ونضيفلها دور المستخدم ورد الموديل بعد كل خطوة — بالظبط زي ما Chat.
send_message شغّالة جواها، لكن مع حرية تغيير الـ config (نص حر أو JSON
schema) في كل نداء على حدة.

=== تعديل سابق: الانتقال من Groq إلى Gemini ===
كانت النسخة السابقة بتستخدم Groq (نموذج openai/gpt-oss-120b). دلوقتي
بتستخدم Google Gemini عبر حزمة "google-genai" الرسمية (pip install
-U google-genai)، وده غيّر 3 حاجات جوهرية:
1) مفتاح البيئة بقى GEMINI_API_KEY بدل GROQ_API_KEY.
2) الـ JSON Schema بتتبع صيغة Gemini (uppercase types)، عبر دالة
   to_gemini_schema() اللي بتحوّل تعريف JSON Schema عادي تلقائيًا.
3) مفيش reasoning_effort زي Groq's gpt-oss — البديل ThinkingConfig
   (thinking_budget=...)، متحكم فيه عبر GEMINI_THINKING_BUDGET.

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
from pathlib import Path

from google import genai
from google.genai import types

SCRIPT_DIR = Path(__file__).parent
PROMPT_PATH = SCRIPT_DIR.parent / "prompts" / "islamic_history_system_prompt.md"
OUTPUT_PATH = SCRIPT_DIR.parent / "state" / "current_episode.json"

# ─────────────────────────── الإعدادات ───────────────────────────

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE = 0.75
# سقف التوكنز لنداءات النص الحر (كل مرحلة/توسيع بيكتب جزء من القصة بس،
# مش القصة كلها، فمحتاج سقف أصغر من نداء finalize).
PHASE_MAX_TOKENS = 4000
# سقف نداء finalize (JSON فيه narration_en كمصفوفة بعدد جمل القصة كاملة
# + باقي الحقول) — سيبناه سخي زي الأصل عشان القصص الطويلة (900+ كلمة
# ممكن تبقى 60-90 جملة).
FINALIZE_MAX_TOKENS = 9000
# انظر الملاحظة فوق. 0 = من غير تفكير داخلي إضافي. اترفعت افتراضيًا عبر
# GEMINI_THINKING_BUDGET في الـ workflow لمهمة التخطيط السردي.
THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))

# === فيديو كامل فوق 5 دقايق، ريل واحد بس (مقتطف من أول الفيديو) ===
# النسبة الموثقة تجريبيًا لسرعة نطق edge-tts (بعد وقفات الجمل): 300
# كلمة ≈ 94-150 ثانية. القيمة الافتراضية هنا 1050 كلمة (مع
# MIN_NARRATION_WORDS=970 في الـ workflow كحد أدنى صارم) لضمان تخطي
# الـ300 ثانية حتى في أسرع سيناريو نطق محتمل.
TARGET_WORDS = int(os.getenv("TARGET_WORDS", "1050"))
MIN_NARRATION_WORDS = os.environ.get("MIN_NARRATION_WORDS")
MIN_NARRATION_WORDS = int(MIN_NARRATION_WORDS) if MIN_NARRATION_WORDS else None

# نسبة الحد الأدنى الكلي اللي المرحلة 1 (تمهيد+تصعيد، من غير ذروة أو
# خاتمة) لازم توصلها تقريبًا قبل ما ننتقل للمرحلة 2 (ذروة+خاتمة).
PHASE1_TARGET_RATIO = 0.55
# حد أقصى لعدد نداءات "التوسيع" الإضافية المسموح بيها داخل كل مرحلة
# (لو المرحلة طلعت قصيرة عن هدفها). كل توسيع بيضيف تفاصيل حسية لنفس
# الأحداث، مش أحداث جديدة.
MAX_PHASE_EXPANSIONS = 2
# لو نداء واحد اتقطع فعليًا بسبب حد التوكنز (MAX_TOKENS)، نرفع السقف
# ونعيد نفس النداء (مش المحاولة كلها) — نفس منطق الأصل بس على مستوى
# النداء الواحد بدل المحاولة الكاملة.
BUDGET_RETRIES = 2
LENGTH_ESCALATION = 1.5

# === إعادة محاولة كاملة من الصفر (محادثة جديدة تمامًا) ===
# دلوقتي ده خط دفاع أخير بس لمشاكل غير متعلقة بالطول (حجب أمان، رد JSON
# تالف، فشل تحليل الحقول الأساسية من رد المرحلة 1، إلخ) — مشكلة الطول
# نفسها بقت بتتحل داخل المحاولة الواحدة عبر آلية المرحلتين+التوسيع فوق،
# فمحتاجناش عدد محاولات كامل كبير زي الأصل (كان 4).
MAX_ATTEMPTS = 2

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
# المرحلتين المُجمَّع) ومن غير hook/region/source_type/source_reference
# (بناخدها زي ما هي من رد المرحلة 1 بدل ما نطلب من الموديل يعيدها).
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


def looks_truncated(narration: str) -> bool:
    stripped = narration.strip()
    if not stripped:
        return True
    return not stripped.endswith((".", "!", "؟", "?", "…", '"', "”", "»"))


def count_arabic_sentences(narration: str) -> int:
    """نفس منطق split_sentences() في generate_voice.py، عشان نتأكد إن
    عدد عناصر narration_en هيطابق عدد الجمل وقت المزامنة مع الصوت."""
    parts = re.split(r"(?<=[.!؟…])\s+", narration.strip())
    return len([part for part in parts if part.strip()])


def clean_continuation_text(text: str) -> str:
    """بينضّف رد المراحل/التوسيعات (نص حر) من أي تسمية أو تنسيق زايد لو
    الموديل حط حاجة زي 'NARRATION:' أو أسوار markdown بالغلط، ومن أي
    علامات اقتباس محيطة بالنص كله."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    cleaned = re.sub(r"^(NARRATION|narration)\s*:\s*", "", cleaned).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "”", "'"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def parse_labeled_response(text: str) -> dict:
    """يحلّل رد المرحلة 1 (نص حر بصيغة HOOK:/REGION:/SOURCE_TYPE:/
    SOURCE_REFERENCE:/NARRATION: كل حقل في سطر بعنوانه) لقاموس بمفاتيح
    lowercase. بيرجع قاموس فاضي لو مقدرش يلاقي أي حقل."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
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

    if MIN_NARRATION_WORDS is not None:
        word_count = count_words(narration)
        if word_count < MIN_NARRATION_WORDS:
            return (
                f"نص narration النهائي قصير جدًا ({word_count} كلمة، "
                f"الحد الأدنى المطلوب {MIN_NARRATION_WORDS})"
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


# ─────────────────────── إدارة المحادثة يدويًا ───────────────────────
# (انظر الملاحظة في أعلى الملف عن سبب عدم استخدام client.chats.create)

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
    """بيبعت prompt_text كدور مستخدم جديد فوق الـ history الحالي، مع
    إعادة نفس النداء (بسقف توكنز أعلى) لو اتقطع بسبب MAX_TOKENS. بيضيف
    الدور (مستخدم + رد الموديل) للـ history مرة واحدة بس، بعد ما يستقر
    على رد نهائي، عشان مايتلوثش الـ history بمحاولات فاشلة وسط الطريق.
    بيرجّع (نص الرد, finish_reason)."""
    attempt_budget = budget
    response = None
    finish_reason = ""
    for retry in range(BUDGET_RETRIES + 1):
        contents = history + [make_content("user", prompt_text)]
        try:
            response = client.models.generate_content(
                model=MODEL, contents=contents,
                config=config_builder(system_prompt, attempt_budget),
            )
        except Exception as exc:  # noqa: BLE001 — أخطاء شبكة/حصة/حجب أمان
            raise AttemptFailed(f"فشل استدعاء Gemini API في مرحلة {label} ({exc})") from exc

        log_usage(response, label)
        candidates = getattr(response, "candidates", None) or []
        finish_reason = str(candidates[0].finish_reason) if candidates else ""

        if "MAX_TOKENS" in finish_reason and retry < BUDGET_RETRIES:
            attempt_budget = int(attempt_budget * LENGTH_ESCALATION)
            print(f"   ⚠️ {label}: اتقطع بسبب حد التوكنز — هرفع السقف لـ {attempt_budget} وأعيد نفس النداء...")
            continue
        break

    if "SAFETY" in finish_reason or "PROHIBITED" in finish_reason or "BLOCKLIST" in finish_reason:
        raise AttemptFailed(f"الرد اتحجب من Gemini في مرحلة {label} (finish_reason={finish_reason})")

    reply_text = response.text or ""
    history.append(make_content("user", prompt_text))
    history.append(make_content("model", reply_text))
    return reply_text, finish_reason


# ─────────────────────────── نصوص البرومبت ───────────────────────────

def build_phase1_prompt(
    recent_titles: list[str], recent_regions: list[str], recent_hooks: list[str],
    phase1_target: int,
) -> str:
    message = (
        "اكتب المرحلة الأولى فقط من حلقة جديدة تمامًا — التمهيد وتصعيد "
        "الأحداث بس. 🚫 ممنوع منعًا باتًا في هذه الرسالة إنك تكتب الذروة "
        "أو الحل أو الخاتمة أو أي عبرة ختامية — توقف عند نقطة تصعيد قوية "
        "قبل الذروة مباشرة، وسأطلب منك كتابة الذروة والخاتمة في رسالة "
        "منفصلة بعد كده.\n\n"
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
        f"⚠️ الطول: اكتب هذه المرحلة (تمهيد+تصعيد بس) في حدود "
        f"{phase1_target} كلمة عربية تقريبًا (يزيد أو ينقص 20%). أضف "
        "تفاصيل حسّية ووصفية واردة في المصدر نفسه (المكان، الأجواء، "
        "ردود الأفعال) بدل الاختصار، من غير اختراع أي تفصيلة غير موثقة.\n\n"
        "اكتب ردك بالضبط بهذا الشكل (كل حقل في سطر بعنوانه، ومفيش أي "
        "نص أو تعليق إضافي خارج الحقول دي):\n\n"
        "HOOK: <جملة الهوك>\n"
        "REGION: <وصف العصر/المكان>\n"
        "SOURCE_TYPE: <نوع المصدر (قرآن/حديث صحيح/حديث حسن/مصدر تاريخي "
        "معتمد)>\n"
        "SOURCE_REFERENCE: <المرجع الدقيق>\n"
        "NARRATION:\n<نص المرحلة الأولى بالكامل — تمهيد وتصعيد بس، من "
        "غير ذروة أو خاتمة>"
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


def build_phase1_expand_prompt(remaining_words: int) -> str:
    return (
        f"لسه في مرحلة التمهيد والتصعيد بس (مش الذروة ولا الخاتمة بعد). "
        f"وسّع فيما كتبته بتفاصيل حسّية إضافية واردة في المصدر نفسه "
        "(المكان، الأصوات، ردود الأفعال، المشاعر) من غير ما تتقدم للذروة "
        "أو تلمّح لنهاية القصة، ومن غير اختراع أي تفصيلة جديدة غير "
        f"موثقة. أضف حوالي {remaining_words} كلمة إضافية. اكتب استكمال "
        "نص narration مباشرة من حيث توقفت بالظبط — من غير أي تسمية أو "
        "تعليق أو إعادة لأي جزء سبق كتابته."
    )


def build_phase2_prompt(phase2_target: int) -> str:
    return (
        "دلوقتي اكتب الجزء الأخير من القصة: الذروة (لحظة الحسم الفعلية "
        "للواقعة كما ثبتت في المصدر) ثم خاتمة حقيقية فيها عبرة أو حكمة "
        "واضحة تقفل القصة تمامًا. لازم آخر جملة في ردك تنتهي بعلامة "
        "ترقيم واضحة (نقطة أو علامة تعجب أو علامة استفهام أو علامات "
        "حذف) تدل فعليًا على اكتمال القصة — القطع قبل الوصول لخاتمة "
        "حقيقية غير مقبول إطلاقًا. ممنوع اختراع أي حدث أو تفصيلة غير "
        f"واردة في المصدر. اكتب هذا الجزء في حدود {phase2_target} كلمة "
        "على الأقل، بتفاصيل حسّية كافية من غير استعجال للخاتمة. اكتب "
        "استكمال نص narration مباشرة من حيث توقفت آخر مرة — من غير "
        "إعادة أي جزء سبق كتابته ومن غير أي تسمية أو تعليق."
    )


def build_phase2_expand_short_prompt(remaining_words: int) -> str:
    return (
        "القصة وصلت لخاتمتها لكن عدد الكلمات لسه أقل من المطلوب بحوالي "
        f"{remaining_words} كلمة. وسّع في وصف مشهد الذروة أو الخاتمة "
        "نفسها بتفاصيل حسّية ووصفية إضافية من المصدر (المشاعر، الأصوات، "
        "رد الفعل، السياق المكاني والزمني)، من غير إضافة أي حدث جديد لم "
        "يثبت فعلاً ومن غير تكرار أي جملة سابقة. حافظ على إن آخر جملة "
        "في استكمالك لسه تنتهي بعلامة ترقيم واضحة تدل على اكتمال القصة."
    )


def build_phase2_expand_truncated_prompt() -> str:
    return (
        "النص اتقطع قبل ما يوصل لخاتمة حقيقية. اكتب دلوقتي فقط الجملة "
        "أو الجمل الختامية اللي تقفل القصة بعبرة أو حكمة واضحة مبنية "
        "على المصدر نفسه، من غير أي حدث جديد ومن غير تكرار أي جملة "
        "سابقة، وتأكد إنها تنتهي بعلامة ترقيم واضحة (نقطة أو علامة "
        "تعجب أو علامة استفهام)."
    )


def build_finalize_prompt(final_narration: str, recent_titles: list[str]) -> str:
    message = (
        "هذا هو نص narration النهائي والمعتمد بالكامل للحلقة (تجميع كل "
        "ما كتبته في الرسائل السابقة). لا تُعدّل فيه أو تُعِد صياغته أو "
        "تختصره أو تُطِله بأي شكل — دورك الآن بس إنك تبني باقي حقول "
        "الحلقة بناءً عليه:\n\n"
        f"--- بداية narration النهائي ---\n{final_narration}\n"
        "--- نهاية narration النهائي ---\n\n"
        "المطلوب منك الآن:\n\n"
        "1) title: عنوان جذّاب ومختصر للحلقة، غير مكرر مع العناوين "
        "السابقة المذكورة تحت.\n\n"
        "2) narration_en: مصفوفة (array)، كل عنصر فيها هو الترجمة "
        "الإنجليزية الأمينة لجملة واحدة فقط من narration أعلاه، بنفس "
        "الترتيب وبنفس العدد بالضبط (التقسيم بعد كل نقطة أو علامة تعجب "
        "أو علامة استفهام أو علامات حذف، تمامًا كما تُقسَّم narration "
        "نفسها لجمل). لو narration فيها مثلاً 40 جملة، لازم narration_en "
        "تحتوي على 40 عنصرًا بالضبط لا أكثر ولا أقل.\n\n"
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
    effective_min: int,
    phase1_target: int,
    attempt_label: str,
) -> dict:
    history: list[types.Content] = []

    # ── المرحلة 1: الهوك + التمهيد + تصعيد أول ──
    reply, _ = call_model(
        client, history,
        build_phase1_prompt(recent_titles, recent_regions, recent_hooks, phase1_target),
        free_text_config, system_prompt, PHASE_MAX_TOKENS,
        f"{attempt_label} | مرحلة 1",
    )
    fields = parse_labeled_response(reply)
    for key in ("hook", "region", "source_type", "source_reference", "narration"):
        if not fields.get(key, "").strip():
            raise AttemptFailed(f"رد المرحلة 1 ناقص حقل '{key}' أو فاضي")

    hook = fields["hook"]
    region = fields["region"]
    source_type = fields["source_type"]
    source_reference = fields["source_reference"]
    narration = clean_continuation_text(fields["narration"])

    print(f"   📝 مرحلة 1: {count_words(narration)} كلمة (هدف تقريبي {phase1_target})")

    # توسيع المرحلة 1 لو لسه قصيرة عن هدفها
    for expansion in range(1, MAX_PHASE_EXPANSIONS + 1):
        if count_words(narration) >= phase1_target:
            break
        remaining = phase1_target - count_words(narration)
        reply, _ = call_model(
            client, history, build_phase1_expand_prompt(remaining),
            free_text_config, system_prompt, PHASE_MAX_TOKENS,
            f"{attempt_label} | مرحلة 1 - توسيع {expansion}",
        )
        narration += " " + clean_continuation_text(reply)
        print(f"   📝 مرحلة 1 بعد توسيع {expansion}: {count_words(narration)} كلمة")

    # ── المرحلة 2: الذروة + الخاتمة ──
    phase2_target = max(effective_min - count_words(narration), 150)
    reply, _ = call_model(
        client, history, build_phase2_prompt(phase2_target),
        free_text_config, system_prompt, PHASE_MAX_TOKENS,
        f"{attempt_label} | مرحلة 2",
    )
    narration += " " + clean_continuation_text(reply)
    print(f"   📝 مرحلة 2: الإجمالي بقى {count_words(narration)} كلمة (الحد الأدنى الكلي {effective_min})")

    # توسيع المرحلة 2 لو لسه قصيرة أو متقطوعة
    for expansion in range(1, MAX_PHASE_EXPANSIONS + 1):
        short = count_words(narration) < effective_min
        truncated = looks_truncated(narration)
        if not short and not truncated:
            break
        if short:
            remaining = effective_min - count_words(narration)
            prompt = build_phase2_expand_short_prompt(remaining)
        else:
            prompt = build_phase2_expand_truncated_prompt()
        reply, _ = call_model(
            client, history, prompt,
            free_text_config, system_prompt, PHASE_MAX_TOKENS,
            f"{attempt_label} | مرحلة 2 - توسيع {expansion}",
        )
        narration += " " + clean_continuation_text(reply)
        print(f"   📝 مرحلة 2 بعد توسيع {expansion}: {count_words(narration)} كلمة")

    final_word_count = count_words(narration)
    if final_word_count < effective_min:
        raise AttemptFailed(
            f"narration لسه قصيرة بعد كل التوسيعات ({final_word_count} كلمة، "
            f"الحد الأدنى {effective_min})"
        )
    if looks_truncated(narration):
        raise AttemptFailed("narration لسه متقطوعة بعد كل التوسيعات (مش منتهية بعلامة ترقيم واضحة)")

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

    effective_min = TARGET_WORDS
    if MIN_NARRATION_WORDS is not None:
        effective_min = max(effective_min, MIN_NARRATION_WORDS)
    phase1_target = int(effective_min * PHASE1_TARGET_RATIO)

    print(
        f"🕌 الموديل: {MODEL} | thinking_budget: {THINKING_BUDGET} | "
        f"الحد الأدنى الكلي: {effective_min} كلمة | هدف مرحلة 1: {phase1_target} كلمة"
    )

    last_error = "لا يوجد"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n===== محاولة كاملة {attempt}/{MAX_ATTEMPTS} (محادثة جديدة) =====")
        try:
            return run_single_attempt(
                client, system_prompt, recent_titles, recent_regions, recent_hooks,
                effective_min, phase1_target, f"محاولة {attempt}",
            )
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
