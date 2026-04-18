"""Regression / replay test: would the schema have caught pilot_s3?

pilot_s3 was a canonical failure case:
- brief ev_bps = 1.538
- entry = MARKET BUY (crosses ~4.75 bps half-spread on 034020)
- brief horizon 3000 ticks, actual hold ~14 ticks (42s) — horizon_scale ~0.005
- 034020 in -6.6% downtrend during backtest window

Under the schema, either (a) the pilot_s3-style alpha JSON must be authored with
a brief_realism block whose adjusted_ev is correctly negative AND decision='reject',
or (b) the authorship fails validation. This test demonstrates (b) directly.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pilot_s3_idea_json_without_realism_block_fails_validation():
    """If we submit the existing (schema-less) pilot_s3 idea.json as alpha-designer
    output, the new validator should reject it for missing brief_realism."""
    existing = json.loads(
        (REPO_ROOT
         / "strategies/strat_20260417_0005_pilot_s3_034020_spread/idea.json").read_text()
    )
    # Build a minimal alpha-designer-shaped wrapper around existing content
    wrapper = {
        "strategy_id": "strat_20260417_0005_pilot_s3_034020_spread",
        "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer",
        "model_version": "claude-sonnet-4-6",
        "draft_md_path": "strategies/_drafts/pilot_s3_034020_spread_alpha.md",
        "name": existing.get("name", "pilot_s3"),
        "hypothesis": existing.get("hypothesis", ""),
        "entry_condition": existing.get("entry_condition", ""),
        "market_context": existing.get("market_context", ""),
        "signals_needed": existing.get("signals_needed", []),
        "missing_primitive": existing.get("missing_primitive"),
        "needs_python": existing.get("needs_python", False),
        "paradigm": existing.get("paradigm", "mean_reversion"),
        "multi_date": existing.get("multi_date", True),
        "parent_lesson": existing.get("parent_lesson"),
        "signal_brief_rank": existing.get("signal_brief_rank", 1),
        "universe_rationale": existing.get("universe_rationale", ""),
        "escape_route": existing.get("escape_route"),
        # brief_realism is MISSING — the point of this test
    }
    result = subprocess.run(
        [sys.executable, "scripts/verify_outputs.py",
         "--agent", "alpha-designer", "--output", json.dumps(wrapper)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert any("brief_realism" in f for f in out["failures"]), (
        f"Expected brief_realism failure; got: {out['failures']}"
    )


def test_pilot_s3_with_honest_realism_block_is_rejected_by_decision():
    """Even if we hand-fill a truthful brief_realism block for pilot_s3's actual
    conditions, it should fail the 'adjusted_ev < 0 but decision=proceed' rule."""
    realism = {
        "brief_ev_bps_raw": 1.538,
        "entry_order_type": "MARKET",
        "spread_cross_cost_bps": 4.75,  # half of 9.5 bps 1-tick spread on 034020
        "brief_horizon_ticks": 3000,
        "planned_holding_ticks_estimate": 14,  # ~42s / typical tick rate
        "horizon_scale_factor": 0.01,  # 14/3000 rounded
        "symbol_trend_pct_during_target_window": -6.6,
        "regime_compatibility": "mismatch",
        "regime_adjustment_bps": 0.0,
        "adjusted_ev_bps": 1.538 * 0.01 - 4.75 - 0.0,  # ≈ -4.73
        "decision": "proceed",  # contradicts negative adjusted_ev
        "rationale": "attempted to force proceed",
    }
    wrapper = {
        "strategy_id": None, "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer", "model_version": "v",
        "draft_md_path": "p.md",
        "name": "pilot_s3_replay", "hypothesis": "h", "entry_condition": "c",
        "market_context": "m", "signals_needed": ["spread_bps", "obi_5"],
        "missing_primitive": None, "needs_python": False,
        "paradigm": "mean_reversion", "multi_date": True,
        "parent_lesson": None, "signal_brief_rank": 1,
        "universe_rationale": "u", "escape_route": None,
        "brief_realism": realism,
    }
    result = subprocess.run(
        [sys.executable, "scripts/verify_outputs.py",
         "--agent", "alpha-designer", "--output", json.dumps(wrapper)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert any("decision='proceed'" in f for f in out["failures"]), (
        f"Expected decision-contradiction failure; got: {out['failures']}"
    )
