"""ExecutionHandoff — output of execution-designer, consumed by spec-writer."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from engine.schemas.alpha import AlphaHandoff
from engine.schemas.base import HandoffBase


class DeviationFromBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pt_pct: float
    sl_pct: float
    rationale: str

    @field_validator("pt_pct", "sl_pct")
    @classmethod
    def _within_band(cls, v: float) -> float:
        if abs(v) > 0.20:
            raise ValueError(
                f"Deviation |{v}| > 0.20 requires structural_concern escalation, not proceed"
            )
        return v


class EntryExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: Literal["bid", "bid_minus_1tick", "mid", "ask"]
    ttl_ticks: Optional[int] = Field(default=None, ge=1)
    cancel_on_bid_drop_ticks: Optional[int] = Field(default=None, ge=1)


class ExitExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profit_target_bps: float = Field(gt=0)
    stop_loss_bps: float = Field(gt=0)
    trailing_stop: bool
    trailing_activation_bps: Optional[float]
    trailing_distance_bps: Optional[float]

    @model_validator(mode="after")
    def _trailing_requires_params(self):
        if self.trailing_stop and (
            self.trailing_activation_bps is None or self.trailing_distance_bps is None
        ):
            raise ValueError(
                "trailing_stop=True requires both trailing_activation_bps and trailing_distance_bps"
            )
        return self


class PositionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_size: int = Field(ge=1)
    max_entries_per_session: int = Field(ge=1)


class ExecutionHandoff(HandoffBase):
    """Output of execution-designer. Nests AlphaHandoff for full carry-over."""

    agent_name: Literal["execution-designer"]
    alpha: AlphaHandoff
    entry_execution: EntryExecution
    exit_execution: ExitExecution
    position: PositionConfig
    deviation_from_brief: DeviationFromBrief
