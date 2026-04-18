"""Unit tests for engine.schemas.execution."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from tests.test_handoff_alpha import _valid_alpha


def _valid_exec(**overrides):
    base = dict(
        strategy_id=None,
        timestamp=datetime(2026, 4, 17),
        agent_name="execution-designer",
        model_version="claude-sonnet-4-6",
        draft_md_path="strategies/_drafts/foo_exec.md",
        alpha=_valid_alpha(),
        entry_execution=dict(
            price="ask",
            ttl_ticks=None,
            cancel_on_bid_drop_ticks=None,
        ),
        exit_execution=dict(
            profit_target_bps=30.0,
            stop_loss_bps=15.0,
            trailing_stop=False,
            trailing_activation_bps=None,
            trailing_distance_bps=None,
        ),
        position=dict(lot_size=1, max_entries_per_session=3),
        deviation_from_brief=dict(
            pt_pct=0.10, sl_pct=-0.05, rationale="within band"
        ),
    )
    base.update(overrides)
    return base


def test_execution_handoff_accepts_valid():
    from engine.schemas.execution import ExecutionHandoff
    ExecutionHandoff(**_valid_exec())


def test_deviation_from_brief_rejects_out_of_band():
    from engine.schemas.execution import DeviationFromBrief
    with pytest.raises(ValidationError, match="Deviation"):
        DeviationFromBrief(pt_pct=0.30, sl_pct=0.0, rationale="too wide")


def test_exit_execution_rejects_non_positive_pt():
    from engine.schemas.execution import ExecutionHandoff
    bad = _valid_exec()
    bad["exit_execution"]["profit_target_bps"] = 0.0
    with pytest.raises(ValidationError):
        ExecutionHandoff(**bad)


def test_position_rejects_zero_lot():
    from engine.schemas.execution import ExecutionHandoff
    bad = _valid_exec()
    bad["position"]["lot_size"] = 0
    with pytest.raises(ValidationError):
        ExecutionHandoff(**bad)


def test_execution_carries_alpha_nested():
    from engine.schemas.execution import ExecutionHandoff
    h = ExecutionHandoff(**_valid_exec())
    assert h.alpha.signal_brief_rank == 1
    assert h.alpha.brief_realism.decision == "reject"
