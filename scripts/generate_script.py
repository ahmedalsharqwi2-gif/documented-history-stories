"""
generate_script.py
يستدعي Gemini API عشان يولّد سيناريو القصة الدينية/التاريخية الإسلامية +
الترجمة الإنجليزية الموازية + كلمات البحث البصرية + مرجع التوثيق الشرعي.

=== تعديل جديد: الانتقال من Groq إلى Gemini ===
كانت النسخة السابقة بتستخدم Groq (نموذج openai/gpt-oss-120b). دلوقتي
بتستخدم Google Gemini عبر حزمة "google-genai" الرسمية (pip install
-U google-genai)، وده غيّر 3 حاجات جوهرية في السكربت:

1) مفتاح البيئة بقى GEMINI_API_KEY بدل GROQ_API_KEY — لازم تحدّث الـ
   GitHub Secret بالاسم الجديد (وتحذف القديم لو مش مستخدم في حاجة
   تانية).

2) الـ JSON Schema بتتبع صيغة Gemini (أنواع بحروف كبيرة زي "OBJECT"/
   "STRING"/"ARRAY" بدل "object"/"string"/"array" بحروف صغيرة زي
   OpenAI/Groq، ومفيش "additionalProperties"). عشان منحتفظش بنفس
   الحقول مرتين، الـ schema الأساسية لسه متعرّفة بصيغة JSON Schema
   العادية (lowercase) زي الأول، وفيه دالة to_gemini_schema() بتحوّلها
   تلقائيًا لصيغة Gemini وقت الاستدعاء بس — أي تعديل مستقبلي على
   الحقول (إضافة/حذف حقل) يتم في EPISODE_SCHEMA مكان واحد بس.

3) مفيش reasoning_effort في Gemini زي موديلات Groq's gpt-oss. البديل
   القريب هو ThinkingConfig(thinking_budget=...) — تحكم في مقدار
   "التفكير الداخلي" قبل الرد. بما إن المهمة هنا توليد JSON منظم بس
   (مش تحليل منطقي معقد)، القيمة الافتراضية GEMINI_THINKING_BUDGET=0
   (تعطيل التفكير الإضافي) كافية وأسرع وأرخص؛ ارفعها لو حسّيت إن جودة
   القصص المولّدة محتاجة تفكير أعمق.

باقي منطق الملف (تتبع العناوين/الهوكات/المناطق المستخدمة، التحقق من
اكتمال narration وتطابق narration_en، إعادة المحاولة عند القطع أو
الخطأ) باقٍ كما هو تمامًا، لأنه منطق مستقل عن مزوّد الـ API.

=== تعديل جديد: تصعيد حقيقي عند قِصر narration ===
لوحظ إن الموديل بيميل بشكل منهجي لكتابة narration أقصر من TARGET_WORDS
المطلوب (أحيانًا أقل من النص المطلوب بـ 40-50%)، وإن إعادة المحاولة
القديمة كانت بترسل نفس الرسالة بالحرف الواحد من غير أي إشارة إن
المحاولة اللي فاتت كانت قصيرة — فمفيش أي "ضغط" حقيقي يدفع الموديل
يكتب أطول في المحاولة التالية، وأحيانًا كانت المحاولة الثانية بتطلع
أقصر من الأولى.

الحل: build_user_message() بقت بتاخد short_attempt_word_count اختياري.
لو مبعوت، بيتضاف مقطع تحذيري صريح في آخر الرسالة يقول بالظبط عدد
الكلمات اللي طلعت في المحاولة اللي فاتت وإنه غير مقبول، ويطلب صراحة
كتابة نص أطول بوضوح. كمان الصياغة الأساسية اتغيّرت من "حوالي X كلمة
(±15%)" لصياغة أوضح بإنه حد أدنى صارم ومفيش مجال للتهاون فيه.

⚠️ تنويه مهم وصادق (باقٍ كما كان مع أي مزوّد API): الموديل مايقدرش
"يتحقق" فعليًا من صحة أي حديث أو نسبة رواية بشكل قاطع — مفيش أداة بحث
أو مطابقة أسانيد جوه السكريبت، سواء كان المزوّد Groq أو Gemini أو غيره.
حقل "source_type"/"source_reference" بيجبر الموديل يصرّح بمرجعه
تحديدًا لكل حلقة، عشان يبقى قابلاً للمراجعة البشرية قبل النشر.
"""
import os
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
MAX_OUTPUT_TOKENS = 9000
# انظر الملاحظة رقم 3 أعلى الملف. 0 = من غير تفكير داخلي إضافي (أسرع
# وأرخص، مناسب لمهمة توليد JSON منظم). ارفعها (مثلاً 512 أو 1024) لو
# حابب تفكير أعمق قبل كتابة القصة على حساب سرعة/تكلفة أعلى شوية.
THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))
# === تعديل جديد: فيديو كامل فوق 5 دقايق، ريل واحد بس (وليس جزئين) ===
# التصميم القديم (جزئين/ريلين، كل جزء حد أقصى 90 ثانية) اتلغى — دلوقتي
# assemble_video.py بينتج ريل واحد بس (90 ثانية كحد أقصى) مقتطف من أول
# الفيديو الكامل، والفيديو الكامل نفسه مطلوب يكون فوق 5 دقايق (300
# ثانية) عشان يفضل بعد الريل محتوى حقيقي كتير يستاهل زيارة الصفحة له.
# النسبة الموثقة تجريبيًا لسرعة نطق edge-tts هنا (بعد تضمين وقفات
# الجمل PAUSE_AFTER_*): 300 كلمة ≈ 94-150 ثانية (أسرع سيناريو نطق
# ~0.313 ثانية/كلمة، أبطأ سيناريو ~0.5 ثانية/كلمة). عشان نضمن تخطي
# الـ300 ثانية حتى في أسرع سيناريو نطق محتمل، القيمة الافتراضية هنا
# 1050 كلمة (مع MIN_NARRATION_WORDS=970 في الـ workflow كحد أدنى صارم
# — شوف main.yml). لو لاحظت بعد التشغيل إن المدة الفعلية (مطبوعة في
# لوج assemble_video.py: "مدة الفيديو الكامل: X ثانية") أقل أو أكتر
# بكتير مما هو متوقع، عدّل الرقمين في main.yml على أساس النسبة الفعلية
# اللي لاحظتها بدل الاعتماد على التقدير النظري وحده.
TARGET_WORDS = int(os.getenv("TARGET_WORDS", "1050"))
# فحص إضافي (اختياري): لو الـ workflow حاطط MIN_NARRATION_WORDS، أي
# حلقة أقل من الرقم ده بالكلمات تترفض وتتعاد المحاولة. لو المتغير مش
# موجود، الفحص متعطّل.
MIN_NARRATION_WORDS = os.environ.get("MIN_NARRATION_WORDS")
MIN_NARRATION_WORDS = int(MIN_NARRATION_WORDS) if MIN_NARRATION_WORDS else None
# رفعناها من 2 لـ 3 عشان نديله فرصة تصعيد إضافية (شوف build_user_message
# وقسم "تصعيد حقيقي عند قِصر narration" فوق).
# رفعناها من 3 لـ 4: الهدف الجديد (970+ كلمة) أصعب 3 أضعاف تقريبًا من
# القديم (220)، فمحتاج فرص أكتر عشان آلية التصعيد (قصر النص + القطع)
# تقدر توصل بالموديل للنتيجة المطلوبة.
MAX_ATTEMPTS = 4
HISTORY_LIMIT = 8
LENGTH_ESCALATION = 1.5

