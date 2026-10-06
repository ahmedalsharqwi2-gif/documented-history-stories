"""
assemble_video.py

ينتج أصلين من نفس الحلقة:

1) فيديو كامل أفقي 16:9:
   output/final_video_full.mp4

2) ريل واحد رأسي 9:16، مقتطف من أول الفيديو الكامل ويتوقف قبل النهاية/الحل:
   output/short_1_youtube.mp4
   output/short_1_facebook.mp4
   output/short_1_instagram.mp4

مصدر الحقيقة للصوت والترجمة العربية هو current_episode.json. يدعم الملف الحقول الجديدة:

{
  "final_audio": "downloaded_clips/narration.mp3",
  "subtitles": "downloaded_clips/narration.ass",
  "shorts": [
    {"start_seconds": 0, "end_seconds": 75}
  ]
}

إذا لم توجد قائمة shorts، يتم إنشاء ريل واحد تلقائيًا من بداية الفيديو،
مع ترك AUTO_END_MARGIN_SECONDS في نهاية الحلقة حتى لا يصل المقتطف إلى الحل.

مهم: مدة 90 ثانية حد للريل فقط، وليست حدًا للفيديو الكامل.

=== تعديل جديد: ريل واحد بس بدل شورتين ===
كان بيتنتج شورتان (short_1 من البداية، short_2 من المنتصف تقريبًا).
المطلوب دلوقتي ريل واحد بس، يبدأ من أول الفيديو مباشرة، مع تنويه في
آخره يوجّه المشاهد لمشاهدة بقية الفيديو على الصفحة. الحل: DEFAULT_SHORT_COUNT
بقت 1 بدل 2 — default_short_specs() أصلًا كانت بتدعم أي عدد، فمع القيمة
الجديدة بترجع ريل واحد بس يبدأ من الثانية صفر (start=0) ويمتد لحد
MAX_SHORT_DURATION_SECONDS أو حد الهامش قبل النهاية، أيهما أصغر.

=== تخطيط النص في المنطقة الآمنة ===
ترجمة السرد في أصل 16:9 محاذاة أسفل-وسط بهامش سفلي 70px، بعيدًا عن حواف
الفيديو. يظهر CTA في مسار علوي ثانٍ بهامش 620px في الريل، كي لا يتداخل
مع سطر الترجمة خلال النهاية.
"""

from __future__ import annotations
import os

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from scripts.media_audio import add_topic_soundtrack

try:
    from scripts.clip_review import review_clip
    from scripts.media_audio import normalized_audio_args, ducking_filters
except ModuleNotFoundError:
    from clip_review import review_clip
    from media_audio import normalized_audio_args, ducking_filters

try:
    from scripts.audio_matching import validate_manifest
except ModuleNotFoundError:
    from audio_matching import validate_manifest

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
STATE_DIR = ROOT_DIR / "state"
CLIPS_DIR = ROOT_DIR / "downloaded_clips"
OUTPUT_DIR = ROOT_DIR / "output"
SUBTITLES_PATH = CLIPS_DIR / "narration.ass"

FETCHED_CLIPS_PATH = STATE_DIR / "fetched_clips.json"
EPISODE_PATH = STATE_DIR / "current_episode.json"

# الفيديو الكامل: أفقي 16:9
FULL_WIDTH = 1920
FULL_HEIGHT = 1080

# الريل: رأسي 9:16
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
MAX_SHORT_DURATION_SECONDS = 90.0
# ريل واحد بس (كان 2 قبل كده) — يبدأ من أول الفيديو مباشرة. شوف شرح
# "ريل واحد بس بدل شورتين" أعلى الملف.
DEFAULT_SHORT_COUNT = 1
AUTO_END_MARGIN_SECONDS = 8.0
CTA_DURATION_SECONDS = 6.0
REEL_CTA_TOP_MARGIN = 620
FPS = 24

