"""Transcribe a downloaded episode locally with faster-whisper.

Audio is pre-extracted to a clean WAV via the system ffmpeg binary before
being handed to Whisper. faster-whisper's own internal audio decoder
(PyAV) is pickier about certain containers than ffmpeg's CLI is -- some
sources (e.g. certain Ogg Theora/Vorbis files) trip PyAV with an
av.error.ArgumentError even though ffmpeg itself decodes them without
complaint. Pre-extracting sidesteps that whole category of incompatibility.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .errors import ClipFarmError
from .io_utils import write_json


def _extract_audio(video_path: Path, workdir: Path) -> Path:
    audio_path = workdir / "audio.wav"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",  # no video stream
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15 * 60,
        )
    except subprocess.CalledProcessError as exc:
        detail = " ".join((exc.stderr or "").splitlines()[-5:])
        raise ClipFarmError(
            "transcription",
            f"ffmpeg could not extract audio: {detail[-500:]}",
            "Confirm the download contains an audible track.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ClipFarmError(
            "transcription", "audio extraction exceeded 15 minutes",
        ) from exc

    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        raise ClipFarmError(
            "transcription",
            "ffmpeg produced no usable audio",
            "Confirm the download contains an audible track.",
        )
    return audio_path


def transcribe_episode(video_path: Path, transcript_path: Path) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ClipFarmError("transcription", "faster-whisper is not installed") from exc

    audio_path = _extract_audio(video_path, transcript_path.parent)

    model_size = os.environ.get("WHISPER_MODEL", "small").strip() or "small"
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments_iterator, info = model.transcribe(
            str(audio_path),
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
    except ClipFarmError:
        raise
    except Exception as exc:
        raise ClipFarmError(
            "transcription",
            f"Whisper could not transcribe the source ({type(exc).__name__}: {exc})",
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
