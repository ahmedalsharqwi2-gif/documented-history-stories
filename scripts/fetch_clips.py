"""Fetch historical candidates, then review the actual clip against its era and scene.

Search terms and URL slugs are not evidence. Unrelated fallback is forbidden;
actual video/audio review is mandatory before clips enter the manifest.
"""
import os
import json
import re
import subprocess
import sys
import time
import requests
from pathlib import Path

try:
    from scripts.clip_review import review_clip
except ModuleNotFoundError:
    from clip_review import review_clip
try:
    from scripts.commons_media import image_fallback
except ModuleNotFoundError:
    from commons_media import image_fallback
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from scripts.audio_matching import build_audio_record
except ModuleNotFoundError:
    from audio_matching import build_audio_record

SCRIPT_DIR = Path(__file__).parent
STATE_DIR = SCRIPT_DIR.parent / "state"
EPISODE_PATH = STATE_DIR / "current_episode.json"
USED_CLIPS_PATH = STATE_DIR / "used_clips.json"
CLIPS_DIR = SCRIPT_DIR.parent / "downloaded_clips"

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Bound stock search and inspection before moving to reviewed still images.
MAX_PAGES_TO_TRY = 2
RESULTS_PER_PAGE = 80
CLIPS_PER_KEYWORD = 2
MAX_TOTAL_CLIPS = 24

MIN_DURATION_SECONDS = 4    # نتجنب الكليبات القصيرة جدًا

# عدد محاولات التحميل القصوى لكل كليب (لو انقطع الاتصال أثناء التحميل).
DOWNLOAD_MAX_ATTEMPTS = 2
MAX_CLIP_BLACK_SECONDS = 0.30
BLACK_INTERVAL_RE = re.compile(r"black_start:([0-9.]+).*black_end:([0-9.]+)")

def _build_session() -> requests.Session:
    """Session واحدة لكل الطلبات (بحث + تحميل) مع Retry adapter بيعيد
    المحاولة تلقائيًا على انقطاعات الشبكة العابرة (Connection reset,
    timeouts, أكواد 429/5xx)، بما فيها فشل الـ SSL handshake نفسه —
    ده بالظبط اللي كان بيوقف fetch_clips.py قبل كده."""
    session = requests.Session()
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=False,
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


