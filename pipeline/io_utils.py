"""Small, dependency-free JSON and status helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_status(results_dir: Path, stage: str, state: str, message: str) -> None:
    status_path = results_dir / "status.json"
    status = read_json(status_path) if status_path.exists() else {}
    status.update({
        "stage": stage,
        "state": state,
        "message": message,
        "updated_at": utc_now(),
    })
    write_json(status_path, status)
