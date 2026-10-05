#!/usr/bin/env python3
"""Deterministic audio matching metadata for documentary clips.

This module never treats embedded audio as historical evidence. It records the
presence and technical properties of the source audio, applies a conservative
mix decision, and leaves semantic/editorial overrides explicit in the manifest.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

AUDIO_DECISIONS = {
    "ORIGINAL AUDIO",
    "ORIGINAL AUDIO + VOICE",
    "ORIGINAL AUDIO + VOICE DUCKING",
    "ORIGINAL AUDIO + MUSIC",
    "ORIGINAL AUDIO + VOICE + MUSIC",
    "VOICE ONLY",
    "MUTE",
}


def probe_audio(path: Path) -> dict[str, Any]:
    """Return technical audio facts without guessing what the sound means."""
    command = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,codec_type,channels,sample_rate,duration",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe audio inspection failed for {path}: {result.stderr[-300:]}")
    payload = json.loads(result.stdout or "{}")
    stream = (payload.get("streams") or [{}])[0]
    if not stream.get("codec_type"):
        return {"present": False, "codec": "", "channels": 0, "sample_rate": "", "duration": 0.0}
    return {
        "present": True,
        "codec": str(stream.get("codec_name") or "unknown"),
        "channels": int(stream.get("channels") or 0),
        "sample_rate": str(stream.get("sample_rate") or ""),
        "duration": float(stream.get("duration") or 0.0),
    }


def choose_decision(audio: dict[str, Any], override: str | None = None) -> tuple[str, str]:
    """Choose a safe default; semantic overrides must be one of the allowlist."""
    if override:
        decision = " ".join(str(override).upper().split())
        if decision not in AUDIO_DECISIONS:
            raise ValueError(f"Unsupported audio decision: {override}")
        return decision, "editorial manifest override"
    if not audio.get("present"):
        return "VOICE ONLY", "no embedded source audio detected"
    return "VOICE ONLY", "embedded sound requires scene/audio review before retention"


def build_audio_record(path: Path, *, override: str | None = None) -> dict[str, Any]:
    facts = probe_audio(path)
    decision, rationale = choose_decision(facts, override)
    return {
        "source": "embedded_clip_audio" if facts["present"] else "none",
        "analysis": facts,
        "decision": decision,
        "rationale": rationale,
        "historical_claim": False,
        "semantic_match_review": "required before publication",
    }


def validate_manifest(clips: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate that every clip has an explicit, auditable audio decision."""
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    for index, clip in enumerate(clips, 1):
        record = clip.get("audio") if isinstance(clip, dict) else None
        if not isinstance(record, dict):
            errors.append(f"clip #{index} missing audio analysis")
            continue
        decision = " ".join(str(record.get("decision") or "").upper().split())
        if decision not in AUDIO_DECISIONS:
            errors.append(f"clip #{index} has unsupported audio decision: {decision or '<empty>'}")
        if decision.startswith("ORIGINAL AUDIO") and record.get("semantic_match_review") != "PASS":
            errors.append(f"clip #{index} original audio has no semantic match approval")
        analysis = record.get("analysis")
        if not isinstance(analysis, dict) or "present" not in analysis:
            errors.append(f"clip #{index} missing technical audio analysis")
        records.append({"file": clip.get("file", ""), "keyword": clip.get("keyword", ""), **record})
    return {"passed": not errors, "clip_count": len(clips), "records": records, "errors": errors}
