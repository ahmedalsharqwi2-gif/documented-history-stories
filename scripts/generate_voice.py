"""توليد صوت الحلقة كاملة وترجمة ASS متزامنة ثنائية اللغة (عربي + إنجليزي).

هذا الملف لا يقسم القصة إلى أجزاء. ينتج:
- downloaded_clips/narration_voice.mp3
- downloaded_clips/narration_with_music.mp3
- downloaded_clips/narration.ass
ويحدّث current_episode.json بالمسارات الجديدة.

=== تحويل القناة: إضافة نص إنجليزي متزامن على الشاشة ===
كانت نسخة الرعب تعرض ترجمة عربية فقط (كتل من 4 كلمات متزامنة مع الصوت
عبر Whisper). المطلوب الآن: عرض النص العربي والإنجليزي معًا على الشاشة
في نفس الوقت (سكريبت ثنائي اللغة)، مع بقاء الصوت المسموع عربيًا فقط
(السرد الإنجليزي غير منطوق، نص فقط).

آلية التزامن الثنائي:
1) التوقيت العربي (على مستوى الكلمة) يُحسب بالضبط زي الأول عبر محاذاة
   Whisper الفعلية مع الصوت المُصنَّع (انظر align_words_with_whisper).
2) التوقيت الإنجليزي (على مستوى الجملة الكاملة لا الكلمة) يُشتق من نفس
   توقيت الكلمات العربية: بيتحسب عدد كلمات كل جملة عربية على حدة، وبيتم
   جمع بداية أول كلمة فيها ونهاية آخر كلمة فيها من الأحداث العربية
   المحسوبة فعليًا، فتبقى بداية ونهاية كل جملة إنجليزية مطابقة تمامًا
   لبداية ونهاية الجملة العربية المقابلة لها في الصوت. الترجمة على
   مستوى الجملة كاملة لا الكلمة لأن الترجمة الأمينة لا تتبع نفس ترتيب
   الكلمات العربية غالبًا، فمزامنتها كلمة بكلمة ستكون مضلِّلة.

⚠️ ملاحظة مهمة عن عرض الشورتس (اقرأها قبل تعديل عرض الأسطر تحت):
الفيديو الكامل الأفقي (1920x1080) هو اللي بتتحرق عليه الترجمة فعليًا في
assemble_video.py، وبعدين الشورتس الرأسية (9:16) بتتقص من مركز الفيديو
الكامل ده (crop مركزي شديد أفقيًا). ده معناه إن أي سطر ترجمة عرضه أكبر
من تقريبًا ثلث عرض الفيديو الكامل هيتقص من الجانبين في نسخة الشورتس.
لتفادي كده، النص الإنجليزي هنا بيتقسم لأسطر قصيرة نسبيًا (WRAP_MAX_CHARS
تحت) بدل سطر واحد طويل، حتى لو ده معناه ظهور 3-4 أسطر قصيرة بدل سطرين
طويلين في الفيديو الكامل نفسه — تضحية بسيطة في شكل العرض الأفقي مقابل
ضمان إن الترجمة متقروءة وغير مقصوصة في الشورتس كمان، لأن نفس ملف
الترجمة بيُستخدم للاثنين معًا. لو حابب حل أدق (ملفا ترجمة منفصلين لكل
نسخة)، ده تعديل إضافي في assemble_video.py مش في الملف ده.

مزامنة الكلمات العربية: بدل الاعتماد فقط على توقيت "WordBoundary" الذي
يرجعه edge-tts ذاتيًا لكل جملة، ثم تجميعه يدويًا مع مدد السكتات بين
الجمل (طريقة عرضة للانحراف التراكمي)، يُشغَّل الآن Whisper
(faster-whisper) على الصوت النهائي الكامل بعد تجميعه فعليًا، ويُطابَق
ناتجه (توقيت حقيقي مبني على الموجة الصوتية الفعلية) مع كلمات القصة
نفسها. توقيت edge-tts الذاتي (القديم) يبقى فقط كخطة احتياطية إذا تعذّر
تشغيل Whisper لأي سبب.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
from voice_profiles import resolve_reference_profile

TTS_ENGINE = os.getenv("TTS_ENGINE", "silma").strip().lower()
BARK_HISTORY_PROMPT = os.getenv("BARK_HISTORY_PROMPT", "").strip()
BARK_TEXT_TEMP = float(os.getenv("BARK_TEXT_TEMP", "0.7"))
BARK_WAVEFORM_TEMP = float(os.getenv("BARK_WAVEFORM_TEMP", "0.7"))
XTTS_MODEL = os.getenv("XTTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
XTTS_SPEAKER_WAV = Path(os.getenv("XTTS_SPEAKER_WAV", "assets/voice_reference.wav"))
XTTS_USE_GPU = os.getenv("XTTS_USE_GPU", "false").lower() == "true"
SILMA_REFERENCE_WAV = Path(os.getenv("SILMA_REFERENCE_WAV", "assets/voice_reference_synthetic.wav"))
SILMA_REFERENCE_TEXT = os.getenv(
    "SILMA_REFERENCE_TEXT",
    "في عام 1943، بدأت خطة خداع عسكرية بوثيقة صغيرة، لكنها غيرت مسار معركة كاملة.",
).strip()
SILMA_REFERENCE_PROFILE = os.getenv("SILMA_REFERENCE_PROFILE", "").strip()
SILMA_VOICE_PROFILES_FILE = Path(
    os.getenv("SILMA_VOICE_PROFILES_FILE", "assets/voices/voice_profiles.json")
)
SILMA_SPEED = float(os.getenv("SILMA_SPEED", "1.0"))
SILMA_GUARD_ENABLED = os.getenv("SILMA_GUARD_ENABLED", "true").lower() == "true"
SILMA_GUARD_MIN_MATCH_WORDS = int(os.getenv("SILMA_GUARD_MIN_MATCH_WORDS", "2"))

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
STATE_DIR = ROOT_DIR / "state"
CLIPS_DIR = ROOT_DIR / "downloaded_clips"
ASSETS_DIR = ROOT_DIR / "assets"
EPISODE_PATH = STATE_DIR / "current_episode.json"
BACKGROUND_MUSIC = ASSETS_DIR / "background_music.mp3"

# الصوت الأساسي ثم أصوات احتياطية. يمكن تغييرها من GitHub Actions عبر
# EDGE_TTS_VOICES="ar-EG-ShakirNeural,ar-SA-HamedNeural,ar-SA-ZariyahNeural"
VOICE = os.getenv("EDGE_TTS_VOICE", "ar-EG-ShakirNeural")
VOICE_CANDIDATES = list(dict.fromkeys([
    item.strip()
    for item in os.getenv(
        "EDGE_TTS_VOICES",
        "ar-EG-ShakirNeural,ar-SA-HamedNeural,ar-SA-ZariyahNeural",
    ).split(",")
    if item.strip()
]))
if VOICE not in VOICE_CANDIDATES:
    VOICE_CANDIDATES.insert(0, VOICE)
EDGE_TTS_RETRIES = int(os.getenv("EDGE_TTS_RETRIES", "3"))
EDGE_TTS_RETRY_DELAY = float(os.getenv("EDGE_TTS_RETRY_DELAY", "2"))
RATE = os.getenv("EDGE_TTS_RATE", "-8%")
PITCH = os.getenv("EDGE_TTS_PITCH", "-5Hz")
VOLUME = "+0%"
MUSIC_VOLUME = 0.15
WORDS_PER_CAPTION_CHUNK = 4
VIDEO_W = 1920
VIDEO_H = 1080

# نموذج Whisper المستخدم لمحاذاة الترجمة مع الصوت الفعلي (انظر
# align_words_with_whisper أدناه). "base" اختيار متوازن بين السرعة
# والدقة على معالج عادي؛ يمكن رفعه لـ "small" لدقة أعلى مقابل وقت أطول
# عبر متغير البيئة WHISPER_MODEL.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")

VOICE_AUDIO = CLIPS_DIR / "narration_voice.mp3"
FINAL_AUDIO = CLIPS_DIR / "narration_with_music.mp3"
SUBTITLES = CLIPS_DIR / "narration.ass"

PAUSE_AFTER_ELLIPSIS = 1.3
PAUSE_AFTER_QUESTION_EXCLAIM = 0.75
PAUSE_AFTER_PERIOD = 0.45
DEFAULT_PAUSE = 0.5

ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08E1\u08E3-\u08FF]")
_WORD_TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
# علامات تُحذف من النص المرئي فقط حتى يبدو طبيعيًا وغير آلي. نص الراوي
# الأصلي يظل محتفظًا بها لأن edge-tts يستخدمها لصناعة الوقفات الصحيحة.
DISPLAY_PUNCTUATION = str.maketrans(".,،؛:!?؟…-—_()[]{}\"«»/\\", " " * 23)

# أقصى عدد حروف تقريبي لكل سطر ترجمة إنجليزية قبل الانتقال لسطر جديد
# (انظر الملاحظة أعلى الملف عن سبب اختيار قيمة متحفظة بسبب قص الشورتس).
WRAP_MAX_CHARS_EN = 17

# قاموس تشكيل انتقائي: كل كلمة هنا لها أكثر من قراءة ممكنة بلا تشكيل، لكن
# قراءة واحدة منها فقط هي المسيطرة فعليًا في سياق سرد ديني/تاريخي —
# تمامًا مثل مشكلة "زر" (زِرّ الضغط مقابل فعل الزيارة): كلمة بلا تشكيل
# ممكن يقرأها المحرك بمعنى مختلف تمامًا عن المقصود. أي كلمة يُضاف
# تشكيلها هنا يجب أن يكون لها قراءة واحدة غالبة بوضوح في هذا السياق.
HARD_WORDS_DIACRITICS = {
    "عدة": "عِدّة", "قلبه": "قَلْبه", "همس": "هَمْس", "خطى": "خُطى",
    "عبرة": "عِبرة", "أمة": "أُمّة", "غزوة": "غَزوة", "فتح": "فَتْح",
    "نصر": "نَصْر", "هجرة": "هِجرة",
}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("❌ فشل الأمر:\n" + " ".join(command) + "\n\n" + result.stderr)
    return result


def configure_silma_voice_profile() -> str:
    """Resolve the chosen bundled WAV and its exact reference transcript."""
    global SILMA_REFERENCE_WAV, SILMA_REFERENCE_TEXT
    selected, label, wav, transcript = resolve_reference_profile(
        SILMA_REFERENCE_PROFILE,
        SILMA_VOICE_PROFILES_FILE,
        ROOT_DIR,
    )
    SILMA_REFERENCE_WAV = wav
    SILMA_REFERENCE_TEXT = transcript
    print(f"🎙️ ملف الصوت المختار: {label} ({selected})")
    return selected


def save_voice_to_history(episode: dict, selected_voice: str) -> None:
    history_path = ROOT_DIR / "state" / "used_clips.json"
    if not history_path.exists():
        return
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
        for item in reversed(data.get("history", [])):
            if item.get("title") == episode.get("title"):
                item["voice_profile"] = selected_voice
                break
        history_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        print("⚠️ تعذر حفظ اختيار الصوت في سجل الحلقات")


def strip_diacritics(text: str) -> str:
    return ARABIC_DIACRITICS_PATTERN.sub("", text)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", strip_diacritics(text)).strip()


def apply_phonetic_hints(text: str, hints: list[dict]) -> str:
    """يستبدل كل مدخل من phonetic_hints (كلمة أو عبارة كما وردت بالضبط
    في narration) بنسختها المشكّلة، قبل أي تشكيل عام. بترتب المدخلات من
    الأطول للأقصر أولاً عشان عبارة من كذا كلمة (زي اسم مكان مركّب)
    تتستبدل كوحدة واحدة قبل ما أي كلمة مفردة جواها تتستبدل غلط لو ظهرت
    في مدخل تاني. المفروض phonetic تكون نفس الكلمة بالحروف الأساسية
    بالظبط مع إضافة تشكيل بس (شوف history_strategy_system_prompt.md)، فـ
    strip_diacritics() بترجّعها زي الأصل تمامًا في الترجمة."""
    for hint in sorted(hints, key=lambda h: len(str(h.get("word", ""))), reverse=True):
        word = str(hint.get("word", "")).strip()
        phonetic = str(hint.get("phonetic", "")).strip()
        if word and phonetic:
            text = text.replace(word, phonetic)
    return text


def apply_light_diacritics(text: str) -> str:
    def replace(match: re.Match) -> str:
        word = match.group(0)
        return HARD_WORDS_DIACRITICS.get(word, word)
    return _WORD_TOKEN_PATTERN.sub(replace, text)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!؟…])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def pause_duration_for(sentence: str) -> float:
    stripped = sentence.strip()
    if stripped.endswith("…") or stripped.endswith("..."):
        return PAUSE_AFTER_ELLIPSIS
    if stripped.endswith("؟") or stripped.endswith("!"):
        return PAUSE_AFTER_QUESTION_EXCLAIM
    if stripped.endswith("."):
        return PAUSE_AFTER_PERIOD
    return DEFAULT_PAUSE


def probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(result.stdout.strip())


def build_silence_clip(duration: float, path: Path) -> None:
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{duration:.3f}", "-c:a", "libmp3lame", "-b:a", "192k", str(path),
    ])


def synthesize_sentences_bark(sentences: list[str]) -> list[dict]:
    """ينتج مقاطع WAV عبر Bark من Suno. Bark لا يعيد WordBoundary؛ لذلك
    تُستخرج المحاذاة لاحقًا عبر Whisper مثل خطة الاحتياط الحالية."""
    try:
        # Bark 0.1.5 يستخدم torch.load بالطريقة القديمة. ابتداءً من
        # PyTorch 2.6 أصبح weights_only=True هو الافتراضي، ما يمنع تحميل
        # checkpoints الرسمية. نمرر False صراحةً للملفات التي ينزلها Bark
        # من مستودع النماذج الرسمي، وهو ما يتوافق مع واجهة Bark الحالية.
        import torch
        _torch_load = torch.load
        def _bark_torch_load(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _torch_load(*args, **kwargs)
        torch.load = _bark_torch_load
        from bark import generate_audio, preload_models
        from scipy.io import wavfile
    except ImportError as exc:
        raise RuntimeError("تعذر استيراد Bark/Scipy؛ ثبّت suno-bark وscipy") from exc

    print(f"🦜 تحميل نماذج Bark من Suno (history_prompt={BARK_HISTORY_PROMPT})...")
    preload_models()
    segments = []
    for index, raw_sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", str(raw_sentence)).strip()
        if not sentence:
            continue
        seg_path = CLIPS_DIR / f"_seg_full_{index:03d}.wav"
        print(f"   🦜 Bark: الجملة {index + 1}/{len(sentences)}")
        audio = generate_audio(
            sentence,
            history_prompt=BARK_HISTORY_PROMPT or None,
            text_temp=BARK_TEXT_TEMP,
            waveform_temp=BARK_WAVEFORM_TEMP,
        )
        wavfile.write(str(seg_path), 24000, audio)
        duration = probe_duration(seg_path)
        if duration <= 0:
            raise RuntimeError("Bark أعاد ملفًا صوتيًا فارغًا")
        segments.append({
            "path": seg_path, "duration": duration, "events": None,
            "sentence": sentence, "is_silence": False,
        })
        if index < len(sentences) - 1:
            pause = pause_duration_for(sentence)
            pause_path = CLIPS_DIR / f"_pause_full_{index:03d}.mp3"
            build_silence_clip(pause, pause_path)
            segments.append({
                "path": pause_path, "duration": pause, "events": None,
                "sentence": None, "is_silence": True,
            })
    return segments


def synthesize_sentences_xtts(sentences: list[str]) -> list[dict]:
    """ينتج الصوت العربي عبر Coqui XTTS-v2 باستخدام عينة صوت مرجعية واحدة.
    يتم تحميل النموذج مرة واحدة ثم توليد كل جملة في ملف WAV مستقل."""
    if not XTTS_SPEAKER_WAV.is_absolute():
        speaker_wav = ROOT_DIR / XTTS_SPEAKER_WAV
    else:
        speaker_wav = XTTS_SPEAKER_WAV
    if not speaker_wav.exists():
        raise RuntimeError(
            f"ملف الصوت المرجعي غير موجود: {speaker_wav}. "
            "أضف assets/voice_reference.wav أو اضبط XTTS_SPEAKER_WAV."
        )
    try:
        from TTS.api import TTS
    except ImportError as exc:
        raise RuntimeError("تعذر استيراد Coqui TTS؛ ثبّت coqui-tts") from exc

    print(f"🐸 تحميل Coqui XTTS-v2: {XTTS_MODEL} (GPU={XTTS_USE_GPU})...")
    tts = TTS(model_name=XTTS_MODEL, progress_bar=True, gpu=XTTS_USE_GPU)
    segments = []
    for index, raw_sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", str(raw_sentence)).strip()
        if not sentence:
            continue
        seg_path = CLIPS_DIR / f"_seg_full_{index:03d}.wav"
        print(f"   🐸 XTTS: الجملة {index + 1}/{len(sentences)}")
        tts.tts_to_file(
            text=sentence,
            speaker_wav=str(speaker_wav),
            language="ar",
            file_path=str(seg_path),
            split_sentences=False,
        )
        duration = probe_duration(seg_path)
        if duration <= 0:
            raise RuntimeError("XTTS أعاد ملفًا صوتيًا فارغًا")
        segments.append({
            "path": seg_path, "duration": duration, "events": None,
            "sentence": sentence, "is_silence": False,
        })
        if index < len(sentences) - 1:
            pause = pause_duration_for(sentence)
            pause_path = CLIPS_DIR / f"_pause_full_{index:03d}.mp3"
            build_silence_clip(pause, pause_path)
            segments.append({
                "path": pause_path, "duration": pause, "events": None,
                "sentence": None, "is_silence": True,
            })
    return segments


def _norm_arabic_words(text: str) -> list[str]:
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text or "")
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return [w for w in text.lower().split() if w]


def detect_silma_reference_leak(audio_path: Path) -> str | None:
    """Transcribe audio and reject a contiguous phrase copied from SILMA reference."""
    if not SILMA_GUARD_ENABLED or not SILMA_REFERENCE_TEXT:
        return None
    from faster_whisper import WhisperModel
    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), language="ar", word_timestamps=False, vad_filter=False)
    heard = _norm_arabic_words(" ".join(seg.text or "" for seg in segments))
    ref = _norm_arabic_words(SILMA_REFERENCE_TEXT)
    minimum = max(2, min(SILMA_GUARD_MIN_MATCH_WORDS, len(ref)))
    for size in range(len(ref), minimum - 1, -1):
        phrase = ref[-size:]
        for i in range(len(heard) - size + 1):
            if heard[i:i + size] == phrase:
                return " ".join(phrase)
    return None


def synthesize_sentences_silma(sentences: list[str]) -> list[dict]:
    """ينتج الصوت العربي عبر SILMA TTS v1 باستخدام مرجع بشري واحد.
    يُحمّل النموذج مرة واحدة ثم يولّد ملف WAV لكل جملة."""
    reference_wav = SILMA_REFERENCE_WAV
    if not reference_wav.is_absolute():
        reference_wav = ROOT_DIR / reference_wav
    if not reference_wav.exists():
        raise RuntimeError(
            f"ملف مرجع SILMA غير موجود: {reference_wav}. "
            "شغّل خطوة إنشاء المرجع الاصطناعي أولاً أو اضبط SILMA_REFERENCE_WAV."
        )
    try:
        from silma_tts.api import SilmaTTS
    except ImportError as exc:
        raise RuntimeError("تعذر استيراد SILMA؛ ثبّت silma-tts في بيئة التشغيل") from exc

    print(f"🟣 تحميل SILMA TTS v1 (speed={SILMA_SPEED})...")
    silma = SilmaTTS()
    segments = []
    for index, raw_sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", str(raw_sentence)).strip()
        if not sentence:
            continue
        seg_path = CLIPS_DIR / f"_seg_full_{index:03d}.wav"
        seg_path.unlink(missing_ok=True)
        print(f"   🟣 SILMA: الجملة {index + 1}/{len(sentences)}")
        silma.infer(
            ref_file=str(reference_wav),
            ref_text=SILMA_REFERENCE_TEXT or None,
            gen_text=sentence,
            file_wave=str(seg_path),
            seed=None,
            speed=SILMA_SPEED,
        )
        duration = probe_duration(seg_path)
        if duration <= 0:
            raise RuntimeError("SILMA أعاد ملفاً صوتياً فارغاً")
        segments.append({"path": seg_path, "duration": duration, "events": None,
                         "sentence": sentence, "is_silence": False})
        if index < len(sentences) - 1:
            pause = pause_duration_for(sentence)
            pause_path = CLIPS_DIR / f"_pause_full_{index:03d}.mp3"
            build_silence_clip(pause, pause_path)
            segments.append({"path": pause_path, "duration": pause, "events": None,
                             "sentence": None, "is_silence": True})
    return segments


async def synthesize_sentences(sentences: list[str], engine_override: str | None = None) -> list[dict]:
    """يختار محرك الصوت صراحةً؛ SILMA لا يرجع إلى Edge تلقائياً."""
    engine = engine_override or TTS_ENGINE
    if engine == "silma":
        try:
            return synthesize_sentences_silma(sentences)
        except Exception as exc:
            if engine_override is None and os.getenv("SILMA_FALLBACK_TO_EDGE", "true").lower() == "true":
                print(f"⚠️ تعذر SILMA ({exc}) — الرجوع إلى Edge TTS.")
                return await synthesize_sentences(sentences, "edge")
            raise
    if TTS_ENGINE == "xtts":
        try:
            return synthesize_sentences_xtts(sentences)
        except Exception as exc:  # XTTS اختياري؛ لا نسقط النشر بالكامل
            if os.getenv("XTTS_FALLBACK_TO_EDGE", "true").lower() == "true":
                print(f"⚠️ تعذر XTTS ({exc}) — الرجوع إلى Edge TTS.")
            else:
                raise
    if TTS_ENGINE == "bark":
        try:
            return synthesize_sentences_bark(sentences)
        except Exception as exc:  # Bark اختياري؛ لا نسقط النشر بالكامل
            if os.getenv("BARK_FALLBACK_TO_EDGE", "true").lower() == "true":
                print(f"⚠️ تعذر Bark ({exc}) — الرجوع إلى Edge TTS.")
            else:
                raise
    segments = []
    for index, raw_sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", str(raw_sentence)).strip()
        if not sentence:
            print(f"⚠️ تم تجاهل جملة فارغة رقم {index + 1}.")
            continue

        seg_path = CLIPS_DIR / f"_seg_full_{index:03d}.mp3"
        events = []
        last_error: Exception | None = None
        succeeded = False

        for voice in VOICE_CANDIDATES:
            for retry in range(1, EDGE_TTS_RETRIES + 1):
                seg_path.unlink(missing_ok=True)
                events = []
                try:
                    communicate = edge_tts.Communicate(
                        sentence, voice, rate=RATE, pitch=PITCH, volume=VOLUME
                    )
                    with seg_path.open("wb") as audio_file:
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                audio_file.write(chunk["data"])
                            elif chunk["type"] == "WordBoundary":
                                events.append(chunk)
                    if not seg_path.exists() or seg_path.stat().st_size == 0:
                        raise RuntimeError("Edge TTS أعاد ملفًا صوتيًا فارغًا")
                    duration = probe_duration(seg_path)
                    if duration <= 0:
                        raise RuntimeError("Edge TTS أعاد مدة صوت تساوي صفرًا")
                    succeeded = True
                    print(
                        f"   🔊 الجملة {index + 1}/{len(sentences)}: "
                        f"الصوت {voice}، المحاولة {retry}، {duration:.2f} ثانية"
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    seg_path.unlink(missing_ok=True)
                    print(
                        f"   ⚠️ فشل Edge TTS في الجملة {index + 1}/{len(sentences)} "
                        f"بالصوت {voice}، المحاولة {retry}/{EDGE_TTS_RETRIES}: {exc}"
                    )
                    if retry < EDGE_TTS_RETRIES:
                        await asyncio.sleep(EDGE_TTS_RETRY_DELAY * retry)
            if succeeded:
                break
            print(f"   🔁 الانتقال إلى صوت Edge TTS احتياطي بعد فشل {voice}.")

        if not succeeded:
            preview = sentence[:160].replace("\n", " ")
            raise RuntimeError(
                f"تعذر توليد الجملة رقم {index + 1} بكل أصوات Edge TTS. "
                f"النص: {preview!r}. آخر خطأ: {last_error}"
            ) from last_error

        segments.append({
            "path": seg_path,
            "duration": duration,
            "events": events,
            "sentence": sentence,
            "is_silence": False,
        })
        if index < len(sentences) - 1:
            pause = pause_duration_for(sentence)
            pause_path = CLIPS_DIR / f"_pause_full_{index:03d}.mp3"
            build_silence_clip(pause, pause_path)
            segments.append({
                "path": pause_path,
                "duration": pause,
                "events": None,
                "sentence": None,
                "is_silence": True,
            })
    return segments


def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def two_lines_ar(words: list[str]) -> str:
    """يقسم كتلة كلمات عربية إلى سطرين لعرض ترجمة عربية متزامنة كلمة
    بكلمة تقريبًا (تُستخدم لخط الترجمة العربية السفلي)."""
    words = [word.translate(DISPLAY_PUNCTUATION).strip() for word in words]
    words = [word for word in words if word]
    if len(words) <= 2:
        return "\u200f" + " ".join(words)
    midpoint = (len(words) + 1) // 2
    # \N هو كسر سطر ASS، أما U+200F فهو حرف اتجاه غير مرئي. لا نستخدم
    # النص الحرفي "\\u200f" حتى لا يظهر بجانب الكلام في الفيديو.
    return "\u200f" + " ".join(words[:midpoint]) + r"\N" + "\u200f" + " ".join(words[midpoint:])


def wrap_lines_en(text: str, max_chars: int = WRAP_MAX_CHARS_EN) -> str:
    """يقسم نص الترجمة الإنجليزية إلى أسطر قصيرة (انظر الملاحظة أعلى
    الملف عن سبب التحفّظ في عرض السطر بسبب قص الشورتس)."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return r"\N".join(lines) if lines else text


