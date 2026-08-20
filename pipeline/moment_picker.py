"""Select campaign-compliant source moments with Gemini structured output."""

from __future__ import annotations

import os
import time
from typing import Any

from .captions import transcript_text_for_window
from .config import Campaign
from .constraints import (
    CampaignConstraints,
    merge_required_hashtags,
    normalize_text,
    validate_candidate_window,
)
from .errors import ClipFarmError

SYSTEM_PROMPT = """You are an exacting short-form video producer. Select only
verbatim, contiguous moments from the provided transcript. Never invent dialogue,
change timestamps, or propose visual elements that are absent from the source.

Every chosen moment should have:
- Hook (first 0–2 seconds): contradiction, tension, surprising claim, or bold statement.
- Context (roughly 2–7 seconds): who this is for and what is at stake.
- Payoff: a useful reveal, insight, or punchline.
- Loop: a natural ending that flows into or reopens the hook.

The CAMPAIGN REQUIREMENTS are binding. Exclude a moment if it violates a banned
topic/style, omits required in-clip messaging, falls outside the supplied duration
bounds, or cannot be supported by literal transcript evidence. Post captions may be
new copy, but spoken hook/evidence must be verbatim. Return the strongest compliant
moments only, up to 15; aim for at least 5 when the source genuinely supports them.
Do not manufacture weak or non-compliant candidates to reach a quota.
"""


def pick_moments(
    transcript_payload: dict[str, Any],
    campaign: Campaign,
    constraints: CampaignConstraints,
) -> list[dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ClipFarmError(
            "selection",
            "GEMINI_API_KEY is missing",
            "Add it under repository Settings → Secrets and variables → Actions.",
        )

    try:
        from google import genai
        from google.genai import types
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise ClipFarmError("selection", "Google GenAI or Pydantic is not installed") from exc

    class Candidate(BaseModel):
        start_seconds: float
        end_seconds: float
        hook_text: str
        virality_score: int = Field(ge=0, le=100)
        hook_strength: int = Field(ge=0, le=100)
        loop_potential: int = Field(ge=0, le=100)
        reason: str
        post_caption: str
        hashtags: list[str]
        campaign_compliant: bool
        compliance_evidence: list[str]

    class CandidateBatch(BaseModel):
        candidates: list[Candidate]

    segments = transcript_payload["segments"]
    transcript_text = "\n".join(
        f"[{segment['start']:.2f}–{segment['end']:.2f}] {segment['text']}"
        for segment in segments
    )
    prompt = f"""CAMPAIGN BRIEF
{campaign.ai_brief()}

DETERMINISTIC DURATION BOUNDS
Every candidate must be between {constraints.minimum_seconds:g} and
{constraints.maximum_seconds:g} seconds inclusive.

DETECTED REQUIRED HASHTAGS
{', '.join(constraints.required_hashtags) or '(none detected)'}

DETECTED REQUIRED IN-CLIP PHRASES
{', '.join(constraints.required_phrases) or '(none detected; still interpret the full requirements)'}

TIMESTAMPED TRANSCRIPT
{transcript_text}
"""

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=180_000))
    response = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=CandidateBatch,
                    temperature=0.25,
                ),
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt * 4)
    if response is None:
        raise ClipFarmError(
            "selection",
            f"Gemini failed after 3 attempts ({type(last_error).__name__}: {last_error})",
            "Check the API key, free-tier quota, and model availability, then retry.",
        ) from last_error

    try:
        parsed = response.parsed
        batch = parsed if isinstance(parsed, CandidateBatch) else CandidateBatch.model_validate_json(response.text)
    except Exception as exc:
        raise ClipFarmError(
            "selection",
            "Gemini returned an invalid candidate structure",
            "Retry once; if it repeats, inspect the Select moments step in Actions.",
        ) from exc

    transcript_end = float(transcript_payload["duration_seconds"])
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
    seen_windows: set[tuple[int, int]] = set()
    for proposal in batch.candidates[:15]:
        candidate = proposal.model_dump()
        failure = validate_candidate_window(candidate, constraints, transcript_end)
        if failure:
            rejected.append(f"{candidate.get('start_seconds')}–{candidate.get('end_seconds')}: {failure}")
            continue

        start = float(candidate["start_seconds"])
        end = float(candidate["end_seconds"])
        window_key = (round(start), round(end))
        if window_key in seen_windows:
            continue
        source_text = transcript_text_for_window(segments, start, end)
        normalized_source = normalize_text(source_text)
        hook = normalize_text(str(candidate["hook_text"]))
        if hook and hook not in normalized_source:
            rejected.append(f"{start}–{end}: hook is not verbatim in the selected transcript")
            continue
        missing_phrases = [
            phrase for phrase in constraints.required_phrases
            if normalize_text(phrase) not in normalized_source
        ]
        if missing_phrases:
            rejected.append(f"{start}–{end}: missing required phrase(s): {', '.join(missing_phrases)}")
            continue

        candidate["hashtags"] = merge_required_hashtags(
            list(candidate.get("hashtags") or []), constraints.required_hashtags
        )
        candidate["source_text"] = source_text
        seen_windows.add(window_key)
        accepted.append(candidate)

    accepted.sort(key=lambda item: int(item["virality_score"]), reverse=True)
    if not accepted:
        detail = rejected[0] if rejected else "Gemini proposed no compliant moments"
        raise ClipFarmError(
            "selection",
            f"no candidates passed validation ({detail})",
            "Check that the source actually contains the required messaging and allowed 15–45s moments.",
        )
    return accepted
