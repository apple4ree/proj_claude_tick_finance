"""Input schema for chain2-gate (stage 6_promotion_gate)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import SignalSpec, BacktestResult, Feedback  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class GateTriple(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: SignalSpec
    result: BacktestResult
    feedback: Feedback


class GateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iterations_scanned: list[int] = Field(..., min_length=1)
    triples: list[GateTriple] = Field(default_factory=list)
    fee_scenarios: list[str] = Field(..., min_length=1,
                                      description="IDs from fee_scenarios.md (e.g. 'krx_cash_23bps')")
    top_k: int = Field(3, ge=1, le=20)
    n_symbols: int = Field(..., ge=1, description="How many symbols the backtests covered")
    n_dates: int = Field(..., ge=1, description="How many distinct dates the backtests covered")
    use_llm_narrative: bool = Field(False, description="If True and live API, produce rationale_kr")
