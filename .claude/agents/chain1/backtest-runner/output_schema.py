"""Output schema for backtest-runner (stage ③)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import BacktestResult  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402


class BacktestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: BacktestResult
