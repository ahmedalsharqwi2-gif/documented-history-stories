"""Create a reel-specific ASS track without changing horizontal-video subtitles."""
from __future__ import annotations

from pathlib import Path

SOURCE_HEIGHT = 1080
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
REEL_TOP_SAFE_MARGIN = 260


def _time_to_cs(value: str) -> int:
    hours, minutes, remainder = value.strip().split(":", 2)
    if "." in remainder:
        seconds, centiseconds = remainder.split(".", 1)
    else:
        seconds, centiseconds = remainder, "0"
    centiseconds = (centiseconds + "00")[:2]
    return ((int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 100) + int(centiseconds)


def _cs_to_time(value: int) -> str:
    value = max(0, int(value))
    hours, remainder = divmod(value, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _scaled_value(value: str, scale: float, *, integer: bool = False) -> str:
    number = float(value) * scale
    if integer:
        return str(max(0, int(round(number))))
    rendered = f"{number:.2f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _reel_style(line: str, fields: list[str], scale: float) -> str:
    values = [value.strip() for value in line.split(":", 1)[1].split(",")]
    if len(values) != len(fields):
        raise ValueError("Invalid ASS Style record")
    style = dict(zip(fields, values))
    for field in ("Fontsize", "Outline", "Shadow", "MarginL", "MarginR"):
        if field in style:
            style[field] = _scaled_value(
                style[field], scale, integer=field in ("Fontsize", "MarginL", "MarginR")
            )
    if "Alignment" not in style or "MarginV" not in style:
        raise ValueError("ASS Style is missing Alignment or MarginV")
    style["Alignment"] = "8"
    style["MarginV"] = str(REEL_TOP_SAFE_MARGIN)
    return "Style: " + ",".join(style[field] for field in fields)


def write_reel_subtitles(
    source_path: Path,
    start_seconds: float,
    end_seconds: float,
    output_path: Path,
) -> Path:
    """Write a clipped 9:16 subtitle track; the source ASS remains untouched."""
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise ValueError("Invalid reel subtitle range")

    range_start = int(round(start_seconds * 100))
    range_end = int(round(end_seconds * 100))
    scale = REEL_HEIGHT / SOURCE_HEIGHT
    source_lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    output_lines: list[str] = []
    section = ""
    style_fields: list[str] = []
    found_x = found_y = False
    styles_written = 0

    for raw_line in source_lines:
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            output_lines.append(raw_line)
            continue

        if section == "[script info]":
            if line.startswith("PlayResX:"):
                output_lines.append(f"PlayResX: {REEL_WIDTH}")
                found_x = True
                continue
            if line.startswith("PlayResY:"):
                output_lines.append(f"PlayResY: {REEL_HEIGHT}")
                found_y = True
                continue

        if section in ("[v4+ styles]", "[v4 styles]"):
            if line.startswith("Format:"):
                style_fields = [field.strip() for field in line.split(":", 1)[1].split(",")]
            elif line.startswith("Style:"):
                if not style_fields:
                    raise ValueError("ASS Style record appears before its Format")
                output_lines.append(_reel_style(line, style_fields, scale))
                styles_written += 1
                continue

        if section == "[events]" and line.startswith("Dialogue:"):
            fields = line.split(":", 1)[1].lstrip().split(",", 9)
            if len(fields) != 10:
                raise ValueError("Invalid ASS Dialogue record")
            event_start = _time_to_cs(fields[1])
            event_end = _time_to_cs(fields[2])
            clipped_start = max(event_start, range_start)
            clipped_end = min(event_end, range_end)
            if clipped_end <= clipped_start:
                continue
            fields[1] = _cs_to_time(clipped_start - range_start)
            fields[2] = _cs_to_time(clipped_end - range_start)
            # Use the new 9:16 style's scaled margins, not old event overrides.
            fields[5:8] = ["0", "0", "0"]
            output_lines.append("Dialogue: " + ",".join(fields))
            continue

        output_lines.append(raw_line)

    if not found_x or not found_y or styles_written == 0:
        raise ValueError("ASS source must define PlayResX, PlayResY, and at least one Style")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return output_path
