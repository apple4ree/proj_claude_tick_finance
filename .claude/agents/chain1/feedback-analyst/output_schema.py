"""Output schema for feedback-analyst (stage ④)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import Feedback  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402


class FeedbackOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback: Feedback