# آخر N عصور/أماكن اتستخدمت — بتتبعت في الـ prompt عشان نضمن تنويع في
# العصور والشخصيات ومنمنعش نفس العصر يتكرر أكتر من مرة قريبة.
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
        # === ترجمة إنجليزية متوازية، جملة بجملة ===
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
        # === توثيق شرعي/تاريخي إلزامي لكل حلقة ===
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


def to_gemini_schema(schema: dict) -> dict:
    """يحوّل تعريف JSON Schema عادي (lowercase types, زي OpenAI/Groq) إلى
    صيغة Gemini (uppercase types: OBJECT/STRING/ARRAY...، بدون
    additionalProperties لأن Gemini مش بتدعمها). بيتعمل تلقائيًا وقت كل
    استدعاء، عشان EPISODE_SCHEMA فوق يفضل مصدر التعريف الوحيد لو احتجت
    تضيف أو تشيل حقل مستقبلاً."""
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


# ─────────────────────────── مساعدات ───────────────────────────

def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_used_history(limit: int = HISTORY_LIMIT) -> list[str]:
    """يجيب آخر N عناوين عشان الموديل يتجنب التكرار."""
    history_path = SCRIPT_DIR.parent / "state" / "used_clips.json"
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [h.get("title", "") for h in data.get("history", [])][-limit:]


