"""Smoke test for engine.data_loader.iter_events_crypto_lob.

Verifies that the adapter can read parquet files produced by
scripts/binance_lob_collector.py and yield `OrderBookSnapshot` objects
with the integer-scaled fields the engine expects.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.data_loader import (
    CRYPTO_LOB_ROOT,
    CRYPTO_PRICE_SCALE,
    OrderBookSnapshot,
    iter_events_crypto_lob,
)


def _lob_archive_has_data() -> bool:
    if not CRYPTO_LOB_ROOT.exists():
        return False
    for p in CRYPTO_LOB_ROOT.rglob("*.parquet"):
        return True
    return False


@pytest.mark.skipif(not _lob_archive_has_data(),
                    reason="no parquet yet under data/binance_lob — collector not started or still warming up")
def test_iter_events_yields_snapshots_in_ts_order():
    # Wide window spanning all available data
    start_ns = 0
    end_ns = time.time_ns() + 10**12
    snaps = list(iter_events_crypto_lob(start_ns, end_ns, ["BTCUSDT", "ETHUSDT", "SOLUSDT"]))
    if not snaps:
        pytest.skip("parquet present but empty-range after filters")
    # Ordering
    for i in range(1, len(snaps)):
        assert snaps[i].ts_ns >= snaps[i - 1].ts_ns, f"ts not monotonic at {i}"
    # Shape + type
    s0 = snaps[0]
    assert isinstance(s0, OrderBookSnapshot)
    assert s0.ask_px.dtype.kind == "i", f"ask_px must be int64 (scaled), got {s0.ask_px.dtype}"
    assert s0.ask_px.shape == (10,)
    assert s0.bid_qty.shape == (10,)
    assert s0.symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    # Ascending book structure: ask[0] < ask[1] for healthy snapshots
    # (allow rare crossed / zero-padded levels)
    assert int(s0.ask_px[0]) > int(s0.bid_px[0]), "best ask must be > best bid"
    # Scaling sanity — BTC price in USD scaled by 1e8 should be > 1e12
    if s0.symbol == "BTCUSDT":
        raw_px = int(s0.ask_px[0]) / CRYPTO_PRICE_SCALE
        assert 1000 < raw_px < 1_000_000, f"BTC price {raw_px} out of sanity range"


@pytest.mark.skipif(not _lob_archive_has_data(),
                    reason="no parquet yet")
def test_iter_events_window_filter():
    # Use tight window around a known parquet timestamp
    for p in CRYPTO_LOB_ROOT.rglob("*.parquet"):
        import pyarrow.parquet as pq
        tbl = pq.read_table(p)
        ts = tbl["ts_ns"].to_numpy()
        if len(ts) < 2:
            continue
        start, end = int(ts[0]), int(ts[1]) + 1
        snaps = list(iter_events_crypto_lob(start, end, ["BTCUSDT", "ETHUSDT", "SOLUSDT"]))
        assert all(start <= s.ts_ns < end for s in snaps)
        return
    pytest.skip("no usable parquet row")


def test_import_only_without_archive():
    """Adapter must import cleanly even if CRYPTO_LOB_ROOT does not exist."""
    snaps = list(iter_events_crypto_lob(0, 1, ["BTCUSDT"], lob_root=Path("/tmp/_nonexistent_lob")))
    assert snaps == []
