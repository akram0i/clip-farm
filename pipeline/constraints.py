"""Deterministic extraction and enforcement of campaign constraints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .errors import ClipFarmError

ABSOLUTE_MIN_SECONDS = 15.0
ABSOLUTE_MAX_SECONDS = 45.0
DEFAULT_MIN_SECONDS = 20.0
DEFAULT_MAX_SECONDS = 35.0

_RANGE_PATTERNS = (
    re.compile(r"\b(?:between\s+)?(\d{1,3}(?:\.\d+)?)\s*(?:-|–|—|to|and)\s*(\d{1,3}(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", re.I),
    re.compile(r"\b(?:length|duration)\s*:?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d{1,3}(?:\.\d+)?)\b", re.I),
)
_MIN_PATTERN = re.compile(r"\b(?:minimum|min\.?|at\s+least)\s*(?:length\s*)?(?:of\s*)?(\d{1,3}(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", re.I)
_MAX_PATTERN = re.compile(r"\b(?:maximum|max\.?|up\s+to|no\s+(?:more|longer)\s+than)\s*(?:length\s*)?(?:of\s*)?(\d{1,3}(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", re.I)
_HASHTAG_PATTERN = re.compile(r"(?<![\w#])#[A-Za-z0-9_]+")
_PHRASE_PATTERN = re.compile(
    r"\b(?:must|required\s+to|needs?\s+to|and)\s+(?:include|mention|say|contain)\s+"
    r"(?:the\s+(?:word|phrase|message)\s+)?[\"'“‘]([^\"'”’]{2,100})[\"'”’]",
    re.I,
)


@dataclass(frozen=True)
class CampaignConstraints:
    minimum_seconds: float
    maximum_seconds: float
    required_hashtags: tuple[str, ...]
    required_phrases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimum_seconds": self.minimum_seconds,
            "maximum_seconds": self.maximum_seconds,
            "required_hashtags": list(self.required_hashtags),
            "required_phrases": list(self.required_phrases),
        }


def derive_constraints(requirements: str, available_content: str = "") -> CampaignConstraints:
    text = f"{requirements}\n{available_content}"
    requested_min: float | None = None
    requested_max: float | None = None

    for pattern in _RANGE_PATTERNS:
        match = pattern.search(text)
        if match:
            requested_min, requested_max = map(float, match.groups())
            break
    if requested_min is None:
        match = _MIN_PATTERN.search(text)
        if match:
            requested_min = float(match.group(1))
    if requested_max is None:
        match = _MAX_PATTERN.search(text)
        if match:
            requested_max = float(match.group(1))

    if requested_min is not None and requested_max is not None and requested_min > requested_max:
        raise ClipFarmError("input", "campaign minimum clip length exceeds its maximum")

    minimum = requested_min if requested_min is not None else DEFAULT_MIN_SECONDS
    maximum = requested_max if requested_max is not None else DEFAULT_MAX_SECONDS
    minimum = max(minimum, ABSOLUTE_MIN_SECONDS)
    maximum = min(maximum, ABSOLUTE_MAX_SECONDS)
    if minimum > maximum:
        raise ClipFarmError(
            "input",
            "campaign clip-length rule does not overlap ClipFarm's hard 15–45 second bounds",
            "Choose a compatible campaign or correct the pasted requirement.",
        )

    hashtag_values: list[str] = []
    hashtag_keys: set[str] = set()
    for tag in _HASHTAG_PATTERN.findall(text):
        key = tag.casefold()
        if key not in hashtag_keys:
            hashtag_keys.add(key)
            hashtag_values.append(tag)
    hashtags = tuple(hashtag_values)
    phrases = tuple(dict.fromkeys(match.strip() for match in _PHRASE_PATTERN.findall(text)))
    return CampaignConstraints(minimum, maximum, hashtags, phrases)


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def validate_candidate_window(
    candidate: dict[str, Any],
    constraints: CampaignConstraints,
    transcript_end: float,
) -> str | None:
    try:
        start = float(candidate["start_seconds"])
        end = float(candidate["end_seconds"])
    except (KeyError, TypeError, ValueError):
        return "timestamps are missing or invalid"
    duration = end - start
    if start < 0 or end > transcript_end + 1.0 or end <= start:
        return "timestamps fall outside the transcript"
    if duration < constraints.minimum_seconds - 0.05:
        return f"duration {duration:.1f}s is below {constraints.minimum_seconds:g}s"
    if duration > constraints.maximum_seconds + 0.05:
        return f"duration {duration:.1f}s exceeds {constraints.maximum_seconds:g}s"
    if not bool(candidate.get("campaign_compliant")):
        return "AI marked the candidate non-compliant"
    for score in ("virality_score", "hook_strength", "loop_potential"):
        try:
            value = int(candidate[score])
        except (KeyError, TypeError, ValueError):
            return f"{score} is missing or invalid"
        if not 0 <= value <= 100:
            return f"{score} is outside 0–100"
    return None


def merge_required_hashtags(suggested: list[str], required: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in [*suggested, *required]:
        tag = str(raw).strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(tag)
    return normalized