def load_used_regions(limit: int = REGION_HISTORY_LIMIT) -> list[str]:
    """
    يجيب آخر N عصور/أماكن اتستخدمت، عشان نطلب من الموديل يتجنب تكرارها.
    آمن على ملفات used_clips.json القديمة اللي مفيهاش حقل "region" أصلاً
    (هيتجاهلها ببساطة من غير ما يفشل).
    """
    history_path = SCRIPT_DIR.parent / "state" / "used_clips.json"
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    regions = [h.get("region", "") for h in data.get("history", []) if h.get("region")]
    return regions[-limit:]


def load_used_hooks(limit: int = HISTORY_LIMIT) -> list[str]:
    """
    يجيب آخر N هوكات اتستخدمت. الهوك بيوصف الواقعة نفسها بدقة أكتر من
    العنوان (اللي ممكن يتغيّر صياغةً بين حلقة وحلقة عن نفس الواقعة
    بالظبط) — بيُستخدم هنا عشان نمنع الموديل يرجع لنفس الواقعة الشهيرة
    تحت عنوان مختلف. آمن على ملفات used_clips.json القديمة اللي مفيهاش
    حقل "hook" أصلاً.
    """
    history_path = SCRIPT_DIR.parent / "state" / "used_clips.json"
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    hooks = [h.get("hook", "") for h in data.get("history", []) if h.get("hook")]
    return hooks[-limit:]


def looks_truncated(narration: str) -> bool:
    stripped = narration.strip()
    if not stripped:
        return True
    return not stripped.endswith((".", "!", "؟", "?", "…", '"', "”", "»"))


def count_arabic_sentences(narration: str) -> int:
    """بيعدّ الجمل بنفس منطق split_sentences() في generate_voice.py
    (تقسيم بعد نقطة/تعجب/استفهام/حذف)، عشان نتأكد إن عدد عناصر
    narration_en هيطابق عدد الجمل وقت المزامنة الفعلية مع الصوت."""
    import re
    parts = re.split(r"(?<=[.!؟…])\s+", narration.strip())
    return len([part for part in parts if part.strip()])


def validate_episode(episode: dict) -> str | None:
    """يرجّع رسالة الخطأ لو الحلقة فيها مشكلة، أو None لو سليمة."""
    if not REQUIRED_KEYS.issubset(episode.keys()):
        return f"الرد ناقص حقول مطلوبة: {sorted(episode.keys())}"

    narration = str(episode.get("narration", "")).strip()
    if looks_truncated(narration):
        return "نص narration شكله متقطوع (مش منتهي بعلامة ترقيم واضحة)"

    if MIN_NARRATION_WORDS is not None:
        word_count = len(narration.split())
        if word_count < MIN_NARRATION_WORDS:
            return (
                f"نص narration قصير جدًا ({word_count} كلمة، "
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


def log_usage(response, attempt: int) -> None:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return
    print(
        f"   🔢 محاولة {attempt} | مدخل: {usage.prompt_token_count} "
        f"| مخرج: {usage.candidates_token_count} "
        f"| إجمالي: {usage.total_token_count}"
    )


def create_completion(client: genai.Client, system_prompt: str, user_message: str, budget: int):
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=TEMPERATURE,
        max_output_tokens=budget,
        response_mime_type="application/json",
        response_schema=to_gemini_schema(EPISODE_SCHEMA),
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
    )
    return client.models.generate_content(
        model=MODEL, contents=user_message, config=config,
    )


# ─────────────────────────── التوليد ───────────────────────────