PLATFORM_CTA = {
    "youtube": "شاهد الفيديو الكامل\nعلى قناة YouTube",
    "facebook": "شاهد الفيديو الكامل\nعلى صفحتنا",
    "instagram": "شاهد الفيديو الكامل\nعلى صفحتنا",
}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "❌ فشل الأمر:\n"
            + " ".join(command)
            + "\n\n"
            + result.stderr
        )
    return result


def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(f"❌ تعذر قراءة مدة الملف: {path}")


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    # المسارات القديمة قد تكون نسبية إلى جذر المشروع أو إلى scripts/.
    candidates = [ROOT_DIR / path, SCRIPT_DIR / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return ROOT_DIR / path


def normalize_clip(input_path: Path, output_path: Path, duration: float, audio_decision: str = "VOICE ONLY") -> None:
    """Render only explicitly approved embedded audio, with a stable stream layout."""
    extra, mapping = normalized_audio_args(input_path, audio_decision.startswith("ORIGINAL AUDIO"))
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(input_path), *extra,
         "-t", f"{duration:.3f}", "-vf",
         f"scale={FULL_WIDTH}:{FULL_HEIGHT}:force_original_aspect_ratio=increase,crop={FULL_WIDTH}:{FULL_HEIGHT},setsar=1,fps={FPS}",
         "-map", "0:v:0", *mapping, "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path)])


def concat_clips(paths: list[Path], output_path: Path, list_path: Path) -> None:
    if not paths:
        raise RuntimeError("❌ لا توجد مقاطع صالحة لتجميعها.")

    list_path.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in paths) + "\n",
        encoding="utf-8",
    )
    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ])


def _ass_timestamp(value: str) -> float:
    """Convert an ASS timestamp (H:MM:SS.cc) to seconds."""
    hours, minutes, seconds = value.strip().split(":")
    whole, fraction = (seconds.split(".", 1) + ["0"])[:2]
    return int(hours) * 3600 + int(minutes) * 60 + int(whole) + int(fraction[:2].ljust(2, "0")) / 100


def _text_words(value: str) -> list[str]:
    value = re.sub(r"\{[^}]*\}", "", value or "").replace(r"\N", " ")
    return re.findall(r"[\w\u0600-\u06ff]+", value, flags=re.UNICODE)


def _narration_sentences(narration: str) -> list[str]:
    """Split narration at its spoken sentence boundaries, preserving text."""
    return [part.strip() for part in re.split(r"(?<=[.!؟])\s+", narration.strip()) if part.strip()]


def _subtitle_events(subtitles: Path | None) -> list[dict]:
    """Read timed ASS dialogue events as the authoritative spoken timeline."""
    if not subtitles or not subtitles.exists():
        return []
    events = []
    for line in subtitles.read_text(encoding="utf-8").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            continue
        try:
            start, end = _ass_timestamp(fields[1]), _ass_timestamp(fields[2])
        except (ValueError, IndexError):
            continue
        words = _text_words(fields[9])
        if words and end > start:
            events.append({"start": start, "end": end, "words": len(words)})
    return events


def _sentence_windows(narration: str, subtitles: Path | None, total: float) -> list[dict]:
    """Return one [start, end] window per sentence using subtitle timings."""
    sentences = _narration_sentences(narration)
    if not sentences:
        return []
    events = _subtitle_events(subtitles)
    counts = [max(1, len(_text_words(sentence))) for sentence in sentences]
    if not events:
        total_words = sum(counts)
        cursor = 0.0
        windows = []
        for index, count in enumerate(counts):
            end = total if index == len(counts) - 1 else cursor + total * count / total_words
            windows.append({"start": cursor, "end": max(end, cursor + 0.05)})
            cursor = end
        return windows

    windows = []
    event_index = 0
    for sentence_index, count in enumerate(counts):
        start = events[min(event_index, len(events) - 1)]["start"]
        consumed = 0
        last_end = start
        while event_index < len(events) and consumed < count:
            event = events[event_index]
            consumed += event["words"]
            last_end = event["end"]
            event_index += 1
        if sentence_index == len(counts) - 1:
            last_end = total
        windows.append({"start": start, "end": min(total, max(last_end, start + 0.05))})
    windows[-1]["end"] = total
    for index in range(1, len(windows)):
        windows[index]["start"] = max(windows[index]["start"], windows[index - 1]["end"])
        windows[index]["end"] = max(windows[index]["end"], windows[index]["start"] + 0.05)
    return windows


