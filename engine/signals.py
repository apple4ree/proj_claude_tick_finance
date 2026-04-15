"""Signal primitives for tick strategies.

Each primitive reads a current OrderBookSnapshot and per-symbol rolling
state, and returns a scalar. State is updated centrally each tick before
primitives are evaluated, so primitives themselves are pure reads.

Registered primitives form SIGNAL_REGISTRY and are invoked by name from
the DSL evaluator (engine/dsl.py).
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Callable

from engine.data_loader import OrderBookSnapshot


@dataclass
class SymbolState:
    symbol: str
    mid_buffer: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=4096)
    )
    acml_vol_buffer: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=4096)
    )
    best_ask_buffer: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=4096)
    )
    best_bid_buffer: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=4096)
    )


def update_state(st: SymbolState, snap: OrderBookSnapshot) -> None:
    st.mid_buffer.append(snap.mid)
    st.acml_vol_buffer.append(int(snap.acml_vol))
    st.best_ask_buffer.append(int(snap.ask_px[0]))
    st.best_bid_buffer.append(int(snap.bid_px[0]))


# ---------------------------------------------------------------------------
# Primitives (pure reads)
# ---------------------------------------------------------------------------

def sig_mid(snap: OrderBookSnapshot, st: SymbolState) -> float:
    return float(snap.mid)


def sig_spread(snap: OrderBookSnapshot, st: SymbolState) -> float:
    return float(snap.spread)


def sig_best_ask(snap: OrderBookSnapshot, st: SymbolState) -> float:
    return float(snap.ask_px[0])


def sig_best_bid(snap: OrderBookSnapshot, st: SymbolState) -> float:
    return float(snap.bid_px[0])


def sig_obi(snap: OrderBookSnapshot, st: SymbolState, depth: int = 5) -> float:
    depth = max(1, min(int(depth), len(snap.ask_qty)))
    b = int(snap.bid_qty[:depth].sum())
    a = int(snap.ask_qty[:depth].sum())
    if a + b == 0:
        return 0.0
    return (b - a) / (b + a)


def sig_microprice(snap: OrderBookSnapshot, st: SymbolState) -> float:
    ba = int(snap.bid_qty[0])
    aa = int(snap.ask_qty[0])
    if ba + aa == 0:
        return float(snap.mid)
    return (int(snap.ask_px[0]) * ba + int(snap.bid_px[0]) * aa) / (ba + aa)


def sig_total_imbalance(snap: OrderBookSnapshot, st: SymbolState) -> float:
    denom = snap.total_ask_qty + snap.total_bid_qty
    if denom == 0:
        return 0.0
    return (snap.total_bid_qty - snap.total_ask_qty) / denom


def sig_volume_delta(snap: OrderBookSnapshot, st: SymbolState, lookback: int = 1) -> float:
    lb = max(1, int(lookback))
    if len(st.acml_vol_buffer) < lb + 1:
        return 0.0
    return float(st.acml_vol_buffer[-1] - st.acml_vol_buffer[-lb - 1])


def sig_mid_return_bps(snap: OrderBookSnapshot, st: SymbolState, lookback: int = 1) -> float:
    lb = max(1, int(lookback))
    if len(st.mid_buffer) < lb + 1:
        return 0.0
    cur = st.mid_buffer[-1]
    ref = st.mid_buffer[-lb - 1]
    if ref == 0:
        return 0.0
    return (cur - ref) / ref * 1e4


def sig_mid_change(snap: OrderBookSnapshot, st: SymbolState, lookback: int = 1) -> float:
    lb = max(1, int(lookback))
    if len(st.mid_buffer) < lb + 1:
        return 0.0
    return float(st.mid_buffer[-1] - st.mid_buffer[-lb - 1])


def sig_spread_bps(snap: OrderBookSnapshot, st: SymbolState) -> float:
    mid = float(snap.mid)
    if mid <= 0:
        return 0.0
    return float(snap.spread) / mid * 1e4


def sig_krw_turnover(snap: OrderBookSnapshot, st: SymbolState, lookback: int = 1) -> float:
    """KRW-notional turnover over the last `lookback` ticks.

    Returns (acml_vol_delta_shares * current_mid_KRW), a share-price-agnostic
    activity gate. Use this instead of volume_delta when comparing symbols
    with very different share prices (e.g. 000660 at 934k KRW vs 010140 at
    28k KRW) — a uniform share-count threshold silently excludes low-float
    high-price names while allowing noisy low-price names.

    Typical IS values (10:30-13:00 window, 1-tick lookback):
      000660 (SK Hynix):   ~500k–5M KRW per tick
      006800 (Mirae):      ~50k–500k KRW per tick
      034020 (Doosan):     ~100k–2M KRW per tick
    Gate suggestion: krw_turnover > 5e8  (500M KRW over lookback ticks)
    """
    lb = max(1, int(lookback))
    if len(st.acml_vol_buffer) < lb + 1:
        return 0.0
    vol_delta = float(st.acml_vol_buffer[-1] - st.acml_vol_buffer[-lb - 1])
    mid = float(snap.mid)
    return vol_delta * mid


SIGNAL_REGISTRY: dict[str, Callable] = {
    "mid": sig_mid,
    "spread": sig_spread,
    "best_ask": sig_best_ask,
    "best_bid": sig_best_bid,
    "obi": sig_obi,
    "microprice": sig_microprice,
    "total_imbalance": sig_total_imbalance,
    "volume_delta": sig_volume_delta,
    "mid_return_bps": sig_mid_return_bps,
    "mid_change": sig_mid_change,
    "spread_bps": sig_spread_bps,
    "krw_turnover": sig_krw_turnover,
}