def build_user_message(
    recent_titles: list[str],
    recent_regions: list[str],
    recent_hooks: list[str],
    short_attempt_word_count: int | None = None,
    previous_truncated: bool = False,
) -> str:
    # الحد الأدنى الفعّال اللي بنخاطب بيه الموديل: لو فيه MIN_NARRATION_WORDS
    # محدد في الـ workflow، بناخد الأكبر بينه وبين TARGET_WORDS عشان الرسالة
    # متناقضش نفسها (سبق وحصل تعارض بين "حوالي 300" وحد أدنى فعلي أعلى).
    effective_min = TARGET_WORDS
    if MIN_NARRATION_WORDS is not None:
        effective_min = max(effective_min, MIN_NARRATION_WORDS)

    message = (
        "اكتب حلقة جديدة تمامًا.\n\n"
        "⚠️ مهم جدًا بخصوص اللغة: اكتب حقل narration بالكامل باللغة العربية "
        "الفصحى المبسّطة (Modern Standard Arabic) فقط. ممنوع استخدام أي "
        "لهجة عامية أو محلية حتى لو كلمة واحدة.\n\n"
        "⚠️ مهم جدًا جدًا بخصوص التوثيق الشرعي والتاريخي: لازم تكون القصة "
        "مبنية حصريًا على واقعة ثابتة من القرآن الكريم، أو حديث نبوي "
        "صحيح أو حسن، أو مصدر تاريخي إسلامي معتمد ومتفق عليه عند عامة "
        "أهل العلم. ممنوع منعًا باتًا: اختلاق أي حوار أو تفصيلة أو اسم لم "
        "يرد في المصدر الأصلي، استخدام أي رواية إسرائيلية غير موافقة "
        "لما ثبت بالقرآن والسنة الصحيحة، أو الاستناد لحديث ضعيف جدًا أو "
        "موضوع حتى لو كان منتشرًا شعبيًا. لو لست متأكدًا تمامًا من ثبوت "
        "تفصيلة ما، لا تكتبها كحقيقة قطعية — اختر واقعة أخرى أنت متأكد "
        "من ثبوتها. اذكر مصدرك بدقة في source_type وsource_reference.\n\n"
        "⚠️ مهم جدًا بخصوص narration_en: بعد كتابة narration، اكتب مصفوفة "
        "narration_en بحيث يكون كل عنصر فيها هو الترجمة الإنجليزية "
        "الأمينة لجملة واحدة فقط من narration، بنفس الترتيب وبنفس العدد "
        "بالضبط (التقسيم يكون بعد كل نقطة أو علامة تعجب أو علامة "
        "استفهام أو علامات حذف، تمامًا كما تُقسَّم narration نفسها لجمل). "
        "لو عدد الجمل العربية 12 جملة مثلًا، لازم narration_en تحتوي على "
        "12 عنصرًا بالضبط لا أكثر ولا أقل.\n\n"
        "⚠️ مهم جدًا جدًا بخصوص عدم التكرار: ممنوع منعًا باتًا اختيار نفس "
        "الواقعة اللي اتستخدمت في حلقة سابقة، حتى لو غيّرت العنوان أو "
        "الصياغة بالكامل. راجع قائمة الهوكات (وليس العناوين فقط) اللي "
        "اتستخدمت قبل كده تحت — لو الواقعة اللي في بالك بتوصف نفس حادثة "
        "أي هوك منهم، ارفضها فورًا واختار واقعة مختلفة تمامًا.\n\n"
        "⚠️ مهم جدًا بخصوص الهوك: أول جملة في حقل hook لازم تكون مشوّقة "
        "ومباشرة وتخلق فضول فوري (سؤال مثير، أو تفصيلة تاريخية مدهشة "
        "وحقيقية، أو مشهد لحظة الذروة) — من غير أي تهويل يخالف وقار "
        "الموضوع الديني. وبعدين ابدأ narration بنفس الهوك أو صياغة قريبة "
        "جدًا منه كأول جملة فيه، مش بمقدمة عامة بطيئة.\n\n"
        "⚠️ مهم جدًا بخصوص visual_keywords: كل كلمة بحث لازم تكون مشتقة "
        "من تفصيلة ملموسة ومحددة مذكورة فعليًا في narration، وممنوع "
        "منعًا باتًا أي كلمة بحث ممكن تنتج لقطة فيها تجسيد بشري لنبي أو "
        "خليفة راشد أو صحابي بعينه — طبيعة/عمارة إسلامية تاريخية/مخطوطات "
        "وخط عربي/أشخاص مجهولي الهوية بس.\n\n"
        "⚠️ التنويع: اختار عصرًا/شخصية محورية مختلفة عن اللي اتذكرت قبل "
        "كده (تحت). حط وصف المكان والعصر في حقل region.\n\n"
        f"⚠️ الطول: هذا حد أدنى صارم وليس تقريبًا: حقل narration لازم "
        f"يحتوي على {effective_min} كلمة عربية على الأقل، ويفضَّل أن "
        f"يكون حول {TARGET_WORDS}-{int(effective_min * 1.2)} كلمة. لا "
        f"تتوقف عن السرد أو تنتقل للخاتمة إلا بعد أن تتأكد أن ما كتبته "
        f"فعلاً {effective_min} كلمة أو أكثر — أضف تفاصيل حسّية ووصفية "
        "إضافية واردة في المصدر نفسه (المكان، الأجواء، ردود الأفعال) "
        "بدل الاختصار، بدل اختراع أي تفصيلة غير موثقة. النصوص القصيرة "
        "سترفض تلقائيًا.\n"
        "⚠️ عشان تضمن الوصول للطول المطلوب من غير ما تقطع القصة فجأة "
        "أو تستعجل الخاتمة: قسّم القصة ذهنيًا لأربع مراحل متقاربة في "
        "الطول تقريبًا (نحو ربع عدد الكلمات المطلوب لكل مرحلة): "
        "(1) الهوك والتمهيد للموقف، (2) تصعيد أول بتفاصيل حسّية من "
        "المصدر، (3) تصعيد إضافي نحو نقطة الذروة، (4) الذروة والخاتمة "
        "والعبرة. اكتب كل مرحلة بتفصيل كافٍ قبل الانتقال للتي بعدها، "
        "ولا تختصر أي مرحلة عشان توفر وقت أو مساحة.\n"
        "لازم القصة تكون مكتملة: بداية واضحة (الهوك)، تصاعد حقيقي مبني "
        "على المصدر نفسه، وخاتمة فيها عبرة أو حكمة تقفل القصة من غير "
        "تقطيع. لازم آخر جملة في narration تنتهي بعلامة ترقيم واضحة "
        "(نقطة أو علامة تعجب أو علامة استفهام أو علامات حذف) تدل على "
        "اكتمال القصة فعليًا — أي قطع للنص قبل ذلك (حتى لو الـ JSON "
        "نفسه سليم الصياغة) يُعتبر خطأً جسيمًا ويُرفض تلقائيًا.\n"
        "اكتب النص النهائي مباشرة: من غير أي تمهيد أو شرح أو تعليق."
    )
    if recent_titles:
        message += (
            "\n\nالعناوين اللي اتستخدمت قبل كده (تجنب أي تشابه معاها):\n- "
            + "\n- ".join(recent_titles)
        )
    if recent_hooks:
        message += (
            "\n\nالهوكات (ومن ثم الوقائع الفعلية) اللي اتستخدمت قبل كده — "
            "ممنوع اختيار نفس الواقعة حتى بهوك أو عنوان مختلف:\n- "
            + "\n- ".join(recent_hooks)
        )
    if recent_regions:
        message += (
            "\n\nالعصور/الأماكن اللي اتستخدمت قبل كده (اختار عصرًا مختلفًا "
            "عنها):\n- " + "\n- ".join(recent_regions)
        )
    if short_attempt_word_count is not None:
        message += (
            f"\n\n🚨 تحذير عاجل: في محاولة سابقة كتبت narration بـ "
            f"{short_attempt_word_count} كلمة فقط، وهذا غير مقبول إطلاقًا "
            f"لأن الحد الأدنى المطلوب هو {effective_min} كلمة. هذه المرة "
            "اكتب قصة أطول بوضوح: وسّع في وصف المشاهد والأجواء والتفاصيل "
            "الحسّية الواردة في المصدر نفسه (لا تخترع تفاصيل جديدة)، وتأكد "
            f"من أن العدد النهائي للكلمات {effective_min} أو أكثر قبل أن "
            "تُنهي الرد."
        )
    if previous_truncated:
        message += (
            "\n\n🚨 تحذير عاجل: في محاولة سابقة انقطع نص narration فجأة "
            "قبل ما يخلص (ماكانش منتهي بعلامة ترقيم واضحة)، رغم إن الـ "
            "JSON نفسه كان سليم الصياغة — يعني القصة اتقطعت وسط الأحداث "
            "أو حتى وسط جملة بدل ما تتقفل بخاتمة حقيقية. هذه المرة لازم "
            "تخطط للقصة كاملة قبل ما تبدأ تكتب: قسّمها للمراحل الأربع "
            "المذكورة فوق بوضوح في ذهنك، واكتب كل مرحلة بهدوء وتفصيل من "
            "غير استعجال، وتأكد إنك وصلت فعلاً لخاتمة القصة (عبرة أو "
            "حكمة تقفل الأحداث) قبل ما تنهي narration وتنتقل لباقي "
            "حقول الـ JSON."
        )
    return message


