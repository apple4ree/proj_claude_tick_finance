"""Unit tests for engine.schemas.alpha."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError


def _valid_realism(**overrides):
    """Build a valid BriefRealismCheck dict; overrides replace fields."""
    base = dict(
        brief_ev_bps_raw=1.5,
        entry_order_type="MARKET",
        spread_cross_cost_bps=5.0,
        brief_horizon_ticks=3000,
        planned_holding_ticks_estimate=3000,
        horizon_scale_factor=1.0,
        symbol_trend_pct_during_target_window=0.5,
        regime_compatibility="match",
        regime_adjustment_bps=0.0,
        adjusted_ev_bps=-3.5,  # 1.5 * 1.0 - 5.0 - 0.0
        decision="reject",
        rationale="entry cost exceeds raw EV",
    )
    base.update(overrides)
    return base


def _valid_alpha(**overrides):
    base = dict(
        strategy_id=None,
        timestamp=datetime(2026, 4, 17),
        agent_name="alpha-designer",
        model_version="claude-sonnet-4-6",
        draft_md_path="strategies/_drafts/foo_alpha.md",
        name="foo",
        hypothesis="h",
        entry_condition="c",
        market_context="m",
        signals_needed=["obi_5"],
        missing_primitive=None,
        needs_python=False,
        paradigm="mean_reversion",
        multi_date=True,
        parent_lesson=None,
        signal_brief_rank=1,
        universe_rationale="u",
        escape_route=None,
        brief_realism=_valid_realism(),
    )
    base.update(overrides)
    return base


def test_alpha_handoff_accepts_valid():
    from engine.schemas.alpha import AlphaHandoff
    AlphaHandoff(**_valid_alpha())


def test_brief_realism_rejects_inconsistent_adjusted_ev():
    """adjusted_ev must equal raw * scale - spread_cross - regime within 0.5 bps."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError, match="inconsistent with components"):
        BriefRealismCheck(**_valid_realism(adjusted_ev_bps=100.0))  # wildly wrong


def test_brief_realism_rejects_negative_ev_with_proceed():
    """adjusted_ev_bps < 0 and decision='proceed' is contradictory."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError, match="decision='proceed'"):
        BriefRealismCheck(**_valid_realism(decision="proceed"))


def test_brief_realism_horizon_scale_upper_bound():
    """horizon_scale_factor > 2.0 must fail."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError):
        BriefRealismCheck(**_valid_realism(horizon_scale_factor=3.0))


def test_brief_realism_horizon_scale_must_be_positive():
    """horizon_scale_factor <= 0 must fail."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError):
        BriefRealismCheck(**_valid_realism(horizon_scale_factor=0.0))


def test_alpha_handoff_rank_out_of_range():
    from engine.schemas.alpha import AlphaHandoff
    with pytest.raises(ValidationError):
        AlphaHandoff(**_valid_alpha(signal_brief_rank=11))
    with pytest.raises(ValidationError):
        AlphaHandoff(**_valid_alpha(signal_brief_rank=0))


def test_alpha_handoff_spread_cross_can_be_negative_for_limit_bid():
    """LIMIT_AT_BID fills are inside mid — spread_cross_cost can be negative."""
    from engine.schemas.alpha import AlphaHandoff
    realism = _valid_realism(
        entry_order_type="LIMIT_AT_BID",
        spread_cross_cost_bps=-2.0,
        adjusted_ev_bps=3.5,  # 1.5 * 1.0 - (-2.0) - 0.0
        decision="proceed",
        rationale="passive maker captures spread",
    )
    AlphaHandoff(**_valid_alpha(brief_realism=realism))
