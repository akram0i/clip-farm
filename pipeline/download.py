"""Download one source episode.

Source URLs fall into a few categories that each need different handling:

1. Video platforms (YouTube, Vimeo, etc.) -- yt-dlp's dedicated extractors,
   with player-client fallbacks since YouTube increasingly challenges
   requests from cloud/datacenter IP ranges (including GitHub Actions
   runners) with a "Sign in to confirm you're not a bot" error. This is
   unrelated to the specific video and isn't something retrying the same
   request fixes -- yt-dlp maintains alternate "player clients" (tv,
   mweb, ios, etc.) that fetch video info through different, less
   aggressively gated endpoints, tried in sequence.
2. Google Drive share links -- these need a dedicated confirmation-token
   handshake for any file large enough to trigger Drive's "can't scan
   this file for viruses" interstitial. A plain GET or yt-dlp's generic
   extractor gets that HTML page back instead of the file.
3. Dropbox share links -- normalized to their direct-download form
   (dl=1) before download.
4. Plain direct file links (a raw .mp4/.mov/.ogv URL, or a link from an
   file host that has no click-through/JS gate) -- yt-dlp's generic
   extractor handles these well as-is.

What's explicitly NOT handled: services that require a JS-rendered
click-through with no documented API (e.g. WeTransfer). Those need a
different link from the campaign (Drive/Dropbox/a raw file URL) --
there's no free, reliable way to automate a click-through flow.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .errors import ClipFarmError

# Ordered by how reliably each has avoided the bot-check in practice.
# "default" (no override) goes first since it's fastest when it works.
_PLAYER_CLIENT_FALLBACKS = [None, "tv", "mweb", "ios"]

_USER_AGENT = "ClipFarm/1.0 (+https://github.com/akram0i/clip-farm) yt-dlp"

_GOOGLE_DRIVE_ID_PATTERNS = [
    re.compile(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)"),
    re.compile(r"drive\.google\.com/uc\?.*[?&]id=([a-zA-Z0-9_-]+)"),
    re.compile(r"docs\.google\.com/uc\?.*[?&]id=([a-zA-Z0-9_-]+)"),
]


def _google_drive_file_id(url: str) -> str | None:
    for pattern in _GOOGLE_DRIVE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _normalize_dropbox_url(url: str) -> str:
    parsed = urlparse(url)
    if "dropbox.com" not in parsed.netloc:
        return url
    # A Dropbox share link previews in-browser unless dl=1 is set.
    if "dl=1" in parsed.query:
        return url
    query = parse_qs(parsed.query)
    query.pop("dl", None)
    rebuilt = parsed._replace(query="&".join(f"{k}={v[0]}" for k, v in query.items()))
    separator = "&" if rebuilt.query else "?"
    return f"{rebuilt.geturl()}{separator}dl=1"


def _download_from_google_drive(file_id: str, workdir: Path) -> Path:
    """Handles Drive's virus-scan confirmation interstitial for larger
    files -- a plain GET on the share link returns that HTML warning page
    instead of the actual file unless the confirmation token is replayed."""
    try:
        import requests
    except ImportError as exc:
        raise ClipFarmError("download", "the requests library is not installed") from exc

    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})
    base_url = "https://drive.google.com/uc"

    try:
        response = session.get(base_url, params={"id": file_id, "export": "download"}, stream=True, timeout=60)
        token = None
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                token = value
        if token is None and "text/html" in response.headers.get("content-type", ""):
            match = re.search(r"confirm=([0-9A-Za-z_-]+)", response.text)
            if match:
                token = match.group(1)
        if token:
            response = session.get(
                base_url,
                params={"id": file_id, "export": "download", "confirm": token},
                stream=True,
                timeout=60,
            )

        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            raise ClipFarmError(
                "download",
                "Google Drive returned a page instead of a file",
                "Confirm the Drive link's sharing setting is \"Anyone with the link\" and that it points at a single file, not a folder.",
            )

        destination = workdir / "source.mp4"
        with open(destination, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    except requests.RequestException as exc:
        raise ClipFarmError("download", f"Google Drive download failed: {exc}") from exc

    if not destination.exists() or destination.stat().st_size < 100_000:
        raise ClipFarmError("download", "downloaded source file is unexpectedly small")
    return destination.resolve()


def download_episode(url: str, workdir: Path) -> Path:
    drive_file_id = _google_drive_file_id(url)
    if drive_file_id:
        return _download_from_google_drive(drive_file_id, workdir)

    url = _normalize_dropbox_url(url)
    return _download_via_yt_dlp(url, workdir)


def _download_via_yt_dlp(url: str, workdir: Path) -> Path:
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
            _USER_AGENT,
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
