"""Output schema for signal-improver (stage ⑤)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import ImprovementProposal  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class ImproveOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposals: list[ImprovementProposal] = Field(..., min_length=1)
