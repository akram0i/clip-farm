"""Render centered 9:16 MP4 clips with faithful burned-in ASS captions."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import ClipFarmError


def _ass_time(seconds: float) -> str:
    value = max(0.0, seconds)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    remainder = value % 60
    return f"{hours}:{minutes:02d}:{remainder:05.2f}"


def _ass_escape(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def write_ass(captions: list[dict[str, Any]], clip_start: float, output_path: Path) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Captions,DejaVu Sans,68,&H00FFFFFF,&H00FFFFFF,&H00101010,&H78000000,-1,0,0,0,100,100,0,0,1,5,1,2,88,88,430,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for caption in captions:
        start = max(0.0, float(caption["start"]) - clip_start)
        end = max(start + 0.08, float(caption["end"]) - clip_start)
        text = _ass_escape(str(caption["text"]).strip())
        if text:
            lines.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Captions,,0,0,0,,{text}\n"
            )
    output_path.write_text("".join(lines), encoding="utf-8")


def _filter_escape(path: Path) -> str:
    return str(path.resolve()).replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


def render_clip(
    source_video: Path,
    start: float,
    end: float,
    captions: list[dict[str, Any]],
    output_dir: Path,
    clip_number: int,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise ClipFarmError("render", "ffmpeg is not installed")
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"clip-{clip_number:02d}"
    subtitles = output_dir / f"{stem}.ass"
    output = output_dir / f"{stem}.mp4"
    write_ass(captions, start, subtitles)
    duration = end - start
    subtitle_filter = _filter_escape(subtitles)
    video_filter = (
        "crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':"
        "x='(iw-ow)/2':y='(ih-oh)/2',"
        "scale=1080:1920:flags=lanczos,"
        f"ass='{subtitle_filter}'"
    )
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", str(source_video), "-t", f"{duration:.3f}",
        "-map", "0:v:0", "-map", "0:a?", "-vf", video_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30 * 60)
    except subprocess.TimeoutExpired as exc:
        raise ClipFarmError("render", f"clip {clip_number} exceeded the 30-minute render limit") from exc
    except subprocess.CalledProcessError as exc:
        detail = " ".join((exc.stderr or "ffmpeg returned an error").splitlines()[-8:])[-700:]
        raise ClipFarmError(
            "render",
            f"clip {clip_number} failed: {detail}",
            "Inspect the Render clips step; the source codec may be unsupported.",
        ) from exc
    if not output.exists() or output.stat().st_size < 100_000:
        raise ClipFarmError("render", f"clip {clip_number} output is missing or empty")
    return output
