"""
fetch_clips.py
يبحث في Pexels عن كليبات فيديو حقيقية بناءً على visual_keywords،
ويتجنب أي كليب اتستخدم قبل كده باستخدام state/used_clips.json.

يحتاج: متغير بيئة PEXELS_API_KEY (مجاني من https://www.pexels.com/api/)

=== تعديل جديد: قيد العصر التاريخي واستبعاد اللقطات المعاصرة ===
القصص هنا تاريخية إسلامية، وأي لقطة فيها عنصر عصري حديث (سيارات، مباني
زجاجية حديثة، هواتف ذكية، طرق سريعة، إلخ) بتكسر الإحساس بالزمن وتبقى
غير مناسبة تمامًا حتى لو طابقت كلمة البحث تقنيًا.

⚠️ تنويه تقني صادق: Pexels API مفيهوش حقل "tags" أو وصف نصي منفصل
لفيديوهاته (بعكس الصور اللي عندها tags)، ومفيش أي عامل استبعاد
(exclude operator) في البحث نفسه. الفلترة هنا بتعتمد بشكل عملي على
تحليل الـ slug الوصفي الموجود جوه رابط كل فيديو (video["url"]، زي
".../video/aerial-view-of-a-city-at-night-1093662/") ومقارنته بقائمة
MODERN_EXCLUDE_TERMS. ده حل تقريبي معقول لكنه مش مضمون بالكامل: ممكن
يفوت كليب عصري لو الرابط مالوش وصف كافٍ، أو يستبعد كليب بريء بالغلط
لو الوصف فيه كلمة متشابهة. مفيش بديل أدق متاح فعليًا من الـ API نفسه.

منطق البحث صار صارمًا لكل كلمة بحث:
  1) إضافة "no people" إلى استعلام Pexels لتحسين النتائج الخالية من البشر.
  2) رفض أي كليب يظهر في وصف رابطه مؤشر على بشر، نساء، رجال، أطفال، أو
     أي مظهر بشري.
  3) رفض أي كليب يظهر في وصف رابطه مؤشر على عنصر حديث/معاصر.
  4) رفض الكليب إذا لم يوجد له وصف قابل للفحص في رابط Pexels، لأن عدم القدرة
     على التحقق لا يُعتبر موافقة.
  5) عند عدم وجود نتائج، البحث فقط في قائمة لقطات تاريخية عامة خالية من البشر
     وبنفس الفلترة الصارمة. لا توجد أبدًا نتيجة احتياطية غير مفلترة.

=== تعديل سابق: تسجيل region في الهيستوري ===
كان الهيستوري بيسجّل "title" بس مع كل حلقة. دلوقتي بيسجّل "region" كمان
(المنطقة/الدولة اللي القصة منها، جاية من current_episode.json اللي
generate_script.py بيكتبه) — عشان load_used_regions() في generate_script.py
تقدر فعليًا تمنع تكرار نفس المنطقة الجغرافية في حلقات متتالية. لو الحلقة
القديمة اتعملت قبل التعديل ده ومفيهاش region، بيتسجل النص فاضي بدل ما
يحصل خطأ.

تعديلات سابقة على النسخة دي:
- بدل ما ينزّل كليب واحد بس لكل كلمة بحث، بقى بينزّل لحد CLIPS_PER_KEYWORD
  كليبات لكل كلمة (بدل ما كانت CLIPS_PER_KEYWORD معرّفة بس مش مستخدمة فعليًا)،
  عشان يبقى فيه أكبر عدد ممكن من الفيديوهات المتنوعة اللي فعلاً بتعبّر عن
  أحداث القصة، بدل الاعتماد على كليب واحد يتكرر أو يتمط طول الحلقة.
- بيدور على صفحات أكتر (MAX_PAGES_TO_TRY) وبنتائج أكتر لكل صفحة (per_page)
  عشان يقدر يلاقي عدد كافي من الكليبات الجديدة (الغير مستخدمة قبل كده)
  لكل كلمة بحث.
- فيه سقف إجمالي (MAX_TOTAL_CLIPS) يمنع تنزيل عدد ضخم جدًا من الكليبات في
  حلقة واحدة (تحكم في الوقت والمساحة)، قابل للتعديل براحتك.

تحمّل انقطاعات الشبكة العابرة (زي ConnectionResetError اللي كانت
بتوقف الـ run كله وتضيّع كل الكليبات اللي اتنزلت قبلها):
- كل طلبات الشبكة (بحث وتحميل) بتعدي دلوقتي على `requests.Session` معاها
  `Retry` adapter بيعيد المحاولة تلقائيًا على مستوى الـ HTTP connection
  نفسه (بيغطي حتى فشل الـ SSL/TLS handshake).
- `download_clip` كمان عندها طبقة retry يدوية فوق كده (مع مسح أي ملف
  ناقص قبل كل محاولة جديدة)، عشان تتعامل مع أخطاء زي
  ChunkedEncodingError اللي ممكن تحصل بعد ما جزء من الملف اتكتب فعلاً.
- في main()، لو كليب واحد فشل بعد كل المحاولات، بنتخطاه ونكمل باقي
  الكليبات بدل ما نوقف السكريبت كله ونضيّع اللي اتنزل قبل كده.
"""
import os
import json
import re
import sys
import time
import requests
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCRIPT_DIR = Path(__file__).parent
STATE_DIR = SCRIPT_DIR.parent / "state"
EPISODE_PATH = STATE_DIR / "current_episode.json"
USED_CLIPS_PATH = STATE_DIR / "used_clips.json"
CLIPS_DIR = SCRIPT_DIR.parent / "downloaded_clips"

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

