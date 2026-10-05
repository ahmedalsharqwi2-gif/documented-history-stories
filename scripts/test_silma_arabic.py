#!/usr/bin/env python3
"""اختبار SILMA TTS v1 لتوليد صوت عربي محلياً.

تثبيت SILMA في بيئة منفصلة:
    python3 -m venv .venv-silma
    source .venv-silma/bin/activate
    python -m pip install --upgrade pip
    python -m pip install silma-tts

مثال:
    python scripts/test_silma_arabic.py \
        --ref-audio assets/voice_reference.wav \
        --ref-text "هذا نص التسجيل المرجعي الواضح." \
        --text-file state/current_episode.json \
        --output output/silma_arabic_test.wav
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

DEFAULT_TEXT = (
    "هل تستطيع خدعة تاريخية واحدة أن تغير نتيجة معركة كاملة؟ "
    "هذه جملة اختبار باللغة العربية الفصحى."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Arabic audio with SILMA TTS v1")
    parser.add_argument("--ref-audio", required=True, type=Path, help="Clean reference WAV")
    parser.add_argument("--ref-text", default=None, help="Exact transcript of reference audio")
    parser.add_argument("--text", default=None, help="Text to synthesize")
    parser.add_argument(
        "--text-file",
        type=Path,
        default=None,
        help="JSON episode file; reads its narration field",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/silma_arabic_test.wav"),
        help="Output WAV path",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed")
    parser.add_argument("--seed", type=int, default=None, help="Optional reproducibility seed")
    return parser.parse_args()


def load_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text.strip()
    if args.text_file:
        data = json.loads(args.text_file.read_text(encoding="utf-8"))
        text = str(data.get("narration", "")).strip()
        if text:
            return text
        raise ValueError(f"No narration field found in {args.text_file}")
    return DEFAULT_TEXT


def main() -> int:
    args = parse_args()
    if not args.ref_audio.is_file():
        print(f"ERROR: reference audio does not exist: {args.ref_audio}", file=sys.stderr)
        return 2
    if args.speed <= 0:
        print("ERROR: --speed must be greater than zero", file=sys.stderr)
        return 2
    try:
        text = load_text(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not load synthesis text: {exc}", file=sys.stderr)
        return 2

    try:
        from silma_tts.api import SilmaTTS
    except ImportError:
        print(
            "ERROR: SILMA is not installed in this Python environment. "
            "Run: python -m pip install silma-tts",
            file=sys.stderr,
        )
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print("Loading SILMA TTS v1...")
    started = time.perf_counter()
    silma = SilmaTTS()
    loaded = time.perf_counter()
    print(f"Generating {len(text.split())} Arabic words...")
    silma.infer(
        ref_file=str(args.ref_audio),
        ref_text=args.ref_text,
        gen_text=text,
        file_wave=str(args.output),
        seed=args.seed,
        speed=args.speed,
    )
    finished = time.perf_counter()

    if not args.output.exists() or args.output.stat().st_size == 0:
        print("ERROR: SILMA did not create a non-empty WAV file", file=sys.stderr)
        return 4
    print("SILMA test completed successfully")
    print(f"Model load seconds: {loaded - started:.2f}")
    print(f"Generation seconds: {finished - loaded:.2f}")
    print(f"Total seconds: {finished - started:.2f}")
    print(f"Output: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
