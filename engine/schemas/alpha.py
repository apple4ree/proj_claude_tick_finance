"""AlphaHandoff + BriefRealismCheck — the contract alpha-designer returns."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.schemas.base import HandoffBase


class BriefRealismCheck(BaseModel):
    """Reconcile brief's measurement assumptions with this strategy's execution reality.

    This field is the primary defense against 'cited brief EV but did not adjust for
    actual execution conditions' — the root cause of pilot_s3-class failures.
    """

    model_config = ConfigDict(extra="forbid")

    brief_ev_bps_raw: float

    entry_order_type: Literal["MARKET", "LIMIT_AT_BID", "LIMIT_AT_ASK", "LIMIT_MID"]
    spread_cross_cost_bps: float = Field(
        description=(
            "Signed cost vs mid at entry, in bps. MARKET BUY = +half_spread (positive cost). "
            "LIMIT at bid, if fills, is a negative cost (fill is inside mid) — but adjust "
            "for adverse-selection expectation. Sign convention: positive = cost subtracted from raw EV."
        )
    )

    brief_horizon_ticks: int
    planned_holding_ticks_estimate: int
    horizon_scale_factor: float = Field(
        gt=0, le=2.0,
        description="planned / brief. Outside (0, 2.0] — EV extrapolation unreliable."
    )

    symbol_trend_pct_during_target_window: Optional[float]
    regime_compatibility: Literal["match", "partial", "mismatch", "unknown"]
    regime_adjustment_bps: float = Field(
        description="Subtractive. Downtrend vs mean-reversion premise = large positive (adverse)."
    )

    adjusted_ev_bps: float
    decision: Literal["proceed", "proceed_with_caveat", "reject"]
    rationale: str

    @model_validator(mode="after")
    def _validate_consistency(self):
        expected = (
            self.brief_ev_bps_raw * self.horizon_scale_factor
            - self.spread_cross_cost_bps
            - self.regime_adjustment_bps
        )
        tolerance = max(0.5, 0.05 * abs(expected))
        if abs(self.adjusted_ev_bps - expected) > tolerance:
            raise ValueError(
                f"adjusted_ev_bps ({self.adjusted_ev_bps}) inconsistent with components "
                f"(expected ≈ {expected:.2f}, tolerance {tolerance:.2f})"
            )
        if self.adjusted_ev_bps <= 0 and self.decision == "proceed":
            raise ValueError(
                "adjusted_ev_bps < 0 but decision='proceed' — inconsistent; "
                "use 'reject' or 'proceed_with_caveat'"
            )
        # Regime consistency: 'match' cannot coexist with large adjustment; 'mismatch' requires adverse adjustment
        if self.regime_compatibility == "match" and abs(self.regime_adjustment_bps) > 2.0:
            raise ValueError(
                f"regime_compatibility='match' but |regime_adjustment_bps|={abs(self.regime_adjustment_bps):.2f} > 2.0 — inconsistent"
            )
        if self.regime_compatibility == "mismatch" and self.regime_adjustment_bps <= 0.0:
            raise ValueError(
                "regime_compatibility='mismatch' requires positive (adverse) regime_adjustment_bps"
            )
        return self


class AlphaHandoff(HandoffBase):
    """Output of alpha-designer — consumed by execution-designer."""

    agent_name: Literal["alpha-designer"]

    name: str
    hypothesis: str
    entry_condition: str
    market_context: str
    signals_needed: list[str]
    missing_primitive: Optional[str]
    needs_python: bool
    paradigm: Optional[Literal[
        "mean_reversion", "trend_follow", "passive_maker", "fee_escape",
        "market_making",     # 2026-04-19 X4: passive two-sided quoting on LOB (ping-pong)
        "spread_capture",    # 2026-04-19 X4: single-side passive fill harvesting half-spread
    ]]
    multi_date: bool
    parent_lesson: Optional[str]

    signal_brief_rank: int = Field(ge=1, le=10)
    universe_rationale: str
    escape_route: Optional[str]

    brief_realism: BriefRealismCheck