def build_ass_header() -> str:
    """يعرّف تنسيق الترجمة العربية فقط، متزامنة مع الصوت عبر Whisper.
    لا يتم إنشاء Style أو Dialogue باللغة الإنجليزية."""
    style_ar = (
        "Style: Caption,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "1,0,0,0,100,100,0,0,1,3,0,2,70,70,90,1"
    )
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {VIDEO_W}\nPlayResY: {VIDEO_H}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + style_ar
        + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


# ---------------------------------------------------------------------------
# مزامنة الترجمة: محاذاة حقيقية بالصوت الفعلي (Whisper) — مع خطة احتياطية
# ---------------------------------------------------------------------------

def _build_word_events_from_edge_tts(segments: list[dict]) -> list[dict]:
    """توقيت احتياطي فقط: يعتمد على "WordBoundary" الذي يرجعه edge-tts
    لكل جملة على حدة، مجمّعًا يدويًا مع مدد السكتات المُدرَجة بينها. لا
    يُستخدم إلا إذا تعذّرت محاذاة Whisper (انظر align_words_with_whisper)
    — توقيت edge-tts الذاتي للعربية غير موثوق بما يكفي ليكون المصدر
    الأساسي، خصوصًا مع تراكم خطأ كل جملة على التي بعدها."""
    events: list[dict] = []
    cumulative_seconds = 0.0
    for segment in segments:
        if segment["is_silence"]:
            cumulative_seconds += segment["duration"]
            continue
        if segment["events"]:
            for event in segment["events"]:
                events.append({
                    "text": strip_diacritics(event["text"]),
                    "offset": cumulative_seconds + event["offset"] / 10_000_000,
                    "duration": event["duration"] / 10_000_000,
                })
        else:
            words = re.findall(r"\S+", segment["sentence"] or "")
            per_word = segment["duration"] / max(len(words), 1)
            for word_index, word in enumerate(words):
                events.append({
                    "text": strip_diacritics(word),
                    "offset": cumulative_seconds + word_index * per_word,
                    "duration": per_word,
                })
        cumulative_seconds += segment["duration"]
    return events