def generate_episode() -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("خطأ: لازم تضيف GEMINI_API_KEY في GitHub Secrets")

    client = genai.Client(api_key=api_key)
    system_prompt = load_system_prompt()
    recent_titles = load_used_history()
    recent_regions = load_used_regions()
    recent_hooks = load_used_hooks()

    budget = MAX_OUTPUT_TOKENS
    last_error = "لا يوجد"
    # آخر عدد كلمات طلع قصير، بيُستخدم عشان نبني رسالة تصعيد للمحاولة
    # التالية (شوف قسم "تصعيد حقيقي عند قِصر narration" أعلى الملف).
    last_short_word_count: int | None = None
    # True لو المحاولة اللي فاتت اتقطعت (narration مش منتهي بعلامة
    # ترقيم واضحة)، عشان المحاولة الجاية تتبني بتحذير صريح عن المشكلة
    # دي تحديدًا (شوف previous_truncated في build_user_message).
    last_truncated = False

    print(f"🕌 الموديل: {MODEL} | thinking_budget: {THINKING_BUDGET}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        user_message = build_user_message(
            recent_titles, recent_regions, recent_hooks,
            short_attempt_word_count=last_short_word_count,
            previous_truncated=last_truncated,
        )
        # نصفّر التحذيرات قبل كل محاولة ونعيد ملأها بس لو نفس المشكلة
        # تكررت في المحاولة الحالية، عشان محاولة نجحت في تجاوز مشكلة
        # معينة ميفضلش معاها تحذير قديم غير لازم.
        last_short_word_count = None
        last_truncated = False

        try:
            response = create_completion(client, system_prompt, user_message, budget)
        except Exception as exc:  # noqa: BLE001 — أخطاء شبكة/حصة/حجب أمان من Gemini
            last_error = f"فشل استدعاء Gemini API ({exc})"
            print(f"⚠️ محاولة {attempt}/{MAX_ATTEMPTS}: {last_error} — هعيد المحاولة...")
            continue

        log_usage(response, attempt)

        candidates = getattr(response, "candidates", None) or []
        finish_reason = str(candidates[0].finish_reason) if candidates else ""

        if "MAX_TOKENS" in finish_reason:
            budget = int(budget * LENGTH_ESCALATION)
            last_error = "الرد اتقطع بسبب حد التوكنز (finish_reason=MAX_TOKENS)"
            print(f"⚠️ {last_error} — هرفع السقف لـ {budget} وأعيد المحاولة...")
            last_truncated = True
            continue

        if "SAFETY" in finish_reason or "PROHIBITED" in finish_reason or "BLOCKLIST" in finish_reason:
            last_error = f"الرد اتحجب من Gemini (finish_reason={finish_reason})"
            print(f"⚠️ محاولة {attempt}/{MAX_ATTEMPTS}: {last_error} — هعيد المحاولة...")
            continue

        raw = response.text or ""

        try:
            episode = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_error = f"رد غير صالح JSON ({exc})"
            print(f"⚠️ محاولة {attempt}/{MAX_ATTEMPTS}: {last_error} — هعيد المحاولة...")
            continue

        error = validate_episode(episode)
        if error:
            last_error = error
            # لو سبب الفشل قصر النص تحديدًا، سجّل العدد الفعلي عشان
            # المحاولة الجاية تتبني برسالة تصعيد صريحة بالرقم ده.
            narration_text = str(episode.get("narration", "")).strip()
            if narration_text and "قصير جدًا" in error:
                last_short_word_count = len(narration_text.split())
            if "متقطوع" in error:
                last_truncated = True
            print(f"⚠️ محاولة {attempt}/{MAX_ATTEMPTS}: {last_error} — هعيد المحاولة...")
            continue

        return episode

    sys.exit(
        f"❌ فشل توليد حلقة سليمة بعد {MAX_ATTEMPTS} محاولات. آخر خطأ: {last_error}"
    )


if __name__ == "__main__":
    episode = generate_episode()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ اتكتبت الحلقة: {episode['title']}")
    print(f"   العصر/المكان: {episode.get('region', 'غير محدد')}")
    print(f"   الهوك: {episode.get('hook', '')[:80]}")
    print(f"   المصدر: {episode.get('source_type', '')} — {episode.get('source_reference', '')}")
    print(f"   عدد جمل narration_en: {len(episode.get('narration_en', []))}")
    print(f"   كلمات البحث: {episode['visual_keywords']}")
    print(f"   تلميحات النطق: {episode.get('phonetic_hints', [])}")
