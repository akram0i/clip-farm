"""
Sends the transcript + campaign brief to Gemini (free tier) and asks it to
return the strongest clip candidates, structured around the retention
framework that actually predicts distribution:

  Hook (0-2s)    -> contradiction / tension / surprise, stated immediately
  Context (2-7s) -> who this is for, what's at stake
  Payoff         -> the actual value/reveal
  Loop           -> an ending that flows back into the hook (for rewatches)

Also scores each candidate on hook_strength and loop_potential specifically,
since those are the two factors research ties most directly to distribution,
so the human review pass can sort by what actually matters.
"""

import json
import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "gemini-2.5-flash"  # free tier, ~1500 requests/day

SYSTEM_PROMPT = """You are a short-form video producer selecting the highest-
potential clips from a podcast transcript for TikTok/Reels/Shorts.

For EACH clip you propose, structure it around this framework:
- Hook (first 0-2 seconds of the clip): must open on a contradiction,
  tension, surprising claim, or bold statement -- never ease in.
- Context (roughly 2-7s in): one sentence establishing who this is for and
  what's at stake.
- Payoff: the actual insight, reveal, or punchline.
- Loop: prefer clips whose natural end can flow back into the opening line
  or restates the hook's question, so a viewer rewatches without realizing.

Hard constraints:
- Target clip length: 20-35 seconds. Reject candidates that need to be
  under 15s (too little hook depth) or over 45s (retention drop-off).
- The clip MUST use only the source material provided (no fabricated text).
- Follow the campaign brief's rules exactly: required hashtags, banned
  edit styles, minimum/maximum length, topic restrictions, etc.

Return STRICT JSON ONLY (no markdown, no prose) as a list of objects:
[
  {
    "start_seconds": float,
    "end_seconds": float,
    "hook_text": "the literal opening line, verbatim from transcript",
    "caption_segments": [{"start": float, "end": float, "text": "..."}],
    "virality_score": int (0-100, overall),
    "hook_strength": int (0-100, specifically how strong the first 2s grab is),
    "loop_potential": int (0-100, how well the ending flows back to the hook),
    "reason": "one sentence on why this moment was chosen",
    "post_caption": "a short native caption for the post itself",
    "hashtags": ["#..."]
  }
]
"""


def pick_viral_moments(transcript: list[dict], campaign_brief: str) -> list[dict]:
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT,
    )

    transcript_text = "\n".join(
        f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}" for seg in transcript
    )

    user_prompt = f"""CAMPAIGN BRIEF / RULES:
{campaign_brief}

FULL TRANSCRIPT (timestamps in seconds):
{transcript_text}

Return the top 5-15 clip candidates as JSON per the schema described."""

    response = model.generate_content(user_prompt)

    raw = response.text.strip()
    # Strip accidental markdown fences if the model adds them anyway
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw

    return json.loads(raw)