def align_words_with_whisper(audio_path: Path, script_words: list[str]) -> list[dict]:
    """يحاذي script_words مع الصوت الفعلي المُنتَج باستخدام faster-whisper،
    بدل الوثوق بتوقيت edge-tts الذاتي. النص المعروض/المستخدم دائمًا هو
    script_words نفسها؛ ناتج Whisper (بلا تشكيل، وقد يحوي أخطاء تعرّف
    بسيطة) يُستخدم فقط لاستخراج التوقيت الحقيقي، عبر مطابقة الفروقات
    (difflib) بين الكلمتين بعد تطبيع كل منهما. أي كلمة من السكريبت لم
    يتعرّف عليها Whisper بثقة تأخذ توقيتًا تقريبيًا من أقرب كلمتين
    متطابقتين قبلها وبعدها، بدل أن تُفقد."""
    from faster_whisper import WhisperModel

    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(audio_path), language="ar", word_timestamps=True, vad_filter=False,
    )

    whisper_words: list[tuple[str, float, float]] = []
    for segment in segments:
        for w in (segment.words or []):
            text = (w.word or "").strip()
            if text:
                whisper_words.append((text, float(w.start), float(w.end)))
    if not whisper_words:
        raise RuntimeError("Whisper لم يرجع أي توقيت على مستوى الكلمة")

    def _norm(w: str) -> str:
        return strip_diacritics(w).translate(DISPLAY_PUNCTUATION).strip().lower()

    script_norm = [_norm(w) for w in script_words]
    whisper_norm = [_norm(w) for w, _, _ in whisper_words]

    matcher = difflib.SequenceMatcher(None, script_norm, whisper_norm, autojunk=False)
    timings: list[dict | None] = [None] * len(script_words)
    for _tag, i1, i2, j1, j2 in matcher.get_matching_blocks():
        for k in range(i2 - i1):
            if i1 + k >= len(script_words) or j1 + k >= len(whisper_words):
                continue
            _, start, end = whisper_words[j1 + k]
            timings[i1 + k] = {
                "text": script_words[i1 + k],
                "offset": start,
                "duration": max(end - start, 0.05),
            }

    known_indices = [i for i, t in enumerate(timings) if t is not None]
    if not known_indices or len(known_indices) < len(script_words) * 0.5:
        raise RuntimeError(
            f"تطابق ضعيف جدًا: {len(known_indices)}/{len(script_words)} كلمة فقط"
        )

    for i in range(len(timings)):
        if timings[i] is not None:
            continue
        prev_i = max((k for k in known_indices if k < i), default=None)
        next_i = min((k for k in known_indices if k > i), default=None)
        if prev_i is None:
            base = timings[next_i]
            offset = max(base["offset"] - 0.2 * (next_i - i), 0.0)
        elif next_i is None:
            base = timings[prev_i]
            offset = base["offset"] + base["duration"] * (i - prev_i)
        else:
            prev_end = timings[prev_i]["offset"] + timings[prev_i]["duration"]
            next_start = timings[next_i]["offset"]
            span = max(next_start - prev_end, 0.05)
            offset = prev_end + span * (i - prev_i) / (next_i - prev_i)
        timings[i] = {"text": script_words[i], "offset": offset, "duration": 0.3}

    print(
        f"🎯 محاذاة Whisper: {len(known_indices)}/{len(script_words)} كلمة مطابقة مباشرة، "
        f"{len(script_words) - len(known_indices)} بالتقريب"
    )
    return timings


