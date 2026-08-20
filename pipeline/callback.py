"""Optional signed status callback for the Supabase dashboard backend."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .io_utils import read_json


def notify_status(status_path: Path) -> None:
    """POST status when callback secrets exist; never block clip production."""
    url = os.environ.get("CLIPFARM_CALLBACK_URL", "").strip()
    secret = os.environ.get("CLIPFARM_CALLBACK_SECRET", "").strip()
    if not url and not secret:
        return
    if not url or not secret:
        print(
            "::warning title=ClipFarm callback disabled::Both callback URL and secret are required.",
            file=sys.stderr,
        )
        return
    if not status_path.exists():
        return

    status = read_json(status_path)
    github_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    github_server = os.environ.get("GITHUB_SERVER_URL", "").strip()
    github_repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if github_run_id:
        status["github_run_id"] = int(github_run_id)
    if github_run_id and github_server and github_repository:
        status["github_run_url"] = f"{github_server}/{github_repository}/actions/runs/{github_run_id}"

    payload = json.dumps(
        status,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-ClipFarm-Signature": f"sha256={signature}",
            "User-Agent": "ClipFarm-Actions/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"HTTP {response.status}")
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(
            f"::warning title=ClipFarm callback failed::{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
