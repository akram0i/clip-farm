"""
ClipFarm pipeline orchestrator.

Runs end-to-end: download episode -> transcribe -> pick viral moments (Gemini)
-> render vertical captioned clips -> (optionally) publish.

Triggered by GitHub Actions with inputs from a repository_dispatch event:
  campaign_brief : str  (the rules/requirements pasted from Whop)
  episode_url    : str  (source video/podcast URL)
  platforms      : list[str]  e.g. ["youtube", "instagram", "tiktok"]
"""

import json
import os
import sys
from pathlib import Path

from download import download_episode
from transcribe import transcribe_audio
from moment_picker import pick_viral_moments
from render import render_clip

WORKDIR = Path(os.environ.get("CLIPFARM_WORKDIR", "/tmp/clipfarm_job"))


def run(campaign_brief: str, episode_url: str, platforms: list[str]) -> list[dict]:
    WORKDIR.mkdir(parents=True, exist_ok=True)

    print("[1/4] Downloading episode...")
    video_path = download_episode(episode_url, WORKDIR)

    print("[2/4] Transcribing...")
    transcript = transcribe_audio(video_path, WORKDIR)

    print("[3/4] Picking viral moments with Gemini...")
    moments = pick_viral_moments(
        transcript=transcript,
        campaign_brief=campaign_brief,
    )

    print(f"  -> {len(moments)} candidate moments returned")

    print("[4/4] Rendering clips...")
    results = []
    for i, moment in enumerate(moments):
        clip_path = render_clip(
            source_video=video_path,
            start=moment["start_seconds"],
            end=moment["end_seconds"],
            captions=moment["caption_segments"],
            output_dir=WORKDIR / "clips",
            clip_index=i,
        )
        results.append({
            "clip_path": str(clip_path),
            "hook_text": moment["hook_text"],
            "score": moment["virality_score"],
            "hook_strength": moment["hook_strength"],
            "loop_potential": moment["loop_potential"],
            "reason": moment["reason"],
            "suggested_caption": moment["post_caption"],
            "suggested_hashtags": moment["hashtags"],
        })

    # Sort by score descending so the review queue shows best clips first
    results.sort(key=lambda r: r["score"], reverse=True)

    manifest_path = WORKDIR / "manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2))
    print(f"Done. {len(results)} clips rendered. Manifest: {manifest_path}")
    return results


if __name__ == "__main__":
    # When run from GitHub Actions, these come in as env vars set from the
    # repository_dispatch client_payload (see workflow file).
    brief = os.environ["CAMPAIGN_BRIEF"]
    url = os.environ["EPISODE_URL"]
    plats = os.environ.get("PLATFORMS", "youtube").split(",")

    output = run(brief, url, plats)
    print(json.dumps(output, indent=2))
