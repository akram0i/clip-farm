"""Downloads the source episode with yt-dlp (works for YouTube and most
podcast host URLs). No account/API key needed."""

import subprocess
from pathlib import Path


def download_episode(url: str, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    output_template = str(workdir / "source.%(ext)s")

    subprocess.run(
        [
            "yt-dlp",
            "-f", "bestvideo[height<=1080]+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            url,
        ],
        check=True,
    )

    # Find whatever file yt-dlp produced
    matches = list(workdir.glob("source.*"))
    if not matches:
        raise RuntimeError("yt-dlp did not produce an output file")
    return matches[0]