MAX_PAGES_TO_TRY = 10       # نبحث في صفحات أكثر قبل إعلان عدم وجود نتائج جديدة
RESULTS_PER_PAGE = 80       # الحد العملي الأعلى لنتائج Pexels في الصفحة

# أقصى عدد كليبات نحاول نجيبه لكل كلمة بحث (بدل كليب واحد بس زي الأول).
CLIPS_PER_KEYWORD = 12

# سقف إجمالي لعدد الكليبات في الحلقة الواحدة، عشان التنزيل ميطولش أو
# ياكل مساحة/رصيد API أكتر من اللازم. غيّره براحتك.
# حلقة 5–6 دقائق تحتاج عادةً 75–110 لقطة عند تغيير المشهد كل 3–4 ثوانٍ.
# السقف 160 يتيح تنوعًا كبيرًا للحلقات الأطول، بينما يظل عمليًا من ناحية
# زمن التنزيل ومساحة GitHub Actions. العدد الفعلي قد يكون أقل حسب النتائج
# الجديدة المتاحة لكل كلمة بحث.
MAX_TOTAL_CLIPS = 160

MIN_DURATION_SECONDS = 4    # نتجنب الكليبات القصيرة جدًا

# عدد محاولات التحميل القصوى لكل كليب (لو انقطع الاتصال أثناء التحميل).
DOWNLOAD_MAX_ATTEMPTS = 4

# كلمات دالة على عناصر عصرية/معاصرة. لو ظهرت في الوصف المستخرج من رابط
# الكليب (شوف clip_description_slug)، نستبعد الكليب فورًا حتى لو طابق
# كلمة البحث الأصلية، لأنه هيكسر الإحساس بالعصر التاريخي للحلقة. القائمة
# تقريبية وقابلة للتوسيع — أضف أي كلمة لاحظت تسربها في لقطات سابقة.
MODERN_EXCLUDE_TERMS = {
    "car", "cars", "traffic", "highway", "freeway", "smartphone", "phone",
    "iphone", "laptop", "computer", "modern", "skyline", "skyscraper",
    "neon", "airplane", "aircraft", "jet", "helicopter", "train", "subway",
    "metro", "office", "gym", "fitness", "mall", "supermarket", "wifi",
    "drone", "electric", "bicycle", "motorcycle", "bus", "truck", "stadium",
    "concert", "nightclub", "television", "internet", "led", "billboard",
    "apartment", "elevator", "escalator", "shopping", "parking", "urban",
    "downtown", "contemporary", "tourist", "tourists", "selfie", "camera",
    "studio", "microphone", "headphones", "game", "gaming", "keyboard",
    "monitor", "screen", "app", "social-media", "credit-card", "atm",
    "modern-day", "modern-city", "modern-building", "glass-building",
    "skyscrapers", "road", "street", "crosswalk", "suburban", "city-center",
    "airport", "railway", "bus-stop", "factory", "warehouse", "construction",
    "plastic", "neon-light", "streetlight", "power-line", "wind-turbine",
}

