"""
assemble_video.py

ينتج أصلين من نفس الحلقة:

1) فيديو كامل عمودي 9:16:
   output/final_video_full.mp4

2) لا يتم إنشاء ريل؛ المخرج الوحيد هو القصة الكاملة العمودية:

مصدر الحقيقة للصوت والترجمة العربية هو current_episode.json. يدعم الملف الحقول الجديدة:

{
  "final_audio": "downloaded_clips/narration.mp3",
  "subtitles": "downloaded_clips/narration.ass",
  "shorts": [
    {"start_seconds": 0, "end_seconds": 75}
  ]
}

تُهمل أي قائمة shorts قديمة ولا تُنتج ملفات ريل،
مع ترك AUTO_END_MARGIN_SECONDS في نهاية الحلقة حتى لا يصل المقتطف إلى الحل.

مهم: مدة 90 ثانية حد للريل فقط، وليست حدًا للفيديو الكامل.

=== تعديل جديد: ريل واحد بس بدل شورتين ===
كان بيتنتج شورتان (short_1 من البداية، short_2 من المنتصف تقريبًا).
المطلوب دلوقتي ريل واحد بس، يبدأ من أول الفيديو مباشرة، مع تنويه في
آخره يوجّه المشاهد لمشاهدة بقية الفيديو على الصفحة. الحل: DEFAULT_SHORT_COUNT
بقت 1 بدل 2 — default_short_specs() أصلًا كانت بتدعم أي عدد، فمع القيمة
الجديدة بترجع ريل واحد بس يبدأ من الثانية صفر (start=0) ويمتد لحد
MAX_FULL_VIDEO_SECONDS هو الحد الأقصى للفيديو الكامل.

=== تخطيط النص في المنطقة الآمنة ===
ترجمة السرد في أصل 16:9 محاذاة أسفل-وسط بهامش سفلي 70px، بعيدًا عن حواف
الفيديو. يظهر مقتطف في مسار علوي ثانٍ بهامش 620px في الريل، كي لا يتداخل
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

# الفيديو الكامل: عمودي 9:16
FULL_WIDTH = 1080
FULL_HEIGHT = 1920

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
MAX_SHORT_DURATION_SECONDS = 59.0
MAX_FULL_VIDEO_SECONDS = 180.0
# ريل واحد بس (كان 2 قبل كده) — يبدأ من أول الفيديو مباشرة. شوف شرح
# "ريل واحد بس بدل شورتين" أعلى الملف.
DEFAULT_SHORT_COUNT = 1
AUTO_END_MARGIN_SECONDS = 8.0
FPS = 30

PLATFORMS = ("youtube", "facebook", "instagram")


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
                fields[21] = "300"     # safe top margin for 9:16
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


def finish_reel_at_caption_boundary(spec: dict, subtitles: Path | None) -> dict:
    """Prefer a complete sentence between 45 seconds and the requested cap."""
    if not subtitles or not subtitles.exists():
        return spec
    start, end = spec["start_seconds"], spec["end_seconds"]
    caption_ends, sentence_ends = [], []
    for line in subtitles.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) != 10:
            continue
        try:
            hours, minutes, seconds = fields[2].split(":")
            timestamp = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except (ValueError, TypeError):
            continue
        if start + 45 <= timestamp <= end:
            caption_ends.append(timestamp)
            text = re.sub(r"\{[^}]*\}", "", fields[9]).strip()
            if text.rstrip('"»”').endswith((".", "!", "؟", "?", "…")):
                sentence_ends.append(timestamp)
    candidates = sentence_ends or caption_ends
    if not candidates:
        return spec
    return {**spec, "end_seconds": max(candidates)}


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


    # crop مركزي من 16:9 إلى 9:16، مع الإبقاء على صوت الفيديو الكامل.
    vf = (
        f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={SHORT_WIDTH}:{SHORT_HEIGHT},setsar=1"
    )
    narration_filter = subtitle_filter(vertical_subtitles)
    if narration_filter:
        vf += f",{narration_filter}"

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
    from scripts.cinematic_production import enabled, build_episode
    if enabled():
        build_episode(ROOT_DIR)
        return
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
    full_subtitles = make_vertical_subtitles(subtitles, CLIPS_DIR / "narration_full_vertical.ass") if subtitles else None
    full_duration = build_full_video(clips, final_audio, full_subtitles, full_output, episode)
    print(f"✅ الفيديو الكامل العمودي: {full_output}")
    if full_duration <= 0 or full_duration > MAX_FULL_VIDEO_SECONDS:
        raise ValueError(f"مدة الفيديو الكامل يجب أن تكون بين 0 و180 ثانية: {full_duration:.2f}s")
    print(f"✅ مدة الفيديو الكامل العمودي: {full_duration:.1f} ثانية")

    print("✅ تم إنتاج قصة كاملة واحدة فقط؛ لن يتم إنشاء أي ريل أو short_*.mp4.")
def main() -> int:
    try:
        _run()
    except Exception as exc:
        print(f"❌ Video assembly failed: {exc}")
        return 1
    return 0
if __name__ == "__main__":
    raise SystemExit(main())