def search_pexels(
    keyword: str, api_key: str, used_ids: set, count: int,
) -> list[dict]:
    """Return candidates; the actual-video gate decides whether each one is usable."""
    headers = {"Authorization": api_key}
    found: list[dict] = []
    seen_ids_this_search: set[int] = set()

    for page in range(1, MAX_PAGES_TO_TRY + 1):
        if len(found) >= count:
            break

        params = {
            # تحسين فرص الحصول على لقطة خالية من البشر؛ الفلترة الحقيقية
            # تتم لاحقًا ولا تعتمد على نص الاستعلام وحده.
            "query": keyword,
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
            # Period suitability is judged from the actual clip, not a slug.

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
    """Search the requested subject only; never substitute generic landscapes."""
    results = search_pexels(keyword, api_key, used_ids, count)
    if results:
        return results

    print(f"⚠️ No matching clip for {keyword!r}; unrelated fallback is forbidden")
    return []


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


def has_excessive_black_frames(path: Path, max_black_seconds: float = MAX_CLIP_BLACK_SECONDS) -> bool:
    """Reject unusable stock clips before they can create black montage gaps."""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-vf", "blackdetect=d=0.05:pic_th=0.98", "-an", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"ffmpeg could not inspect downloaded clip {path}: {result.stderr[-300:]}")
    intervals = [
        float(end) - float(start)
        for start, end in BLACK_INTERVAL_RE.findall(result.stderr)
    ]
    return sum(intervals) > max_black_seconds


def main():
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("Pexels key absent; using reviewed Commons images")

    episode = load_json(EPISODE_PATH, None)
    if episode is None:
        sys.exit("خطأ: مفيش current_episode.json — شغّل generate_script.py الأول")

    used_data = load_json(USED_CLIPS_PATH, {"pexels_ids_used": [], "history": []})
    used_ids = set(used_data.get("pexels_ids_used", []))

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    fetched_clips = []
    video_attempts = 0

    for keyword in episode["visual_keywords"]:
        if len(fetched_clips) >= MAX_TOTAL_CLIPS:
            print(f"ℹ️ وصلنا للسقف الأقصى ({MAX_TOTAL_CLIPS} كليب) — هنوقف هنا.")
            break

        remaining_budget = MAX_TOTAL_CLIPS - len(fetched_clips)
        wanted = min(CLIPS_PER_KEYWORD, remaining_budget)

        # Fetch extra candidates because black leaders/tails must be rejected
        # before the final montage, while preserving the historical filters.
        results = []
        try:
            results = search_with_fallback(keyword, api_key, used_ids, 2) if api_key and video_attempts < 12 else []
        except requests.RequestException:
            print("Pexels search unavailable; trying Commons")
        if not results:
            print(f"⚠️  مفيش كليبات جديدة لكلمة '{keyword}' — هنجرب صور Commons")

        accepted_for_keyword = 0
        for result in results:
            if accepted_for_keyword >= wanted or len(fetched_clips) >= MAX_TOTAL_CLIPS:
                break
            if video_attempts >= 12:
                break
            video_attempts += 1
            dest_path = CLIPS_DIR / f"clip_{result['id']}.mp4"
            try:
                download_clip(result["url"], dest_path)
            except requests.exceptions.RequestException as exc:
                # كليب واحد فشل بعد كل المحاولات — نتخطاه ونكمل الباقي
                # بدل ما نوقف السكريبت كله ونضيّع كل الكليبات اللي
                # اتنزلت قبل كده في نفس الـ run.
                print(f"❌ فشل تحميل كليب '{keyword}' (Pexels ID: {result['id']}) بعد {DOWNLOAD_MAX_ATTEMPTS} محاولات: {exc} — هنتخطاه")
                continue

            used_ids.add(result["id"])

            try:
                black_frames = has_excessive_black_frames(dest_path)
            except RuntimeError as exc:
                print(f"⚠️ تعذر فحص كليب Pexels {result['id']} — هنرفضه احترازيًا: {exc}")
                dest_path.unlink(missing_ok=True)
                continue
            if black_frames:
                print(f"⚠️ استبعاد كليب Pexels {result['id']}: يحتوي على أكثر من {MAX_CLIP_BLACK_SECONDS:.2f}s إطارات سوداء")
                dest_path.unlink(missing_ok=True)
                continue

            try:
                review = review_clip(dest_path, keyword, str(episode.get("title", "")), historical=True)
                audio_record = build_audio_record(dest_path, override=review["audio_decision"])
                audio_record["semantic_match_review"] = review.get("audio_match", "NOT_REQUIRED")
            except (RuntimeError, ValueError) as exc:
                print(f"⚠️ استبعاد كليب Pexels {result['id']}: تعذر تحليل الصوت الأصلي: {exc}")
                # Keep rejected candidates for byte-bound editorial review.
                continue

            fetched_clips.append({
                "file": str(dest_path),
                "pexels_id": result["id"],
                "keyword": keyword,
                "audio": audio_record,
                "visual_review": review,
            })
            accepted_for_keyword += 1
            print(f"✅ اتنزل كليب لـ '{keyword}' (Pexels ID: {result['id']})")

        if accepted_for_keyword < wanted:
            for item in image_fallback(keyword, str(episode.get("title", "")), CLIPS_DIR,
                                       review_clip, historical=True, limit=wanted-accepted_for_keyword):
                item["audio"] = build_audio_record(Path(item["file"]), override="VOICE ONLY")
                fetched_clips.append(item)

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