def synthesize_voice(voice_text: str) -> None:
    sentences = split_sentences(voice_text)
    if not sentences:
        sys.exit("❌ النص فارغ ولا يمكن إنشاء صوت.")
    segments = asyncio.run(synthesize_sentences(sentences))
    inputs: list[str] = []
    for segment in segments:
        inputs += ["-i", str(segment["path"])]
    concat_filter = "".join(f"[{i}:a]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=0:a=1[aout]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", concat_filter, "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", str(VOICE_AUDIO)])
    if TTS_ENGINE == "silma":
        try:
            leak = detect_silma_reference_leak(VOICE_AUDIO)
        except Exception as exc:  # Whisper unavailable/download failure: respect the configured fallback policy.
            print(f"⚠️ تعذر فحص صوت SILMA عبر Whisper ({exc}).")
            leak = "whisper_guard_error"
        if leak:
            if os.getenv("SILMA_FALLBACK_TO_EDGE", "true").lower() != "true":
                raise RuntimeError(
                    f"تعذر اعتماد ملف SILMA للصوت المختار ({leak})، ولن أستبدله بصوت Edge مختلف."
                )
            print(f"⚠️ تسرّب/خلل في صوت SILMA ({leak}) — إعادة التوليد بـEdge TTS.")
            for segment in segments:
                Path(segment["path"]).unlink(missing_ok=True)
            segments = asyncio.run(synthesize_sentences(sentences, "edge"))
            inputs = []
            for segment in segments:
                inputs += ["-i", str(segment["path"])]
            concat_filter = "".join(f"[{i}:a]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=0:a=1[aout]"
            run(["ffmpeg", "-y", *inputs, "-filter_complex", concat_filter, "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", str(VOICE_AUDIO)])

    # نفس ترتيب/شكل الكلمات المعروضة كما كانت قبل التعديل (بلا تشكيل،
    # وبعلامات الترقيم لا تزال ملتصقة — two_lines_ar() تحذفها وقت العرض).
    display_words = strip_diacritics(voice_text).split()

    try:
        all_word_events = align_words_with_whisper(VOICE_AUDIO, display_words)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ فشلت محاذاة Whisper ({exc}) — الرجوع لتوقيت edge-tts الافتراضي.")
        all_word_events = _build_word_events_from_edge_tts(segments)

    if not all_word_events:
        sys.exit("❌ تعذر إنشاء توقيت الترجمة.")

    dialogue_lines = []
    for index in range(0, len(all_word_events), WORDS_PER_CAPTION_CHUNK):
        group = all_word_events[index:index + WORDS_PER_CAPTION_CHUNK]
        start = group[0]["offset"]
        end = group[-1]["offset"] + group[-1]["duration"]
        dialogue_lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(max(end, start + 0.25))},Caption,,0,0,0,,{two_lines_ar([e['text'] for e in group])}")

    SUBTITLES.write_text(build_ass_header() + "\n".join(dialogue_lines) + "\n", encoding="utf-8")
    for segment in segments:
        Path(segment["path"]).unlink(missing_ok=True)


