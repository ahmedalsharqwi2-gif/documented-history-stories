#!/usr/bin/env python3
"""اختبار محلي لتوليد صوت عربي باستخدام Coqui XTTS-v2.

التثبيت:
    python -m pip install coqui-tts

مثال بصوت مرجعي:
    python scripts/test_xtts_arabic.py \
        --speaker-wav assets/voice_reference.wav \
        --text "هل تستطيع خدعة عسكرية واحدة أن تغير نتيجة معركة كاملة؟" \
        --output output/xtts_arabic_test.wav

ملاحظات:
- ملف speaker-wav يجب أن يحتوي صوت المتحدث المطلوب، ويفضل أن يكون واضحا
  ومدته من 6 إلى 15 ثانية، بلا موسيقى أو ضوضاء أو أكثر من متحدث.
- استخدم --cpu على جهاز بلا GPU. سيعمل، لكنه أبطأ بكثير.
- استنساخ صوت شخص آخر يتطلب إذنه الصريح.
"""

from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
DEFAULT_TEXT = "هل تستطيع خدعة عسكرية واحدة أن تغير نتيجة معركة كاملة؟"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Arabic speech locally with Coqui XTTS-v2."
    )
    parser.add_argument(
        "--speaker-wav",
        required=True,
        type=Path,
        help="Clean reference voice WAV file used for voice cloning.",
    )
    parser.add_argument(
        "--text",
        default=DEFAULT_TEXT,
        help="Arabic text to synthesize.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/xtts_arabic_test.wav"),
        help="Output WAV path.",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU inference. GPU is used automatically when available otherwise.",
    )
    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        help=f"Coqui model name (default: {MODEL_NAME}).",
    )
    parser.add_argument(
        "--no-split-sentences",
        action="store_true",
        help="Do not split long text into sentences before synthesis.",
    )
    return parser.parse_args()


def validate_reference(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Reference audio does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Reference path is not a file: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Reference audio is empty: {path}")


def inspect_wav(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        duration = frames / rate if rate else 0.0
        return {
            "duration_seconds": round(duration, 3),
            "sample_rate": rate,
            "channels": wav.getnchannels(),
            "sample_width_bytes": wav.getsampwidth(),
            "frames": frames,
            "bytes": path.stat().st_size,
        }


def main() -> int:
    args = parse_args()
    try:
        validate_reference(args.speaker_wav)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        from TTS.api import TTS
    except ImportError:
        print(
            "ERROR: Coqui TTS is not installed. Run: python -m pip install coqui-tts",
            file=sys.stderr,
        )
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    use_gpu = not args.cpu
    started = time.perf_counter()

    print(f"Loading model: {args.model}")
    print(f"Device: {'GPU if available' if use_gpu else 'CPU'}")
    tts = TTS(model_name=args.model, progress_bar=True, gpu=use_gpu)
    loaded = time.perf_counter()

    print("Generating Arabic speech...")
    tts.tts_to_file(
        text=args.text,
        speaker_wav=str(args.speaker_wav),
        language="ar",
        file_path=str(args.output),
        split_sentences=not args.no_split_sentences,
    )
    finished = time.perf_counter()

    if not args.output.exists() or args.output.stat().st_size == 0:
        print("ERROR: XTTS did not create a non-empty output file.", file=sys.stderr)
        return 4

    try:
        metadata = inspect_wav(args.output)
    except (wave.Error, OSError) as exc:
        print(f"ERROR: output is not a readable WAV file: {exc}", file=sys.stderr)
        return 5

    print("\nXTTS test completed successfully")
    print(f"Model load seconds: {loaded - started:.2f}")
    print(f"Generation seconds: {finished - loaded:.2f}")
    print(f"Total seconds: {finished - started:.2f}")
    print(f"Output: {args.output.resolve()}")
    print(f"Audio metadata: {metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
