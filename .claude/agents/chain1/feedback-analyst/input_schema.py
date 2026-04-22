"""Input schema for feedback-analyst (stage ④)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import SignalSpec, BacktestResult, Feedback  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration_idx: int = Field(..., ge=0)
    spec: SignalSpec
    result: BacktestResult
    recent_feedback: list[Feedback] | None = None
