"""Resolve reference-audio voice profiles bundled under assets/voices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def resolve_reference_profile(
    profile: str = "",
    config_path: str | Path = "assets/voices/voice_profiles.json",
    base_dir: str | Path | None = None,
) -> tuple[str, str, Path, str]:
    """Return (key, label, WAV path, transcript) for a configured profile."""
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    catalog_path = Path(config_path)
    if not catalog_path.is_absolute():
        catalog_path = root / catalog_path
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Voice profiles catalog is missing: {catalog_path}")

    data: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    profiles = data.get("profiles") or {}
    selected = profile.strip() or str(data.get("default", "")).strip()
    if selected not in profiles:
        available = ", ".join(sorted(profiles)) or "none"
        raise ValueError(f"Unknown voice profile '{selected}'. Available: {available}")

    entry = profiles[selected]
    wav = Path(str(entry["wav"]))
    transcript_path = Path(str(entry["text"]))
    if not wav.is_absolute():
        wav = root / wav
    if not transcript_path.is_absolute():
        transcript_path = root / transcript_path
    if not wav.is_file():
        raise FileNotFoundError(f"Voice profile '{selected}' WAV is missing: {wav}")
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Voice profile '{selected}' transcript is missing: {transcript_path}")

    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        raise ValueError(f"Voice profile '{selected}' transcript is empty: {transcript_path}")
    return selected, str(entry.get("label", selected)), wav, transcript
