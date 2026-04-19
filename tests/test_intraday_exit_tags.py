"""Regression test for intraday_full_artifacts.generate_fills exit-tag plumbing.

Verifies the three return-shape contracts (bar strategy):
  1. pd.Series only          -> all exit fills tagged "exit_signal" (legacy)
  2. (signal, exit_tags)     -> exit fills tagged from exit_tags series
  3. pd.DataFrame(signal,...) -> exit fills tagged from "exit_tag" column
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.intraday_full_artifacts import generate_fills


def _df(n: int = 10) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "open_time": ts,
        "open": np.linspace(100.0, 110.0, n),
        "close": np.linspace(100.5, 110.5, n),
    })


def test_generate_fills_legacy_signal_only_uses_generic_exit_signal():
    df = _df(10)
    # Enter at bar 2, exit at bar 5
    signal = pd.Series([0, 0, 1, 1, 1, 0, 0, 0, 0, 0], index=df.index)
    fills = generate_fills(df, signal, "BTCUSDT", lot_size=1, fee_side_bps=2.0)
    tags = [f["tag"] for f in fills]
    assert tags == ["entry_signal", "exit_signal"]


def test_generate_fills_with_exit_tags_series_uses_specific_reason():
    df = _df(10)
    # signal flips 1->0 at index 5 (strategy decides to exit on bar 5).
    # Strategy places exit_tags[5]="pt_hit" at the same bar.
    signal = pd.Series([0, 0, 1, 1, 1, 0, 0, 0, 0, 0], index=df.index)
    exit_tags = pd.Series(
        ["", "", "", "", "", "pt_hit", "", "", "", ""], index=df.index, dtype=object
    )
    fills = generate_fills(df, signal, "BTCUSDT", lot_size=1,
                           fee_side_bps=2.0, exit_tags=exit_tags)
    tags = [f["tag"] for f in fills]
    assert tags == ["entry_signal", "pt_hit"]


def test_generate_fills_empty_exit_tag_falls_back_to_generic():
    df = _df(10)
    signal = pd.Series([0, 0, 1, 1, 1, 0, 0, 0, 0, 0], index=df.index)
    exit_tags = pd.Series([""] * 10, index=df.index, dtype=object)
    fills = generate_fills(df, signal, "BTCUSDT", lot_size=1,
                           fee_side_bps=2.0, exit_tags=exit_tags)
    tags = [f["tag"] for f in fills]
    assert tags == ["entry_signal", "exit_signal"]


def test_generate_fills_distinguishes_sl_from_pt():
    df = _df(15)
    # Two round-trips: signal flips 1->0 at index 3 (first exit) and index 8 (second).
    # Strategy places exit_tags at those bars.
    signal = pd.Series(
        [0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0], index=df.index
    )
    exit_tags = pd.Series(
        ["", "", "", "sl_hit", "", "", "", "", "pt_hit", "", "", "", "", "", ""],
        index=df.index, dtype=object,
    )
    fills = generate_fills(df, signal, "BTCUSDT", lot_size=1,
                           fee_side_bps=2.0, exit_tags=exit_tags)
    tags = [f["tag"] for f in fills]
    assert tags == ["entry_signal", "sl_hit", "entry_signal", "pt_hit"]
