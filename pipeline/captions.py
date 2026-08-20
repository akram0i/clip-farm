"""Build faithful, readable caption events from local Whisper timestamps."""

from __future__ import annotations

from typing import Any


def transcript_text_for_window(transcript: list[dict[str, Any]], start: float, end: float) -> str:
    pieces: list[str] = []
    for segment in transcript:
        if float(segment.get("end", 0)) <= start or float(segment.get("start", 0)) >= end:
            continue
        words = [
            str(word.get("word", "")).strip()
            for word in (segment.get("words") or [])
            if float(word.get("end") or 0) > start
            and float(word.get("start") or 0) < end
            and str(word.get("word", "")).strip()
        ]
        pieces.append(" ".join(words) if words else str(segment.get("text", "")).strip())
    return " ".join(piece for piece in pieces if piece).strip()


def caption_events_for_window(
    transcript: list[dict[str, Any]],
    start: float,
    end: float,
    max_words: int = 4,
    max_duration: float = 1.35,
) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in transcript:
        for word in segment.get("words") or []:
            word_start = float(word.get("start") or 0)
            word_end = float(word.get("end") or word_start)
            if word_end > start and word_start < end:
                words.append({
                    "start": max(start, word_start),
                    "end": min(end, max(word_end, word_start + 0.08)),
                    "text": str(word.get("word", "")).strip(),
                })

    if not words:
        return [
            {
                "start": max(start, float(segment.get("start", start))),
                "end": min(end, float(segment.get("end", end))),
                "text": str(segment.get("text", "")).strip(),
            }
            for segment in transcript
            if float(segment.get("end", 0)) > start
            and float(segment.get("start", 0)) < end
            and str(segment.get("text", "")).strip()
        ]

    events: list[dict[str, Any]] = []
    group: list[dict[str, Any]] = []
    for word in words:
        group.append(word)
        elapsed = group[-1]["end"] - group[0]["start"]
        ends_phrase = word["text"].endswith((".", "?", "!", ",", ";", ":"))
        if len(group) >= max_words or elapsed >= max_duration or (ends_phrase and len(group) >= 2):
            events.append(_event_from_group(group))
            group = []
    if group:
        events.append(_event_from_group(group))
    return events


def _event_from_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "start": group[0]["start"],
        "end": group[-1]["end"],
        "text": " ".join(word["text"] for word in group).strip(),
    }
