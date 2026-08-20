"""Command-line orchestration used by GitHub Actions and local smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from .callback import notify_status
from .captions import caption_events_for_window
from .config import Campaign, JobPaths
from .constraints import derive_constraints
from .download import download_episode
from .errors import ClipFarmError
from .io_utils import read_json, update_status, utc_now, write_json
from .moment_picker import pick_moments
from .render import render_clip
from .transcribe import transcribe_episode


def _load_campaign(paths: JobPaths) -> Campaign:
    if not paths.campaign.exists():
        raise ClipFarmError("input", "campaign.json is missing; the Prepare job step did not finish")
    return Campaign.from_dict(read_json(paths.campaign))


def prepare(paths: JobPaths) -> None:
    raw = os.environ.get("CLIPFARM_CAMPAIGN_JSON", "")
    if not raw:
        raise ClipFarmError("input", "CLIPFARM_CAMPAIGN_JSON is empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClipFarmError("input", f"campaign JSON is invalid at character {exc.pos}") from exc
    campaign = Campaign.from_dict(payload)
    paths.ensure()
    write_json(paths.campaign, campaign.to_dict())
    update_status(paths.results, "queued", "running", "Campaign accepted; download is next.")
    status = read_json(paths.results / "status.json")
    status["schema_version"] = 1
    status["run_id"] = campaign.run_id
    write_json(paths.results / "status.json", status)
    print(f"Campaign accepted: {campaign.campaign_name}")


def download(paths: JobPaths) -> None:
    campaign = _load_campaign(paths)
    update_status(paths.results, "downloading", "running", "Downloading the source episode.")
    source = download_episode(campaign.episode_url, paths.root)
    paths.source_marker.write_text(str(source), encoding="utf-8")
    update_status(paths.results, "downloading", "complete", "Source episode downloaded.")
    print(f"Downloaded source: {source.name} ({source.stat().st_size / 1_000_000:.1f} MB)")


def transcribe(paths: JobPaths) -> None:
    _load_campaign(paths)
    if not paths.source_marker.exists():
        raise ClipFarmError("transcription", "source path marker is missing")
    source = Path(paths.source_marker.read_text(encoding="utf-8").strip())
    if not source.exists():
        raise ClipFarmError("transcription", "downloaded source file is missing")
    update_status(paths.results, "transcribing", "running", "Transcribing locally with Whisper.")
    payload = transcribe_episode(source, paths.transcript)
    update_status(paths.results, "transcribing", "complete", "Transcript created.")
    print(
        f"Transcript: {len(payload['segments'])} segments, "
        f"{payload['duration_seconds'] / 60:.1f} minutes, language={payload.get('language')}"
    )


def select(paths: JobPaths) -> None:
    campaign = _load_campaign(paths)
    if not paths.transcript.exists():
        raise ClipFarmError("selection", "transcript.json is missing")
    transcript_payload = read_json(paths.transcript)
    constraints = derive_constraints(campaign.requirements, campaign.available_content)
    update_status(paths.results, "selecting", "running", "Gemini is scoring compliant moments.")
    moments = pick_moments(transcript_payload, campaign, constraints)
    write_json(paths.moments, {"constraints": constraints.to_dict(), "moments": moments})
    update_status(
        paths.results,
        "selecting",
        "complete",
        f"Selected {len(moments)} compliant moment(s).",
    )
    print(f"Selected {len(moments)} validated candidate(s).")


def render(paths: JobPaths) -> None:
    campaign = _load_campaign(paths)
    if not paths.source_marker.exists() or not paths.transcript.exists() or not paths.moments.exists():
        raise ClipFarmError("render", "a download, transcript, or moments file is missing")
    source = Path(paths.source_marker.read_text(encoding="utf-8").strip())
    transcript_payload = read_json(paths.transcript)
    selection_payload = read_json(paths.moments)
    moments = selection_payload["moments"]
    segments = transcript_payload["segments"]
    update_status(paths.results, "rendering", "running", f"Rendering {len(moments)} clip(s).")

    clips: list[dict[str, Any]] = []
    for index, moment in enumerate(moments, start=1):
        start = float(moment["start_seconds"])
        end = float(moment["end_seconds"])
        captions = caption_events_for_window(segments, start, end)
        if not captions:
            raise ClipFarmError("render", f"candidate {index} has no caption events")
        output = render_clip(source, start, end, captions, paths.clips, index)
        subtitle_file = output.with_suffix(".ass")
        if subtitle_file.exists():
            subtitle_file.unlink()
        clips.append({
            "rank": index,
            "file": f"clips/{output.name}",
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "duration_seconds": round(end - start, 3),
            "hook_text": moment["hook_text"],
            "virality_score": int(moment["virality_score"]),
            "hook_strength": int(moment["hook_strength"]),
            "loop_potential": int(moment["loop_potential"]),
            "selection_reason": moment["reason"],
            "source_transcript": moment["source_text"],
            "suggested_caption": moment["post_caption"],
            "suggested_hashtags": moment["hashtags"],
            "compliance": {
                "ai_marked_compliant": bool(moment["campaign_compliant"]),
                "evidence": moment["compliance_evidence"],
            },
        })

    manifest = {
        "schema_version": 1,
        "run_id": campaign.run_id,
        "status": "ready",
        "generated_at": utc_now(),
        "campaign": {
            "run_id": campaign.run_id,
            "name": campaign.campaign_name,
            "platforms": list(campaign.platforms),
            "requested_by": campaign.requested_by,
        },
        "constraints": selection_payload["constraints"],
        "clip_count": len(clips),
        "clips": clips,
    }
    write_json(paths.manifest, manifest)
    update_status(paths.results, "ready", "complete", f"{len(clips)} clip(s) are ready to download.")
    print(f"Ready: {len(clips)} rendered clip(s) and manifest.json")


def summarize(paths: JobPaths) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    lines = ["# ClipFarm run\n"]
    if paths.manifest.exists():
        manifest = read_json(paths.manifest)
        lines.extend([
            f"**{manifest['campaign']['name']}** produced **{manifest['clip_count']} clips**.\n",
            "| Rank | File | Overall | Hook | Loop | Duration |",
            "|---:|---|---:|---:|---:|---:|",
        ])
        for clip in manifest["clips"]:
            lines.append(
                f"| {clip['rank']} | `{Path(clip['file']).name}` | {clip['virality_score']} | "
                f"{clip['hook_strength']} | {clip['loop_potential']} | {clip['duration_seconds']:.1f}s |"
            )
        lines.append("\nDownload the **clipfarm-results** artifact from this run. Posting remains manual by design.\n")
    elif paths.error.exists():
        error = read_json(paths.error)
        lines.extend([
            f"**Failed during {error.get('stage', 'pipeline')}.**\n",
            f"> {error.get('message', 'Unknown error')}\n",
        ])
        if error.get("hint"):
            lines.append(f"**Recovery:** {error['hint']}\n")
    else:
        status = read_json(paths.results / "status.json") if (paths.results / "status.json").exists() else {}
        lines.append(f"Run stopped before completion. Last stage: **{status.get('stage', 'unknown')}**.\n")

    rendered = "\n".join(lines) + "\n"
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered)


COMMANDS: dict[str, Callable[[JobPaths], None]] = {
    "prepare": prepare,
    "download": download,
    "transcribe": transcribe,
    "select": select,
    "render": render,
    "summarize": summarize,
}


def _record_failure(paths: JobPaths, error: ClipFarmError) -> None:
    paths.ensure()
    payload = {
        "run_id": _failure_run_id(paths),
        "stage": error.stage,
        "message": error.message,
        "hint": error.hint,
        "failed_at": utc_now(),
    }
    write_json(paths.error, payload)
    status_stage = {
        "input": "queued",
        "download": "downloading",
        "transcription": "transcribing",
        "selection": "selecting",
        "render": "rendering",
    }.get(error.stage, "failed")
    update_status(paths.results, status_stage, "failed", error.message)
    annotation = f"{error.message} Recovery: {error.hint}" if error.hint else error.message
    print(f"::error title=ClipFarm {error.stage} failed::{annotation}", file=sys.stderr)


def _failure_run_id(paths: JobPaths) -> str | None:
    try:
        return str(read_json(paths.campaign).get("run_id")) if paths.campaign.exists() else None
    except Exception:
        return None


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one ClipFarm pipeline stage.")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path(os.environ.get("CLIPFARM_WORKDIR", "/tmp/clipfarm-job")),
    )
    args = parser.parse_args(argv)
    paths = JobPaths(args.workdir.resolve())
    paths.ensure()
    try:
        COMMANDS[args.command](paths)
        if args.command != "summarize":
            notify_status(paths.results / "status.json")
        return 0
    except ClipFarmError as error:
        _record_failure(paths, error)
        notify_status(paths.results / "status.json")
        return 1
    except Exception as exc:  # unexpected bugs still produce a downloadable diagnostic
        traceback.print_exc()
        error = ClipFarmError(
            args.command,
            f"unexpected {type(exc).__name__}: {exc}",
            "Open an issue with the failing Actions step and traceback.",
        )
        _record_failure(paths, error)
        notify_status(paths.results / "status.json")
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
