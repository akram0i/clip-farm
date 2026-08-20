"""Download one source episode with yt-dlp.

YouTube increasingly challenges requests from cloud/datacenter IP ranges
(including GitHub Actions runners) with a "Sign in to confirm you're not
a bot" error. This is unrelated to the specific video and isn't something
retrying the same request fixes. yt-dlp maintains a set of alternate
"player clients" (tv, mweb, ios, etc.) that fetch video info through
different, less aggressively gated endpoints -- we try them in sequence
until one works, rather than failing on the very first block.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import ClipFarmError

# Ordered by how reliably each has avoided the bot-check in practice.
# "default" (no override) goes first since it's fastest when it works.
_PLAYER_CLIENT_FALLBACKS = [None, "tv", "mweb", "ios"]


def download_episode(url: str, workdir: Path) -> Path:
    if not shutil.which("yt-dlp"):
        raise ClipFarmError("download", "yt-dlp is not installed")

    output_template = str(workdir / "source.%(ext)s")
    last_error: subprocess.CalledProcessError | None = None

    for client in _PLAYER_CLIENT_FALLBACKS:
        command = [
            "yt-dlp",
            "--no-playlist",
            "--newline",
            "--no-progress",
            "--retries",
            "5",
            "--fragment-retries",
            "5",
            "--socket-timeout",
            "60",
            "--user-agent",
            "ClipFarm/1.0 (+https://github.com/akram0i/clip-farm) yt-dlp",
            "-f",
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "--merge-output-format",
            "mp4",
            "--print",
            "after_move:filepath",
            "-o",
            output_template,
        ]
        if client:
            command += ["--extractor-args", f"youtube:player_client={client}"]
        command.append(url)

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=45 * 60,
            )
            break
        except subprocess.TimeoutExpired as exc:
            raise ClipFarmError(
                "download",
                "source download exceeded 45 minutes",
                "Try a shorter source or verify that the host is responding.",
            ) from exc
        except subprocess.CalledProcessError as exc:
            last_error = exc
            continue
    else:
        detail = _tail((last_error.stderr or last_error.stdout or "") if last_error else "yt-dlp returned an error")
        is_bot_check = "sign in to confirm" in detail.lower() or "not a bot" in detail.lower()
        recovery = (
            "YouTube is blocking automated downloads from this network for this video. "
            "This isn't specific to your source URL -- if the campaign provides a direct "
            "download link (Google Drive, Dropbox, a raw video file, etc.) use that instead."
            if is_bot_check
            else "Open the source URL in a private window and confirm it is public and playable."
        )
        raise ClipFarmError("download", detail, recovery) from last_error

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
