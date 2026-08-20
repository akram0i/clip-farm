"""Transcribe a downloaded episode locally with faster-whisper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .errors import ClipFarmError
from .io_utils import write_json


def transcribe_episode(video_path: Path, transcript_path: Path) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ClipFarmError("transcription", "faster-whisper is not installed") from exc

    model_size = os.environ.get("WHISPER_MODEL", "small").strip() or "small"
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments_iterator, info = model.transcribe(
            str(video_path),
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
        )
        segments = []
        for segment in segments_iterator:
            words = [
                {
                    "start": float(word.start) if word.start is not None else float(segment.start),
                    "end": float(word.end) if word.end is not None else float(segment.end),
                    "word": word.word.strip(),
                }
                for word in (segment.words or [])
                if word.word and word.word.strip()
            ]
            text = segment.text.strip()
            if text:
                segments.append({
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                    "words": words,
                })
    except Exception as exc:
        raise ClipFarmError(
            "transcription",
            f"Whisper could not transcribe the source ({type(exc).__name__})",
            "Confirm the download contains an audible track, then retry the run.",
        ) from exc

    if not segments:
        raise ClipFarmError(
            "transcription",
            "Whisper returned no spoken transcript",
            "Use a source with clear speech and an audible track.",
        )

    payload = {
        "model": model_size,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration_seconds": segments[-1]["end"],
        "segments": segments,
    }
    write_json(transcript_path, payload)
    return payload
