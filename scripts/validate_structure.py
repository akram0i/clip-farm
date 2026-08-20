#!/usr/bin/env python3
"""Fail loudly when ClipFarm's required repository structure is broken."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    ".github/workflows/process_campaign.yml",
    ".github/workflows/validate.yml",
    "dashboard/index.html",
    "dashboard/styles.css",
    "dashboard/app.js",
    "dashboard/logic.js",
    "dashboard/package.json",
    "dashboard/package-lock.json",
    "dashboard/vite.config.js",
    "dashboard/_headers",
    "dashboard/vercel.json",
    "supabase/functions/start-campaign/index.ts",
    "supabase/functions/run-callback/index.ts",
    "supabase/functions/download-results/index.ts",
    "supabase/migrations/20260820060219_authenticated_dashboard.sql",
    "supabase/migrations/20260820061309_harden_authenticated_dashboard.sql",
    "supabase/migrations/20260820064625_access_contract_version.sql",
    "pipeline/__init__.py",
    "pipeline/main.py",
    "pipeline/requirements.txt",
    "contracts/campaign-dispatch.schema.json",
    "contracts/run-status.schema.json",
    "contracts/manifest.schema.json",
    "contracts/earnings-access.schema.json",
    "contracts/earnings-submission.schema.json",
    "contracts/earnings-review.schema.json",
    "architecture/SUPABASE_BACKEND.md",
    "netlify.toml",
    "README.md",
)
FORBIDDEN_AT_ROOT = (
    "process_campaign.yml",
    "main.py",
    "download.py",
    "transcribe.py",
    "moment_picker.py",
    "render.py",
    "publish.py",
    "requirements.txt",
    "dashboard.html",
)
SECRET_PATTERNS = {
    "GitHub personal access token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "classic GitHub token": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "Google API key": re.compile(r"AIza[A-Za-z0-9_-]{30,}"),
    "Supabase secret key": re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
}
IGNORED_PARTS = {".git", ".netlify", ".vercel", "__pycache__", "dist", "node_modules"}


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    for relative in FORBIDDEN_AT_ROOT:
        if (ROOT / relative).exists():
            errors.append(f"misplaced root-level file: {relative}")

    workflow = ROOT / ".github/workflows/process_campaign.yml"
    if workflow.exists():
        content = workflow.read_text(encoding="utf-8")
        for command in ("prepare", "download", "transcribe", "select", "render"):
            if f"python -m pipeline.main {command}" not in content:
                errors.append(f"process workflow does not invoke the {command} stage")

    start_function = ROOT / "supabase/functions/start-campaign/index.ts"
    if start_function.exists() and "const runId = crypto.randomUUID()" not in start_function.read_text(encoding="utf-8"):
        errors.append("server-side campaign dispatch does not create the stable run UUID")

    for relative in ("dashboard/index.html", "dashboard/app.js"):
        path = ROOT / relative
        if path.exists() and ("Connect GitHub" in path.read_text(encoding="utf-8") or "api.github.com" in path.read_text(encoding="utf-8")):
            errors.append(f"member-facing GitHub configuration found in {relative}")

    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or any(part in IGNORED_PARTS for part in path.parts)
            or path.stat().st_size > 2_000_000
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible hardcoded {label}: {path.relative_to(ROOT)}")

    if errors:
        print("ClipFarm structure validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"ClipFarm structure is valid ({len(REQUIRED)} required files present; no token patterns found).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
