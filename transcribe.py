"""Transcribes the episode locally with faster-whisper.
Free, runs on the GitHub Actions CPU runner, no external account needed.
Returns a list of {start, end, text} word/segment-level entries so we can
build precise burned-in captions later.
"""

import json
from pathlib import Path

from faster_whisper import WhisperModel

# "small" is a good speed/accuracy tradeoff for CI runners with no GPU.
# Bump to "medium" if quality matters more than runtime.
MODEL_SIZE = "small"


def transcribe_audio(video_path: Path, workdir: Path) -> list[dict]:
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    segments, _info = model.transcribe(str(video_path), word_timestamps=True)

    transcript = []
    for segment in segments:
        transcript.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": [
                {"start": w.start, "end": w.end, "word": w.word}
                for w in (segment.words or [])
            ],
        })

    (workdir / "transcript.json").write_text(json.dumps(transcript, indent=2))
    return transcript
