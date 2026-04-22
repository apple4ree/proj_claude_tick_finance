"""Output schema for signal-evaluator (stage ②)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import SpecEvaluation  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402


class EvaluateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation: SpecEvaluation