def build_scene_plan(
    clips: list[dict], episode: dict, subtitles: Path | None, audio_duration: float,
) -> list[dict]:
    """Bind every narration sentence to a timed, semantically labelled clip.

    The prompt supplies 8–10 ordered visual keywords rather than one keyword
    per sentence. Keywords are therefore mapped proportionally across the
    narration, while an unused clip from the matching keyword is preferred.
    """
    narration = str(episode.get("narration", ""))
    sentences = _narration_sentences(narration)
    keywords = [str(item).strip() for item in episode.get("visual_keywords", []) if str(item).strip()]
    if not sentences or not keywords or not clips:
        return []
    windows = _sentence_windows(narration, subtitles, audio_duration)
    by_keyword: dict[str, list[dict]] = defaultdict(list)
    for clip in clips:
        by_keyword[str(clip.get("keyword", "")).strip().casefold()].append(clip)
    used: set[tuple[str, str]] = set()
    plan = []
    for index, sentence in enumerate(sentences):
        keyword = keywords[min(len(keywords) - 1, int(index * len(keywords) / len(sentences)))]
        pool = by_keyword.get(keyword.casefold(), [])
        clip = next((item for item in pool if (str(item.get("id", "")), str(item.get("file", ""))) not in used), None)
        if clip is None:
            # Reuse only a clip matching this sentence's keyword.
            clip = pool[0] if pool else None
        illustrative_fallback = False
        if clip is None and os.getenv("QUALITY_GATES_BLOCKING", "true").lower() != "true":
            clip = clips[index % len(clips)]
            illustrative_fallback = True
            print(f"WARNING: sentence {index + 1} uses an illustrative clip from this episode; exact match unavailable: {keyword}")
        if clip is None:
            raise RuntimeError(f"No matching clip for sentence {index + 1}: {keyword}")
        used.add((str(clip.get("id", "")), str(clip.get("file", ""))))
        window = windows[min(index, len(windows) - 1)]
        plan.append({
            "sentence_index": index,
            "sentence": sentence,
            "keyword": keyword,
            "illustrative_fallback": illustrative_fallback,
            "source_keyword": clip.get("keyword", ""),
            "clip_id": clip.get("pexels_id", clip.get("id")),
            "file": clip["file"],
            "audio_decision": clip.get("audio", {}).get("decision", "VOICE ONLY"),
            "start_seconds": round(window["start"], 3),
            "end_seconds": round(window["end"], 3),
            "duration_seconds": round(max(window["end"] - window["start"], 0.05), 3),
        })
    return plan


def subtitle_filter(subtitles: Path | None) -> str | None:
    if not subtitles or not subtitles.exists():
        return None
    path = str(subtitles.resolve()).replace("\\", "/").replace(":", "\\:")
    return f"subtitles='{path}'"


def make_vertical_subtitles(source: Path, output: Path) -> Path:
    """Move narration captions to the upper safe lane for 9:16 reels."""
    if not source.exists():
        raise RuntimeError(f"ملف الترجمة غير موجود: {source}")
    lines = source.read_text(encoding="utf-8").splitlines()
    rewritten = []
    for line in lines:
        if line.startswith("PlayResX:"):
            line = f"PlayResX: {SHORT_WIDTH}"
        elif line.startswith("PlayResY:"):
            line = f"PlayResY: {SHORT_HEIGHT}"
        elif line.startswith("Style: Caption,"):
            fields = line.split(",")
            if len(fields) >= 23:
                fields[18] = "8"       # top-center alignment
                fields[21] = "160"     # safe top margin for 9:16
                line = ",".join(fields)
        rewritten.append(line)
    output.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    return output


