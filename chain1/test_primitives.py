"""Unit tests for chain1.primitives — numeric regression against hand-computed values."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from chain1.primitives import (
    EPS,
    obi_1, obi_3, obi_5, obi_10, obi_total,
    microprice, microprice_dev_bps, vamp_bbo, vamp_5, vamp_10,
    spread_bps, book_slope_bid, book_slope_ask, book_thickness,
    ofi_proxy, ofi_cks_1, ofi_depth_5, ofi_depth_10, vol_flow,
    mid_px, minute_of_session,
    RollingMean, RollingStd, RollingZScore,
    RollingRealizedVol, RollingMomentum, RollingPriceImpact, RollingArrivalRate,
    PRIMITIVE_WHITELIST, is_primitive,
)


# ---------------------------------------------------------------------------
# Synthetic snap fixture (duck-typed)
# ---------------------------------------------------------------------------


@dataclass
class MockSnap:
    bid_px: np.ndarray
    ask_px: np.ndarray
    bid_qty: np.ndarray
    ask_qty: np.ndarray
    total_bid_qty: int
    total_ask_qty: int
    acml_vol: int = 0
    total_bid_icdc: float = 0.0
    total_ask_icdc: float = 0.0
    ts_ns: int = 0


def make_snap(**kw):
    """Build a 10-level snap with sensible defaults. Override via kwargs."""
    defaults = dict(
        bid_px=np.array([100, 99, 98, 97, 96, 95, 94, 93, 92, 91], dtype=np.int64),
        ask_px=np.array([101, 102, 103, 104, 105, 106, 107, 108, 109, 110], dtype=np.int64),
        bid_qty=np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=np.int64),
        ask_qty=np.array([5, 15, 25, 35, 45, 55, 65, 75, 85, 95], dtype=np.int64),
        total_bid_qty=10 + 20 + 30 + 40 + 50 + 60 + 70 + 80 + 90 + 100,
        total_ask_qty=5 + 15 + 25 + 35 + 45 + 55 + 65 + 75 + 85 + 95,
    )
    defaults.update(kw)
    return MockSnap(**defaults)


# ---------------------------------------------------------------------------
# OBI tests
# ---------------------------------------------------------------------------


def test_obi_1_symmetric_balanced():
    snap = make_snap(
        bid_qty=np.array([10, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.int64),
        ask_qty=np.array([10, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.int64),
    )
    assert abs(obi_1(snap) - 0.0) < 1e-9


def test_obi_1_bid_heavy():
    snap = make_snap()
    # bid_qty[0]=10, ask_qty[0]=5 → (10-5)/(10+5) = 1/3
    assert abs(obi_1(snap) - 1/3) < 1e-9


def test_obi_5_matches_manual():
    snap = make_snap()
    # sum(bid[:5]) = 10+20+30+40+50 = 150
    # sum(ask[:5]) = 5+15+25+35+45 = 125
    # (150-125)/(150+125) = 25/275
    assert abs(obi_5(snap) - 25/275) < 1e-9


def test_obi_total():
    snap = make_snap()
    # total_bid=550, total_ask=500
    expected = (550 - 500) / (550 + 500)
    assert abs(obi_total(snap) - expected) < 1e-9


def test_obi_1_10_bounds():
    snap = make_snap()
    for fn in [obi_1, obi_3, obi_5, obi_10, obi_total]:
        v = fn(snap)
        assert -1.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# Microprice / VAMP tests
# ---------------------------------------------------------------------------


def test_microprice_formula():
    snap = make_snap()
    # microprice = (A1*B_px + B1*A_px)/(A1+B1) = (5*100 + 10*101)/(5+10) = 1510/15 = 100.666...
    expected = (5 * 100 + 10 * 101) / (5 + 10)
    assert abs(microprice(snap) - expected) < 1e-6


def test_microprice_dev_bps_matches_identity():
    """microprice_dev_bps should equal (spread_bps/2) * obi_1 to high precision."""
    snap = make_snap()
    dev = microprice_dev_bps(snap)
    identity = (spread_bps(snap) / 2.0) * obi_1(snap)
    assert abs(dev - identity) < 1e-6


def test_vamp_5_reduces_to_microprice_at_k1():
    snap = make_snap()
    # vamp at k=1 equals microprice (by construction)
    # (not testing that directly — using internal _vamp_k)
    from chain1.primitives import _vamp_k
    assert abs(_vamp_k(snap, 1) - microprice(snap)) < 1e-6


def test_vamp_5_matches_manual():
    snap = make_snap()
    # Σ bid_px[:5]*ask_qty[:5] + Σ ask_px[:5]*bid_qty[:5] / (Σ bid[:5] + Σ ask[:5])
    bpx = snap.bid_px[:5]; apx = snap.ask_px[:5]
    bqty = snap.bid_qty[:5]; aqty = snap.ask_qty[:5]
    num = (bpx * aqty).sum() + (apx * bqty).sum()
    den = bqty.sum() + aqty.sum()
    expected = num / den
    assert abs(vamp_5(snap) - expected) < 1e-3


# ---------------------------------------------------------------------------
# Spread / book slope
# ---------------------------------------------------------------------------


def test_spread_bps():
    snap = make_snap()
    # ask[0]=101, bid[0]=100, mid=100.5, spread=1 → 1/100.5*1e4 ≈ 99.5
    expected = (101 - 100) / 100.5 * 1e4
    assert abs(spread_bps(snap) - expected) < 1e-3


def test_book_slope_bid():
    snap = make_snap()
    # (100 - 96) / (10+20+30+40+50) = 4/150
    expected = 4 / 150
    assert abs(book_slope_bid(snap) - expected) < 1e-6


def test_book_slope_ask():
    snap = make_snap()
    # (105 - 101) / (5+15+25+35+45) = 4/125
    expected = 4 / 125
    assert abs(book_slope_ask(snap) - expected) < 1e-6


# ---------------------------------------------------------------------------
# OFI
# ---------------------------------------------------------------------------


def test_ofi_proxy_zero_when_deltas_zero():
    snap = make_snap(total_bid_icdc=0.0, total_ask_icdc=0.0)
    assert abs(ofi_proxy(snap) - 0.0) < 1e-9


def test_ofi_proxy_bid_pressure():
    snap = make_snap(total_bid_icdc=+100.0, total_ask_icdc=-50.0)
    # (100 - (-50)) / (|100|+|-50|+ε) = 150/150 = 1.0
    assert abs(ofi_proxy(snap) - 1.0) < 1e-6


def test_ofi_cks_1_zero_on_first():
    snap = make_snap()
    assert ofi_cks_1(snap, None) == 0.0


def test_ofi_cks_1_bid_up():
    """Bid price moves up → bid_contrib = bq_now (new level). Ask unchanged → ask_contrib = 0."""
    prev = make_snap(
        bid_px=np.array([99]*10, dtype=np.int64),
        bid_qty=np.array([7]*10, dtype=np.int64),
    )
    snap = make_snap(
        bid_px=np.array([100]*10, dtype=np.int64),   # went up
        bid_qty=np.array([12]*10, dtype=np.int64),
        ask_px=prev.ask_px,
        ask_qty=prev.ask_qty,
    )
    v = ofi_cks_1(snap, prev)
    # bid_contrib = 12 (new level). ask unchanged → ask_contrib = ask_qty_now - ask_qty_prev = 0
    assert abs(v - 12.0) < 1e-9


def test_ofi_cks_1_ask_down_is_bullish():
    """Ask price drops → ask_contrib = aq_now (new level), contributes negatively."""
    prev = make_snap()
    snap = make_snap(
        ask_px=np.array([100]*10, dtype=np.int64),  # ask dropped from 101 to 100
        ask_qty=np.array([3]*10, dtype=np.int64),
    )
    v = ofi_cks_1(snap, prev)
    # bid contrib: bid_px same (100), qty same (10) → 0
    # ask contrib: ap_now(100) < ap_prev(101) → ask_contrib = aq_now = 3
    # result = 0 - 3 = -3 (bullish in CKS convention is negative because ask qty freshly added?)
    # Note: in CKS, ask_contrib positive when ask adds qty at better price (for seller),
    # and final OFI = bid_contrib - ask_contrib. Here ask moved DOWN = new seller on our side:
    # That's net SELL pressure, so OFI should be negative → v = -3 consistent.
    assert abs(v - (-3.0)) < 1e-9


# ---------------------------------------------------------------------------
# vol_flow
# ---------------------------------------------------------------------------


def test_vol_flow_no_prev():
    snap = make_snap(acml_vol=100)
    assert vol_flow(snap, None) == 0.0


def test_vol_flow_delta():
    prev = make_snap(acml_vol=100)
    snap = make_snap(acml_vol=130)
    assert vol_flow(snap, prev) == 30.0


# ---------------------------------------------------------------------------
# Rolling helpers
# ---------------------------------------------------------------------------


def test_rolling_mean():
    rm = RollingMean(3)
    assert rm.update(1.0) == 1.0
    assert rm.update(3.0) == 2.0
    assert rm.update(5.0) == 3.0
    assert rm.update(7.0) == 5.0  # oldest (1.0) dropped


def test_rolling_std_two_samples():
    rs = RollingStd(3)
    assert rs.update(1.0) == 0.0  # only 1 sample
    s = rs.update(3.0)
    assert abs(s - 1.0) < 1e-6  # std of {1, 3} = 1


def test_rolling_zscore():
    rz = RollingZScore(100)
    rz.update(0.0)
    rz.update(10.0)
    # {0, 10}: mean=5, std=5
    z = rz.update(20.0)
    # when x=20: {0, 10, 20} mean=10, std=sqrt(((0-10)²+(10-10)²+(20-10)²)/3) = sqrt(66.67) ≈ 8.165
    # z = (20-10)/8.165 ≈ 1.225
    assert 1.0 < z < 1.5


# ---------------------------------------------------------------------------
# NEW: primitives added in Block A (realized vol, depth-k OFI, regime proxies)
# ---------------------------------------------------------------------------


def test_mid_px():
    snap = make_snap()
    # bid1=100, ask1=101 → mid = 100.5
    assert abs(mid_px(snap) - 100.5) < 1e-9


def test_book_thickness():
    snap = make_snap()
    assert abs(book_thickness(snap) - (550 + 500)) < 1e-9


def test_ofi_depth_5_zero_on_first():
    snap = make_snap()
    assert ofi_depth_5(snap, None) == 0.0
    assert ofi_depth_10(snap, None) == 0.0


def test_ofi_depth_5_equals_sum_of_per_level():
    """Make both snaps identical except level 3 bid jumps up — only level 3
    contributes; ofi_depth_5 should equal that contribution."""
    prev = make_snap(
        bid_qty=np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=np.int64),
    )
    snap = make_snap(
        bid_qty=np.array([10, 20, 35, 40, 50, 60, 70, 80, 90, 100], dtype=np.int64),
    )
    # Level 3 bid_qty went from 30 to 35 (price same); contrib = 5
    # Other levels unchanged → 0 contribution
    # Ask all unchanged → 0 contribution
    assert abs(ofi_depth_5(snap, prev) - 5.0) < 1e-9
    # ofi_depth_10 should be identical since deeper levels unchanged too
    assert abs(ofi_depth_10(snap, prev) - 5.0) < 1e-9


def test_minute_of_session_open():
    """ts corresponding to exactly 09:00 KST → minute 0."""
    # 2026-03-26 00:00:00 UTC = 2026-03-26 09:00:00 KST → ns since epoch
    import datetime as dt
    t_utc = dt.datetime(2026, 3, 26, 0, 0, 0, tzinfo=dt.timezone.utc)
    ns = int(t_utc.timestamp() * 1e9)
    snap = make_snap()
    snap.ts_ns = ns
    m = minute_of_session(snap)
    assert abs(m - 0) < 1e-3, f"expected ~0, got {m}"


def test_minute_of_session_mid_session():
    """12:30 KST → 210 minutes."""
    import datetime as dt
    t_utc = dt.datetime(2026, 3, 26, 3, 30, 0, tzinfo=dt.timezone.utc)  # 12:30 KST
    ns = int(t_utc.timestamp() * 1e9)
    snap = make_snap()
    snap.ts_ns = ns
    m = minute_of_session(snap)
    assert abs(m - 210) < 1e-3, f"expected 210, got {m}"


def test_rolling_realized_vol_basic():
    rv = RollingRealizedVol(3)
    assert rv.update(100.0) == 0.0  # single sample
    # diffs: 100→101 = 1
    assert abs(rv.update(101.0) - 1.0) < 1e-9
    # diffs: 100→101→103 → [1, 2] → sqrt(1 + 4) = sqrt(5)
    import math
    assert abs(rv.update(103.0) - math.sqrt(5)) < 1e-6


def test_rolling_momentum_basic():
    rm = RollingMomentum(3)
    assert rm.update(100.0) == 0.0
    assert rm.update(103.0) == 3.0   # 103 - 100
    assert rm.update(108.0) == 8.0   # 108 - 100 (window full)
    assert rm.update(110.0) == 7.0   # 110 - 103 (oldest dropped)


def test_rolling_price_impact_basic():
    rpi = RollingPriceImpact(3)
    # no prev → 0
    assert rpi.update(100.0, 1000) == 0.0
    # mid 100→105, vol 1000→1200 → 5 / 200 = 0.025
    assert abs(rpi.update(105.0, 1200) - 0.025) < 1e-9


def test_rolling_arrival_rate_basic():
    rar = RollingArrivalRate(4)
    assert rar.update(0.0) == 0.0    # no vol
    assert rar.update(5.0) == 0.5    # 1/2 had vol
    assert abs(rar.update(0.0) - 1/3) < 1e-9
    assert abs(rar.update(10.0) - 2/4) < 1e-9


# ---------------------------------------------------------------------------
# Whitelist completeness
# ---------------------------------------------------------------------------


def test_whitelist_names_are_callable():
    for name, meta in PRIMITIVE_WHITELIST.items():
        assert callable(meta["fn"]), f"{name} fn not callable"


def test_is_primitive():
    assert is_primitive("obi_1")
    assert is_primitive("microprice_dev_bps")
    assert not is_primitive("bogus_primitive_xyz")


if __name__ == "__main__":
    # Simple runner if pytest not available
    import inspect
    import traceback
    mod = __import__(__name__)
    funcs = [(n, f) for n, f in inspect.getmembers(mod, inspect.isfunction) if n.startswith("test_")]
    passed = 0
    failed = []
    for n, f in funcs:
        try:
            f()
            passed += 1
        except AssertionError as e:
            failed.append((n, str(e)))
        except Exception as e:
            failed.append((n, f"{type(e).__name__}: {e}"))
    print(f"{passed}/{len(funcs)} passed")
    for n, msg in failed:
        print(f"  FAIL {n}: {msg}")
