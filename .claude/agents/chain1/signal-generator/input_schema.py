"""Input schema for signal-generator (stage ①)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import Feedback, ImprovementProposal  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class UniverseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(..., min_length=1)
    dates: list[str] = Field(..., min_length=1, description="YYYYMMDD strings")


class GenerateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration_idx: int = Field(..., ge=0)
    n_candidates: int = Field(..., ge=1, le=20)
    universe: UniverseSpec
    prior_feedback: list[Feedback] | None = None
    prior_improvement: ImprovementProposal | None = None
