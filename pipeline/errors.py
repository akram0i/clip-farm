"""User-facing pipeline errors with stage-specific recovery guidance."""

from __future__ import annotations


class ClipFarmError(RuntimeError):
    """An expected failure that can be explained clearly in GitHub Actions."""

    def __init__(self, stage: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        suffix = f" Recovery: {self.hint}" if self.hint else ""
        return f"{self.stage}: {self.message}.{suffix}".replace("..", ".")
