"""Input schema for backtest-runner (stage ③)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import SignalSpec, GeneratedCode  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class UniverseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(..., min_length=1)
    dates: list[str] = Field(..., min_length=1)


class BacktestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration_idx: int = Field(..., ge=0)
    spec: SignalSpec
    code: GeneratedCode
    universe: UniverseSpec
    save_trace: bool = Field(False)
    trace_path: str | None = None
