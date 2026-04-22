"""Input schema for signal-improver (stage ⑤)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import SignalSpec, BacktestResult, Feedback  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class FeedbackTriple(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: SignalSpec
    result: BacktestResult
    feedback: Feedback


class ImproveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration_idx: int = Field(..., ge=0)
    triples: list[FeedbackTriple] = Field(..., min_length=1)
    next_iteration_budget: int = Field(..., ge=1, le=20)
