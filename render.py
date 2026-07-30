"""Renders a single clip: trims to the chosen window, crops to 9:16, and
burns in bold top-third captions (muted-viewing friendly, per the research
that ~85% of viewers watch with sound off first)."""

import subprocess
from pathlib import Path


def _build_ass_subtitles(captions: list[dict], clip_start: float, output_path: Path) -> None:
    """Writes an .ass subtitle file with bold, top-third-positioned captions,
    timestamps re-based to the clip's own start (0:00)."""

    def fmt_time(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Alignment, MarginV
Style: Default,Arial,72,&H00FFFFFF,&H00000000,1,8,220

[Events]
Format: Layer, Start, End, Style, Text
"""
    lines = [header]
    for seg in captions:
        start = max(0.0, seg["start"] - clip_start)
        end = max(0.0, seg["end"] - clip_start)
        text = seg["text"].replace("\n", " ")
        lines.append(f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Default,{text}\n")

    output_path.write_text("".join(lines))


def render_clip(
    source_video: Path,
    start: float,
    end: float,
    captions: list[dict],
    output_dir: Path,
    clip_index: int,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    duration = end - start

    subs_path = output_dir / f"clip_{clip_index}.ass"
    _build_ass_subtitles(captions, start, subs_path)

    output_path = output_dir / f"clip_{clip_index}.mp4"

    # Crop to 9:16 centered, scale to 1080x1920, burn in the .ass captions.
    vf = (
        "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',"
        "scale=1080:1920,"
        f"ass={subs_path}"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source_video),
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            str(output_path),
        ],
        check=True,
    )

    return output_path
