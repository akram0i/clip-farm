"""Validated campaign input and per-run filesystem paths."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from .errors import ClipFarmError

SUPPORTED_PLATFORMS = {
    "tiktok",
    "instagram",
    "youtube",
    "x",
}


def _optional_money(value: Any, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ClipFarmError("input", f"{field_name} must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ClipFarmError("input", f"{field_name} cannot be negative")
    return parsed


@dataclass(frozen=True)
class Campaign:
    schema_version: int
    run_id: str
    campaign_name: str
    episode_url: str
    platforms: tuple[str, ...]
    requirements: str
    available_content: str = ""
    reward_rate: float | None = None
    minimum_payout: float | None = None
    maximum_payout: float | None = None
    requested_by: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Campaign":
        if not isinstance(raw, dict):
            raise ClipFarmError("input", "campaign payload must be a JSON object")

        name = str(raw.get("campaign_name", "")).strip()
        run_id = str(raw.get("run_id", "")).strip()
        url = str(raw.get("episode_url", "")).strip()
        requirements = str(raw.get("requirements", "")).strip()
        available_content = str(raw.get("available_content", "")).strip()
        requested_by = str(raw.get("requested_by", "")).strip()[:100]

        if not name:
            raise ClipFarmError("input", "campaign name is required")
        if len(name) > 160:
            raise ClipFarmError("input", "campaign name must be 160 characters or fewer")
        try:
            UUID(run_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ClipFarmError("input", "run_id must be a valid UUID") from exc

        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ClipFarmError("input", "episode URL must be a valid http(s) URL")
        if not requirements:
            raise ClipFarmError("input", "the Whop Requirements field is required")
        if len(requirements) > 30_000 or len(available_content) > 30_000:
            raise ClipFarmError(
                "input",
                "campaign text is too large",
                "Paste the relevant text rather than an entire document.",
            )

        platform_value = raw.get("platforms", [])
        if not isinstance(platform_value, list):
            raise ClipFarmError("input", "platforms must be a list")
        platforms = tuple(dict.fromkeys(str(item).lower().strip() for item in platform_value))
        unknown = sorted(set(platforms) - SUPPORTED_PLATFORMS)
        if unknown:
            raise ClipFarmError("input", f"unsupported platform(s): {', '.join(unknown)}")
        if not platforms:
            raise ClipFarmError("input", "select at least one eligible platform")

        reward = _optional_money(raw.get("reward_rate"), "reward rate")
        minimum = _optional_money(raw.get("minimum_payout"), "minimum payout")
        maximum = _optional_money(raw.get("maximum_payout"), "maximum payout")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ClipFarmError("input", "minimum payout cannot exceed maximum payout")

        return cls(
            schema_version=int(raw.get("schema_version", 1)),
            run_id=run_id,
            campaign_name=name,
            episode_url=url,
            platforms=platforms,
            requirements=requirements,
            available_content=available_content,
            reward_rate=reward,
            minimum_payout=minimum,
            maximum_payout=maximum,
            requested_by=requested_by,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["platforms"] = list(self.platforms)
        return value

    def ai_brief(self) -> str:
        sections = [
            f"Campaign name: {self.campaign_name}",
            f"Eligible platforms: {', '.join(self.platforms)}",
        ]
        if self.reward_rate is not None:
            sections.append(f"Reward: ${self.reward_rate:g} per 1,000 verified views")
        if self.minimum_payout is not None:
            sections.append(f"Minimum payout: ${self.minimum_payout:g}")
        if self.maximum_payout is not None:
            sections.append(f"Maximum payout: ${self.maximum_payout:g}")
        if self.available_content:
            sections.append(f"Available content / brand guidance:\n{self.available_content}")
        sections.append(f"Requirements — obey exactly:\n{self.requirements}")
        return "\n\n".join(sections)


@dataclass(frozen=True)
class JobPaths:
    root: Path

    @property
    def campaign(self) -> Path:
        return self.root / "campaign.json"

    @property
    def source_marker(self) -> Path:
        return self.root / "source_path.txt"

    @property
    def transcript(self) -> Path:
        return self.root / "transcript.json"

    @property
    def moments(self) -> Path:
        return self.root / "moments.json"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def clips(self) -> Path:
        return self.results / "clips"

    @property
    def manifest(self) -> Path:
        return self.results / "manifest.json"

    @property
    def error(self) -> Path:
        return self.results / "error.json"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)
