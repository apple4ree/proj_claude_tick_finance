"""Integration test for scripts/verify_outputs.py pydantic extensions."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_verify(agent: str, output_json: dict) -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/verify_outputs.py",
         "--agent", agent, "--output", json.dumps(output_json)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return json.loads(result.stdout)


def test_alpha_designer_rejects_missing_brief_realism():
    malformed = {
        "strategy_id": None,
        "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer",
        "model_version": "v1",
        "draft_md_path": "p.md",
        "name": "x", "hypothesis": "h", "entry_condition": "c",
        "market_context": "m", "signals_needed": ["obi_5"],
        "missing_primitive": None, "needs_python": False,
        "paradigm": "mean_reversion", "multi_date": True,
        "parent_lesson": None, "signal_brief_rank": 1,
        "universe_rationale": "u", "escape_route": None,
        # brief_realism intentionally omitted
    }
    out = _run_verify("alpha-designer", malformed)
    assert out["ok"] is False
    assert any("brief_realism" in f for f in out["failures"])


def test_execution_designer_rejects_out_of_band_deviation():
    # Use a minimal valid alpha but bad deviation
    valid_realism = dict(
        brief_ev_bps_raw=1.5, entry_order_type="MARKET",
        spread_cross_cost_bps=5.0, brief_horizon_ticks=3000,
        planned_holding_ticks_estimate=3000, horizon_scale_factor=1.0,
        symbol_trend_pct_during_target_window=0.5,
        regime_compatibility="match", regime_adjustment_bps=0.0,
        adjusted_ev_bps=-3.5, decision="reject",
        rationale="cost dominates",
    )
    valid_alpha = {
        "strategy_id": None, "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer", "model_version": "v1",
        "draft_md_path": "p.md",
        "name": "x", "hypothesis": "h", "entry_condition": "c",
        "market_context": "m", "signals_needed": ["obi_5"],
        "missing_primitive": None, "needs_python": False,
        "paradigm": "mean_reversion", "multi_date": True,
        "parent_lesson": None, "signal_brief_rank": 1,
        "universe_rationale": "u", "escape_route": None,
        "brief_realism": valid_realism,
    }
    out_json = {
        "strategy_id": None, "timestamp": "2026-04-17T00:00:00",
        "agent_name": "execution-designer", "model_version": "v1",
        "draft_md_path": "e.md",
        "alpha": valid_alpha,
        "entry_execution": {"price": "ask", "ttl_ticks": None,
                            "cancel_on_bid_drop_ticks": None},
        "exit_execution": {"profit_target_bps": 30.0, "stop_loss_bps": 15.0,
                           "trailing_stop": False,
                           "trailing_activation_bps": None,
                           "trailing_distance_bps": None},
        "position": {"lot_size": 1, "max_entries_per_session": 3},
        "deviation_from_brief": {"pt_pct": 0.30, "sl_pct": 0.0,  # out of band
                                 "rationale": "bad"},
    }
    out = _run_verify("execution-designer", out_json)
    assert out["ok"] is False
    assert any("Deviation" in f for f in out["failures"])


def test_feedback_analyst_rejects_missing_priority():
    fb = {
        "strategy_id": "sid", "timestamp": "2026-04-17T00:00:00",
        "agent_name": "feedback-analyst", "model_version": "v1",
        "draft_md_path": "p.md",
        "lesson_id": None, "pattern_id": None,
        "primary_finding": "f",
        "agreement_points": [], "disagreement_points": [],
        # priority_action missing
        "next_idea_seed": "s", "local_seed": "l", "escape_seed": "e",
        "stop_suggested": False, "structural_concern": None,
        "data_requests": [], "extensions": {},
    }
    out = _run_verify("feedback-analyst", fb)
    assert out["ok"] is False
    assert any("priority_action" in f for f in out["failures"])