def mix_music_into_voice() -> None:
    if not BACKGROUND_MUSIC.exists():
        run(["ffmpeg", "-y", "-i", str(VOICE_AUDIO), "-c:a", "libmp3lame", "-b:a", "192k", str(FINAL_AUDIO)])
        return
    run([
        "ffmpeg", "-y", "-i", str(VOICE_AUDIO), "-stream_loop", "-1", "-i", str(BACKGROUND_MUSIC),
        "-filter_complex", f"[0:a]volume=1.0[voice];[1:a]volume={MUSIC_VOLUME}[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=3:normalize=0[aout]",
        "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", "-shortest", str(FINAL_AUDIO),
    ])


def main() -> None:
    if not EPISODE_PATH.exists():
        sys.exit("❌ state/current_episode.json غير موجود.")
    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    narration = normalize_text(str(episode.get("narration", "")))
    if not narration:
        sys.exit("❌ حقل narration غير موجود أو فارغ.")

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    selected_voice_profile = ""
    if TTS_ENGINE == "silma":
        selected_voice_profile = configure_silma_voice_profile()

    phonetic_hints = episode.get("phonetic_hints") or []
    voice_text = apply_phonetic_hints(narration, phonetic_hints)
    voice_text = apply_light_diacritics(voice_text)
    synthesize_voice(voice_text)
    mix_music_into_voice()

    episode.pop("parts", None)
    episode["narration"] = narration
    episode["voice_profile"] = selected_voice_profile or TTS_ENGINE
    episode["voice_audio"] = str(VOICE_AUDIO)
    episode["final_audio"] = str(FINAL_AUDIO)
    episode["subtitles"] = str(SUBTITLES)
    EPISODE_PATH.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    if selected_voice_profile:
        save_voice_to_history(episode, selected_voice_profile)
    print(f"✅ صوت كامل: {FINAL_AUDIO}")
    print(f"✅ ترجمة عربية متزامنة بالكلمة فقط: {SUBTITLES}")
    print(f"✅ تلميحات نطق مُطبّقة: {len(phonetic_hints)}")
    print(f"✅ محرك النطق: {TTS_ENGINE} | أصوات Edge الاحتياطية: {VOICE_CANDIDATES}")


if __name__ == "__main__":
    main()
