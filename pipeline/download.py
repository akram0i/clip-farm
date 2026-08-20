"""Download one source episode with yt-dlp."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import ClipFarmError


def download_episode(url: str, workdir: Path) -> Path:
    if not shutil.which("yt-dlp"):
        raise ClipFarmError("download", "yt-dlp is not installed")

    output_template = str(workdir / "source.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--newline",
        "--no-progress",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "-f",
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format",
        "mp4",
        "--print",
        "after_move:filepath",
        "-o",
        output_template,
        url,
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=45 * 60,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClipFarmError(
            "download",
            "source download exceeded 45 minutes",
            "Try a shorter source or verify that the host is responding.",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = _tail(exc.stderr or exc.stdout or "yt-dlp returned an error")
        raise ClipFarmError(
            "download",
            detail,
            "Open the source URL in a private window and confirm it is public and playable.",
        ) from exc

    printed_paths = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    candidates = [path for path in printed_paths if path.exists()]
    if not candidates:
        candidates = [
            path
            for path in workdir.glob("source.*")
            if path.is_file() and not path.name.endswith((".part", ".ytdl"))
        ]
    if not candidates:
        raise ClipFarmError("download", "yt-dlp finished without producing a source file")

    source = max(candidates, key=lambda path: path.stat().st_size)
    if source.stat().st_size < 100_000:
        raise ClipFarmError("download", "downloaded source file is unexpectedly small")
    return source.resolve()


def _tail(value: str, limit: int = 700) -> str:
    cleaned = " ".join(line.strip() for line in value.splitlines()[-8:] if line.strip())
    return cleaned[-limit:] or "yt-dlp returned an error"