# قاعدة أمان صارمة: لا نسمح بظهور أي إنسان، وليس النساء فقط.
# الفلترة تعتمد على الوصف الموجود في رابط Pexels، وليست تحليلًا بصريًا كاملًا.
HUMAN_EXCLUDE_TERMS = {
    "person", "people", "human", "humans", "man", "men", "male",
    "woman", "women", "female", "girl", "girls", "lady", "ladies",
    "mother", "father", "family", "child", "children", "baby", "babies",
    "boy", "boys", "face", "faces", "portrait", "body", "crowd", "crowds",
    "people-walking", "walking", "standing", "sitting", "running", "walking-person",
    "worshipper", "worshippers", "prayer", "praying", "pilgrim", "pilgrims",
    "soldier", "soldiers", "warrior", "warriors", "rider", "riders",
    "worker", "workers", "farmer", "farmers", "merchant", "merchants",
    "king", "queen", "prince", "princess", "prophet", "historian",
    "actor", "actress", "dancer", "model", "hand", "hands", "feet",
    "silhouette", "shadow", "statue", "sculpture", "human-figure",
}

# إذا لم نستطع فحص وصف الرابط، نرفض الكليب بدل قبول لقطة غير مضمونة.
REJECT_UNVERIFIABLE_SLUG = True

# كلمات بحث احتياطية دينية/إسلامية عامة، مستخدمة فقط لو فشل البحث
# بالكلمة الأصلية (حتى بعد إلغاء الفلترة الصارمة) — يعني آخر خط دفاع
# قبل ما نضطر نتخطى الكلمة دي خالص. كلها كلمات محايدة زمنيًا (عمارة/
# طبيعة/مخطوطات) عشان تناسب أي عصر إسلامي تقريبًا.
HISTORICAL_FALLBACK_KEYWORDS = [
    "ancient stone fortress empty no people",
    "historic map parchment close up no people",
    "old wooden sailing ship ocean no people",
    "ancient battlefield landscape no people",
    "desert dunes historic atmosphere no people",
    "old manuscript writing close up no people",
    "ancient city ruins empty no people",
    "historic mountain pass landscape no people",
    "old compass and map close up no people",
    "ancient weapons museum display no people",
]


def _build_session() -> requests.Session:
    """Session واحدة لكل الطلبات (بحث + تحميل) مع Retry adapter بيعيد
    المحاولة تلقائيًا على انقطاعات الشبكة العابرة (Connection reset,
    timeouts, أكواد 429/5xx)، بما فيها فشل الـ SSL handshake نفسه —
    ده بالظبط اللي كان بيوقف fetch_clips.py قبل كده."""
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=2,          # 2s, 4s, 8s, 16s, 32s بين المحاولات
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_SESSION = _build_session()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clip_description_slug(video: dict) -> str:
    """يستخرج الوصف النصي التقريبي من رابط الفيديو نفسه على Pexels (اللي
    بيحتوي عادةً على كلمات وصفية زي
    ".../video/aerial-view-of-a-city-at-night-1093662/")، عشان نقدر
    نفحص الكليب بحثًا عن كلمات دالة على العصر الحديث حتى لو كلمة البحث
    نفسها كانت بريئة. لو الرابط مالوش وصف واضح، بترجع نص فاضي (يعني مفيش
    فلترة هتحصل عليه — الفلترة تحفّظية، مش قاطعة)."""
    url = str(video.get("url", ""))
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    # نشيل الرقم التسلسلي في آخر الـ slug (زي "-1093662")
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-", " ").lower()


def contains_forbidden_human(video: dict) -> bool:
    """ترفض أي كليب يصف رابطه وجود بشر أو هيئة بشرية."""
    description = clip_description_slug(video)
    if not description:
        return REJECT_UNVERIFIABLE_SLUG

    words = set(description.split())
    return any(term in words or term in description for term in HUMAN_EXCLUDE_TERMS)


def looks_contemporary(video: dict) -> bool:
    """True لو الوصف المستخرج من رابط الكليب فيه أي كلمة من
    MODERN_EXCLUDE_TERMS. شوف تنويه الدقة في أعلى الملف."""
    description = clip_description_slug(video)
    if not description:
        return False
    words = set(description.split())
    return any(term in words or term in description for term in MODERN_EXCLUDE_TERMS)


