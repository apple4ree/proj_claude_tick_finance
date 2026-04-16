"""Unit tests for scripts/generate_signal_brief.py output schema."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_brief_schema_has_required_fields():
    """The brief JSON must contain the fields agents rely on."""
    # Use existing cached BTC feature data as input
    features_csv = REPO_ROOT / "data/signal_research/crypto/BTC_features.csv"
    if not features_csv.exists():
        pytest.skip("BTC feature data not available")

    out_dir = REPO_ROOT / "data/signal_briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "BTC.json"
    if out_path.exists():
        out_path.unlink()

    result = subprocess.run(
        [
            sys.executable, "scripts/generate_signal_brief.py",
            "--symbol", "BTC",
            "--features-dir", "data/signal_research/crypto",
            "--fee", "4.0",
            "--out-dir", "data/signal_briefs",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"generator failed: {result.stderr}"
    assert out_path.exists(), "brief JSON not written"

    brief = json.loads(out_path.read_text())
    # Required top-level keys
    assert "symbol" in brief
    assert "fee_bps" in brief
    assert "top_signals" in brief
    assert "recommendation" in brief
    assert brief["symbol"] == "BTC"
    assert brief["fee_bps"] == 4.0
    assert isinstance(brief["top_signals"], list)


def test_brief_top_signals_have_required_fields():
    """Each signal entry must include the fields alpha-designer needs."""
    out_path = REPO_ROOT / "data/signal_briefs/BTC.json"
    if not out_path.exists():
        pytest.skip("brief not generated; run test_brief_schema_has_required_fields first")

    brief = json.loads(out_path.read_text())
    signals = brief["top_signals"]
    assert len(signals) >= 1, "brief must have at least 1 signal"

    for sig in signals:
        assert "rank" in sig
        assert "signal" in sig
        assert "threshold" in sig
        assert "horizon" in sig
        assert "ev_bps" in sig or "q5_mean_bps" in sig
        assert "optimal_exit" in sig
        oe = sig["optimal_exit"]
        assert "pt_bps" in oe
        assert "sl_bps" in oe
        assert "sharpe" in oe
        assert "win_rate_pct" in oe


def test_brief_handles_no_viable_signals():
    """For KRX 005930 (known no-viable market), brief should mark all non-viable."""
    features_csv = REPO_ROOT / "data/signal_research/005930_features.csv"
    if not features_csv.exists():
        pytest.skip("005930 feature data not available")

    out_path = REPO_ROOT / "data/signal_briefs/005930.json"
    if out_path.exists():
        out_path.unlink()

    result = subprocess.run(
        [
            sys.executable, "scripts/generate_signal_brief.py",
            "--symbol", "005930",
            "--features-dir", "data/signal_research",
            "--fee", "21.0",
            "--out-dir", "data/signal_briefs",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0
    brief = json.loads(out_path.read_text())
    # All signals should be flagged non-viable
    viable = [s for s in brief["top_signals"] if s.get("viable")]
    assert len(viable) == 0, (
        f"Expected 0 viable signals on KRX 005930 at 21 bps fee; got {len(viable)}"
    )
    assert "no viable" in brief["recommendation"].lower()