def mix_documentary_audio(source_video: Path, final_audio: Path, duration: float, output_path: Path) -> Path:
    """Keep embedded clip audio and duck it beneath clear narration."""
    # Generic page turns and nature sounds can invent events absent from the
    # narrative. Use only the actual approved scene audio here.
    filters = ducking_filters("[1:a]", "[0:a]")
    filters.append("[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95:level=disabled[a]")
    run(["ffmpeg", "-y", "-i", str(source_video), "-i", str(final_audio),
         "-filter_complex", ";".join(filters), "-map", "[a]", "-t", f"{duration:.3f}",
         "-c:a", "libmp3lame", "-b:a", "192k", str(output_path)])
    add_topic_soundtrack(output_path, final_audio, duration, "history")
    return output_path


def add_audio_and_subtitles(
    video_path: Path,
    final_audio: Path,
    subtitles: Path | None,
    output_path: Path,
) -> None:
    filters = []
    sub_filter = subtitle_filter(subtitles)
    if sub_filter:
        filters.append(sub_filter)

    mixed_audio = output_path.with_suffix(".mixed.mp3")
    mix_documentary_audio(video_path, final_audio, probe_duration(final_audio), mixed_audio)
    command = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(mixed_audio),
    ]
    if filters:
        command += ["-vf", ";".join(filters), "-c:v", "libx264",
                    "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p"]
    else:
        # Normalized H.264 clips need no second video encode when only audio changes.
        command += ["-c:v", "copy"]
    command += [
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", f"{probe_duration(mixed_audio):.3f}",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        run(command)
    finally:
        mixed_audio.unlink(missing_ok=True)


def build_full_video(
    clips: list[dict],
    final_audio: Path,
    subtitles: Path | None,
    output_path: Path,
    episode: dict | None = None,
) -> float:
    """يبني الحلقة الكاملة مع مشهد زمني مقابل لكل جملة صوتية."""
    audio_duration = probe_duration(final_audio)
    if audio_duration <= 0:
        raise RuntimeError("❌ مدة الصوت النهائي غير صالحة.")

    if not clips:
        raise RuntimeError("No clips to assemble")
    for clip in clips:
        reviewed = review_clip(resolve_path(clip["file"]), str(clip.get("keyword", "")), str((episode or {}).get("title", "")), historical=True)
        if reviewed["audio_decision"] != clip.get("audio", {}).get("decision"):
            raise ValueError("Audio decision differs from byte-bound clip review")
    scene_plan = build_scene_plan(clips, episode or {}, subtitles, audio_duration) if episode else []
    if scene_plan:
        (STATE_DIR / "scene_plan.json").write_text(
            json.dumps(scene_plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        # Backward compatibility for older episodes without narration metadata.
        duration_per_clip = max(audio_duration / len(clips), 2.0)
        scene_plan = [
            {"file": clip["file"], "duration_seconds": duration_per_clip, "keyword": clip.get("keyword", "")}
            for clip in clips
        ]

    normalized: list[Path] = []
    for index, scene in enumerate(scene_plan):
        source = resolve_path(scene["file"])
        if not source.exists():
            raise RuntimeError(f"❌ الكليب غير موجود: {source}")
        norm_path = CLIPS_DIR / f"norm_full_{index:03d}.mp4"
        normalize_clip(source, norm_path, max(float(scene["duration_seconds"]), 0.05), scene.get("audio_decision", "VOICE ONLY"))
        normalized.append(norm_path)

    concatenated = CLIPS_DIR / "concatenated_full.mp4"
    concat_clips(normalized, concatenated, CLIPS_DIR / "concat_list_full.txt")
    add_audio_and_subtitles(concatenated, final_audio, subtitles, output_path)
    return probe_duration(output_path)


def write_cta_ass(path: Path, start: float, end: float, text: str) -> None:
    """ينشئ Overlay ASS عربيًا بدل drawtext لتفادي مشاكل تشكيل العربية.

التنويه يظهر أعلى الإطار لكن في مسار ثانٍ أسفل ترجمة السرد (هامش 620px)،
مع الحفاظ على الخط والحجم وحدود النص المتوافقة مع الترجمة.
    """
    def ass_time(seconds: float) -> str:
        centiseconds = max(0, int(round(seconds * 100)))
        hours, rem = divmod(centiseconds, 360000)
        minutes, rem = divmod(rem, 6000)
        secs, cs = divmod(rem, 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"

    safe_text = text.replace("\\", "\\\\").replace("\n", r"\N")
    content = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {SHORT_WIDTH}\n"
        f"PlayResY: {SHORT_HEIGHT}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # أعلى-وسط، في مسار منفصل أسفل ترجمة السرد وأعلى منطقة الشاشة.
        "Style: CTA,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"1,0,0,0,100,100,0,0,1,3,0,8,70,70,{REEL_CTA_TOP_MARGIN},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
        f"Dialogue: 0,{ass_time(start)},{ass_time(end)},CTA,,0,0,0,,{safe_text}\n"
    )
    path.write_text(content, encoding="utf-8")


def default_short_specs(full_duration: float) -> list[dict]:
    """ينشئ ريل/ريلات تلقائيًا تبدأ من أول الفيديو وتترك هامشًا قبل
    نهاية القصة. مع DEFAULT_SHORT_COUNT=1 (القيمة الحالية) بترجع ريل
    واحد بس يبدأ من الثانية صفر."""
    usable_end = max(1.0, full_duration - AUTO_END_MARGIN_SECONDS)
    if usable_end <= 1:
        return [{"start_seconds": 0.0, "end_seconds": min(full_duration, MAX_SHORT_DURATION_SECONDS)}]

    count = DEFAULT_SHORT_COUNT
    window = min(MAX_SHORT_DURATION_SECONDS, usable_end / count)
    specs = []
    for index in range(count):
        start = index * (usable_end / count)
        end = min(start + window, usable_end)
        if end - start < 1:
            continue
        specs.append({"start_seconds": start, "end_seconds": end})
    return specs


def load_short_specs(episode: dict, full_duration: float) -> list[dict]:
    raw = episode.get("shorts")
    if not isinstance(raw, list) or not raw:
        return default_short_specs(full_duration)

    specs = []
    safe_end = max(0.0, full_duration - AUTO_END_MARGIN_SECONDS)
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            start = max(0.0, float(item.get("start_seconds", 0)))
            requested_end = float(item.get("end_seconds", start + MAX_SHORT_DURATION_SECONDS))
        except (TypeError, ValueError):
            continue

        end = min(requested_end, start + MAX_SHORT_DURATION_SECONDS, safe_end)
        if end - start >= 1.0:
            specs.append({"start_seconds": start, "end_seconds": end})

    return specs or default_short_specs(full_duration)


def create_short(
    full_video: Path,
    spec: dict,
    short_index: int,
    platform: str,
    output_path: Path,
    vertical_subtitles: Path | None = None,
) -> float:
    start = float(spec["start_seconds"])
    end = float(spec["end_seconds"])
    duration = min(end - start, MAX_SHORT_DURATION_SECONDS)
    if duration <= 0:
        raise ValueError("مدة الريل يجب أن تكون أكبر من صفر")

    cta_start = max(0.0, duration - CTA_DURATION_SECONDS)
    cta_ass = CLIPS_DIR / f"cta_short_{short_index}_{platform}.ass"
    write_cta_ass(cta_ass, cta_start, duration, PLATFORM_CTA[platform])
    cta_filter = subtitle_filter(cta_ass)

    # crop مركزي من 16:9 إلى 9:16، مع الإبقاء على صوت الفيديو الكامل.
    vf = (
        f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={SHORT_WIDTH}:{SHORT_HEIGHT},setsar=1"
    )
    narration_filter = subtitle_filter(vertical_subtitles)
    if narration_filter:
        vf += f",{narration_filter}"
    if cta_filter:
        vf += f",{cta_filter}"

    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(full_video),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ])
    return probe_duration(output_path)


def _run() -> None:
    for path in (FETCHED_CLIPS_PATH, EPISODE_PATH):
        if not path.exists():
            raise RuntimeError(f"❌ الملف غير موجود: {path}")

    clips = json.loads(FETCHED_CLIPS_PATH.read_text(encoding="utf-8"))
    if not isinstance(clips, list) or not clips:
        raise RuntimeError("❌ fetched_clips.json فارغ أو غير صالح.")
    audio_report = validate_manifest(clips)
    (STATE_DIR / "audio_matching_report.json").write_text(
        json.dumps(audio_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not audio_report["passed"]:
        raise RuntimeError("❌ AUDIO MATCHING GATE: " + "; ".join(audio_report["errors"]))

    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    final_audio_value = episode.get("final_audio")
    subtitles_value = episode.get("subtitles")

    # توافق مع current_episode القديم الذي كان يحفظ المخرجات داخل parts.
    if not final_audio_value:
        parts = episode.get("parts") or []
        if len(parts) == 1:
            final_audio_value = parts[0].get("final_audio")
            subtitles_value = subtitles_value or parts[0].get("subtitles")
        elif len(parts) > 1:
            raise RuntimeError(
                "❌ current_episode.json ما زال يحتوي على أجزاء متعددة. "
                "شغّل generate_voice.py بالنسخة الجديدة لإنتاج صوت كامل واحد."
            )

    if not final_audio_value:
        final_audio_value = str(CLIPS_DIR / "narration.mp3")
    final_audio = resolve_path(final_audio_value)
    subtitles = resolve_path(subtitles_value) if subtitles_value else None

    if not final_audio.exists():
        raise RuntimeError(f"❌ ملف الصوت النهائي غير موجود: {final_audio}")
    if subtitles and not subtitles.exists():
        print(f"⚠️ ملف الترجمة غير موجود؛ سيتم إنتاج الفيديو بدون ترجمة: {subtitles}")
        subtitles = None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    # لا نترك ملفات أصول قديمة تُفهم على أنها ناتج التشغيل الحالي.
    for old in OUTPUT_DIR.glob("final_video_part*.mp4"):
        old.unlink(missing_ok=True)
    for old in OUTPUT_DIR.glob("short_*.mp4"):
        old.unlink(missing_ok=True)

    full_output = OUTPUT_DIR / "final_video_full.mp4"
    full_duration = build_full_video(clips, final_audio, subtitles, full_output, episode)
    print(f"✅ الفيديو الكامل الأفقي: {full_output}")
    print(f"✅ مدة الفيديو الكامل: {full_duration:.1f} ثانية")

    # Reels must not inherit the horizontal bottom-caption layer. Reuse the
    # same rendered clip sequence and audio, then place a dedicated caption
    # track in the upper 9:16 safe lane.
    reel_source = OUTPUT_DIR / "reel_source_clean.mp4"
    add_audio_and_subtitles(CLIPS_DIR / "concatenated_full.mp4", final_audio, None, reel_source)
    vertical_subtitles = None
    if subtitles:
        vertical_subtitles = make_vertical_subtitles(
            subtitles, CLIPS_DIR / "narration_vertical.ass"
        )

    specs = load_short_specs(episode, full_duration)
    print(f"✅ عدد الريلات: {len(specs)} — الحد الأقصى لكل ريل: {MAX_SHORT_DURATION_SECONDS:.0f}s")

    generated = 0
    for short_index, spec in enumerate(specs, 1):
        for platform in PLATFORM_CTA:
            output = OUTPUT_DIR / f"short_{short_index}_{platform}.mp4"
            duration = create_short(
                reel_source, spec, short_index, platform, output, vertical_subtitles
            )
            generated += 1
            print(
                f"✅ ريل {short_index} / {platform}: {output} "
                f"({duration:.1f}s، يتوقف قبل نهاية القصة)"
            )

    if generated == 0:
        raise RuntimeError("❌ لم يتم إنشاء أي ريل.")

    print("✅ اكتمل إنتاج الفيديو الكامل والريل لجميع المنصات.")


def main() -> int:
    try:
        _run()
    except Exception as exc:
        print(f"❌ Video assembly failed: {exc}")
        return 1
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