def search_pexels(
    keyword: str, api_key: str, used_ids: set, count: int,
) -> list[dict]:
    """يرجّع كليبات جديدة قابلة للتحقق فقط: بلا بشر وبلا عناصر حديثة.
    لا توجد نتيجة غير مفلترة؛ عدم القدرة على التحقق يعني الرفض."""
    headers = {"Authorization": api_key}
    found: list[dict] = []
    seen_ids_this_search: set[int] = set()

    for page in range(1, MAX_PAGES_TO_TRY + 1):
        if len(found) >= count:
            break

        params = {
            # تحسين فرص الحصول على لقطة خالية من البشر؛ الفلترة الحقيقية
            # تتم لاحقًا ولا تعتمد على نص الاستعلام وحده.
            "query": f"{keyword} no people",
            "orientation": "landscape",  # المصدر الأساسي للفيديو الكامل 16:9؛ الشورتس تُقص لاحقًا
            "per_page": RESULTS_PER_PAGE,
            "page": page,
        }
        resp = _SESSION.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        videos = data.get("videos", [])
        if not videos:
            break  # مفيش نتائج تانية عن الكلمة دي

        for video in videos:
            if len(found) >= count:
                break
            if video["id"] in used_ids or video["id"] in seen_ids_this_search:
                continue
            if video["duration"] < MIN_DURATION_SECONDS:
                continue
            # ممنوع أي شخص: امرأة، رجل، طفل، وجه، ظل أو تمثال بشري.
            if contains_forbidden_human(video):
                continue

            # ممنوع أي عنصر حديث أو معاصر لا يطابق الحقبة التاريخية.
            if looks_contemporary(video):
                continue

            # تجاهل أي نتيجة لا تحتوي ملفات فيديو قابلة للتنزيل.
            if not video.get("video_files"):
                continue

            # اختار أفضل جودة فيديو ملف (HD لو موجود)
            video_files = sorted(
                video["video_files"],
                key=lambda f: f.get("height", 0),
                reverse=True,
            )
            hd_files = [f for f in video_files if 720 <= f.get("height", 0) <= 1080]
            chosen_file = hd_files[0] if hd_files else video_files[0]

            found.append({
                "id": video["id"],
                "url": chosen_file["link"],
                "keyword": keyword,
                "duration": video["duration"],
            })
            seen_ids_this_search.add(video["id"])

    return found


def search_with_fallback(
    keyword: str, api_key: str, used_ids: set, count: int,
) -> list[dict]:
    """بحث صارم بلا أي fallback غير مفلتر.

    نبحث بالكلمة الأصلية أولًا، ثم نستخدم كلمات عامة خالية من البشر فقط.
    كل المسارات تمر بنفس فحص البشر والعصر الحديث.
    """
    results = search_pexels(keyword, api_key, used_ids, count)
    if results:
        return results

    print(
        f"⚠️  '{keyword}': لا توجد لقطة موثوقة مطابقة — "
        "سيتم البحث في لقطات تاريخية عامة خالية من البشر"
    )

    collected: list[dict] = []
    already_used_this_call = set(used_ids)
    for fallback_keyword in HISTORICAL_FALLBACK_KEYWORDS:
        if len(collected) >= count:
            break
        remaining = count - len(collected)
        fb_results = search_pexels(
            fallback_keyword, api_key, already_used_this_call, remaining,
        )
        for item in fb_results:
            already_used_this_call.add(item["id"])
        collected.extend(fb_results)

    if collected:
        print(f"   ↳ اتلقى {len(collected)} كليب بديل موثوق وخالٍ من البشر")
    return collected


def download_clip(url: str, dest: Path, max_attempts: int = DOWNLOAD_MAX_ATTEMPTS):
    """بتحمّل الكليب مع إعادة محاولة يدوية فوق retry الـ Session نفسها،
    عشان تغطي أخطاء زي ChunkedEncodingError اللي ممكن تحصل بعد ما جزء من
    الملف اتكتب فعلاً على الديسك (مش مجرد فشل في الاتصال الأولي). بنمسح
    أي ملف ناقص قبل كل محاولة جديدة عشان ميفضلش كليب معطوب على الديسك."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = _SESSION.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as exc:
            last_error = exc
            dest.unlink(missing_ok=True)
            if attempt < max_attempts:
                wait = 3 * attempt
                print(f"⚠️ فشلت محاولة تحميل الكليب {attempt}/{max_attempts} ({exc})؛ إعادة محاولة بعد {wait}s")
                time.sleep(wait)

    raise last_error


def main():
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        sys.exit("خطأ: لازم تضيف PEXELS_API_KEY في GitHub Secrets")

    episode = load_json(EPISODE_PATH, None)
    if episode is None:
        sys.exit("خطأ: مفيش current_episode.json — شغّل generate_script.py الأول")

    used_data = load_json(USED_CLIPS_PATH, {"pexels_ids_used": [], "history": []})
    used_ids = set(used_data.get("pexels_ids_used", []))

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    fetched_clips = []

    for keyword in episode["visual_keywords"]:
        if len(fetched_clips) >= MAX_TOTAL_CLIPS:
            print(f"ℹ️ وصلنا للسقف الأقصى ({MAX_TOTAL_CLIPS} كليب) — هنوقف هنا.")
            break

        remaining_budget = MAX_TOTAL_CLIPS - len(fetched_clips)
        wanted = min(CLIPS_PER_KEYWORD, remaining_budget)

        results = search_with_fallback(keyword, api_key, used_ids, wanted)
        if not results:
            print(f"⚠️  مفيش كليبات جديدة لكلمة '{keyword}' حتى بعد كل محاولات البديل — هنتخطاها")
            continue

        for result in results:
            dest_path = CLIPS_DIR / f"clip_{len(fetched_clips):02d}.mp4"
            try:
                download_clip(result["url"], dest_path)
            except requests.exceptions.RequestException as exc:
                # كليب واحد فشل بعد كل المحاولات — نتخطاه ونكمل الباقي
                # بدل ما نوقف السكريبت كله ونضيّع كل الكليبات اللي
                # اتنزلت قبل كده في نفس الـ run.
                print(f"❌ فشل تحميل كليب '{keyword}' (Pexels ID: {result['id']}) بعد {DOWNLOAD_MAX_ATTEMPTS} محاولات: {exc} — هنتخطاه")
                continue

            used_ids.add(result["id"])

            fetched_clips.append({
                "file": str(dest_path),
                "pexels_id": result["id"],
                "keyword": keyword,
            })
            print(f"✅ اتنزل كليب لـ '{keyword}' (Pexels ID: {result['id']})")

    if not fetched_clips:
        sys.exit("خطأ: مفيش ولا كليب واحد اجتاز فلترة البشر والعصر التاريخي — راجع الكلمات المفتاحية أو رصيد الـ API")

    # حدّث ملف التتبع
    used_data["pexels_ids_used"] = list(used_ids)
    used_data["history"].append({
        "title": episode["title"],
        # الهوك بيوصف الحادثة الواقعية نفسها بدقة أكتر من العنوان (اللي
        # ممكن يتغيّر صياغةً بين حلقة وحلقة عن نفس الحادثة بالظبط). بيُقرأ
        # لاحقًا في load_used_hooks() جوه generate_script.py عشان نمنع
        # الموديل يرجع لنفس الواقعة الشهيرة حتى لو غيّر صياغة العنوان.
        "hook": episode.get("hook", ""),
        # المنطقة/الدولة اللي القصة منها (من generate_script.py) — بتُقرأ
        # لاحقًا في load_used_regions() جوه generate_script.py عشان نمنع
        # تكرار نفس المنطقة الجغرافية في حلقات متتالية. .get() بأمان عشان
        # حلقات قديمة اتعملت قبل إضافة الحقل ده ميحصلش فيها KeyError.
        "region": episode.get("region", ""),
        "voice_profile": episode.get("voice_profile", ""),
        "clips": [c["pexels_id"] for c in fetched_clips],
    })
    # خلي الهيستوري آخر 100 حلقة بس عشان الملف مايكبرش أوي
    used_data["history"] = used_data["history"][-100:]
    USED_CLIPS_PATH.write_text(
        json.dumps(used_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # سجّل قائمة الكليبات عشان assemble_video.py يستخدمها
    (STATE_DIR / "fetched_clips.json").write_text(
        json.dumps(fetched_clips, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n🎬 إجمالي الكليبات الجاهزة: {len(fetched_clips)}")


if __name__ == "__main__":
    main()
