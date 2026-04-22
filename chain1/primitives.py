"""Chain 1 primitive library — the single source of truth for whitelisted
signal primitives (OBI, OFI, microprice, spread, volume flow, regime proxies).

Each public name here MUST match a primitive listed in
`.claude/agents/chain1/_shared/references/cheat_sheets/{obi,ofi}_family_formulas.md`.
Adding a new primitive is a three-step change:
  1. Add the formula to the relevant cheat sheet.
  2. Add the Python implementation here with identical semantics.
  3. Update `PRIMITIVE_WHITELIST` at the bottom so signal-evaluator can verify.

Stateless primitives take a single book snapshot: `f(snap) -> float`.
Stateful primitives use helper classes (RollingMean, RollingStd, etc.) or
require the caller to pass prev_snap explicitly (`f(snap, prev) -> float`).

The 'snap' argument is an `engine.data_loader.OrderBookSnapshot` (dataclass)
or any duck-typed object exposing: bid_px, ask_px, bid_qty, ask_qty (each
a sequence of length >= N_LEVELS), plus scalar fields total_ask_qty,
total_bid_qty, acml_vol, and optional total_ask_icdc / total_bid_icdc.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

EPS = 1e-9


# ---------------------------------------------------------------------------
# Level-based static imbalance
# ---------------------------------------------------------------------------


def obi_1(snap: Any) -> float:
    """Top-of-book OBI. See cheat_sheets/obi_family_formulas.md §Static imbalance.

    Formula: (B_1 - A_1) / (B_1 + A_1)
    """
    b = float(snap.bid_qty[0])
    a = float(snap.ask_qty[0])
    return (b - a) / (b + a + EPS)


def _obi_k(snap: Any, k: int) -> float:
    b = float(np.sum(snap.bid_qty[:k]))
    a = float(np.sum(snap.ask_qty[:k]))
    return (b - a) / (b + a + EPS)


def obi_3(snap: Any) -> float:
    return _obi_k(snap, 3)


def obi_5(snap: Any) -> float:
    return _obi_k(snap, 5)


def obi_10(snap: Any) -> float:
    return _obi_k(snap, 10)


def obi_total(snap: Any) -> float:
    """OBI using TOTAL_BIDP_RSQN / TOTAL_ASKP_RSQN aggregate fields."""
    b = float(snap.total_bid_qty)
    a = float(snap.total_ask_qty)
    return (b - a) / (b + a + EPS)


# ---------------------------------------------------------------------------
# Microprice / VAMP
# ---------------------------------------------------------------------------


def microprice(snap: Any) -> float:
    """Stoikov 2018 microprice. See papers/stoikov_2018_microprice.md.

    Formula: (A_1·Pb_1 + B_1·Pa_1) / (A_1 + B_1)
    """
    b_px = float(snap.bid_px[0])
    a_px = float(snap.ask_px[0])
    b_qty = float(snap.bid_qty[0])
    a_qty = float(snap.ask_qty[0])
    return (a_qty * b_px + b_qty * a_px) / (a_qty + b_qty + EPS)


def microprice_dev_bps(snap: Any) -> float:
    """Microprice deviation from mid in bps. Equivalent to (spread/2) * obi_1
    when expressed in bps.
    """
    b_px = float(snap.bid_px[0])
    a_px = float(snap.ask_px[0])
    mid = (b_px + a_px) / 2.0
    return (microprice(snap) - mid) / (mid + EPS) * 1e4


def vamp_bbo(snap: Any) -> float:
    """Same as microprice; retained as an alias for naming consistency with
    the cheat sheet."""
    return microprice(snap)


def _vamp_k(snap: Any, k: int) -> float:
    b_qty_total = float(np.sum(snap.bid_qty[:k]))
    a_qty_total = float(np.sum(snap.ask_qty[:k]))
    # cross-multiplied: bid_px × ask_qty and ask_px × bid_qty
    num = float(np.sum(np.asarray(snap.bid_px[:k], dtype=np.float64) * np.asarray(snap.ask_qty[:k], dtype=np.float64)))
    num += float(np.sum(np.asarray(snap.ask_px[:k], dtype=np.float64) * np.asarray(snap.bid_qty[:k], dtype=np.float64)))
    return num / (b_qty_total + a_qty_total + EPS)


def vamp_5(snap: Any) -> float:
    return _vamp_k(snap, 5)


def vamp_10(snap: Any) -> float:
    return _vamp_k(snap, 10)


# ---------------------------------------------------------------------------
# Spread / book shape
# ---------------------------------------------------------------------------


def spread_bps(snap: Any) -> float:
    """Top-of-book spread in bps."""
    b = float(snap.bid_px[0])
    a = float(snap.ask_px[0])
    mid = (b + a) / 2.0
    return (a - b) / (mid + EPS) * 1e4


def book_slope_bid(snap: Any) -> float:
    """(Pb_1 − Pb_5) / (B_1 + … + B_5). KRW-per-share metric of bid depth density."""
    den = float(np.sum(snap.bid_qty[:5])) + EPS
    return (float(snap.bid_px[0]) - float(snap.bid_px[4])) / den


def book_slope_ask(snap: Any) -> float:
    den = float(np.sum(snap.ask_qty[:5])) + EPS
    return (float(snap.ask_px[4]) - float(snap.ask_px[0])) / den


# ---------------------------------------------------------------------------
# Flow-based (stateful)
# ---------------------------------------------------------------------------


def ofi_proxy(snap: Any) -> float:
    """KIS pre-computed total-qty delta based OFI proxy. Bounded [-1, 1].

    Uses snap.total_bid_icdc and snap.total_ask_icdc (= TOTAL_BIDP_RSQN_ICDC
    and TOTAL_ASKP_RSQN_ICDC in the raw CSV). These fields are differences
    vs. the previous snapshot already pre-computed by KIS, so no manual
    state management is needed.
    """
    b_icdc = float(getattr(snap, "total_bid_icdc", 0.0))
    a_icdc = float(getattr(snap, "total_ask_icdc", 0.0))
    denom = abs(b_icdc) + abs(a_icdc) + EPS
    return (b_icdc - a_icdc) / denom


def ofi_cks_1(snap: Any, prev: Any | None) -> float:
    """Cont-Kukanov-Stoikov 2014 formal OFI, top-of-book. Stateful.

    See papers/cont_kukanov_stoikov_2014_ofi.md §3 for the three-case formula:
      - bid price up / stay / down
      - ask price down / stay / up
    Returns 0 on the very first tick (no prev).
    """
    if prev is None:
        return 0.0
    bp_now = int(snap.bid_px[0]); bp_prev = int(prev.bid_px[0])
    bq_now = int(snap.bid_qty[0]); bq_prev = int(prev.bid_qty[0])
    ap_now = int(snap.ask_px[0]); ap_prev = int(prev.ask_px[0])
    aq_now = int(snap.ask_qty[0]); aq_prev = int(prev.ask_qty[0])

    # Bid contribution
    if bp_now > bp_prev:
        bid_contrib = bq_now
    elif bp_now == bp_prev:
        bid_contrib = bq_now - bq_prev
    else:
        bid_contrib = -bq_prev

    # Ask contribution
    if ap_now < ap_prev:
        ask_contrib = aq_now
    elif ap_now == ap_prev:
        ask_contrib = aq_now - aq_prev
    else:
        ask_contrib = -aq_prev

    return float(bid_contrib - ask_contrib)


def vol_flow(snap: Any, prev: Any | None) -> float:
    """Trade volume between snapshots (shares). ΔACML_VOL."""
    if prev is None:
        return 0.0
    return float(int(snap.acml_vol) - int(prev.acml_vol))


# ---------------------------------------------------------------------------
# NEW: Mid price + regime / impact primitives
# ---------------------------------------------------------------------------


def mid_px(snap: Any) -> float:
    """Mid price in native currency (KRW for KRX). Useful as target of
    stateful helpers like rolling_realized_vol(mid_px, W) and rolling_momentum."""
    return (float(snap.bid_px[0]) + float(snap.ask_px[0])) / 2.0


def _ofi_depth_k(snap: Any, prev: Any | None, k: int) -> float:
    """Cumulative CKS-style OFI across top k levels.

    For each level i in 1..k, compute same-level bid contribution and ask
    contribution (price-change + size-change logic), sum across levels. Much
    harder to dominate top-of-book since quiet orders at deeper levels still
    contribute.
    """
    if prev is None:
        return 0.0
    total = 0.0
    for i in range(k):
        bp_now, bp_prev = int(snap.bid_px[i]), int(prev.bid_px[i])
        bq_now, bq_prev = int(snap.bid_qty[i]), int(prev.bid_qty[i])
        ap_now, ap_prev = int(snap.ask_px[i]), int(prev.ask_px[i])
        aq_now, aq_prev = int(snap.ask_qty[i]), int(prev.ask_qty[i])

        if bp_now > bp_prev:
            bid_contrib = bq_now
        elif bp_now == bp_prev:
            bid_contrib = bq_now - bq_prev
        else:
            bid_contrib = -bq_prev

        if ap_now < ap_prev:
            ask_contrib = aq_now
        elif ap_now == ap_prev:
            ask_contrib = aq_now - aq_prev
        else:
            ask_contrib = -aq_prev

        total += (bid_contrib - ask_contrib)
    return float(total)


def ofi_depth_5(snap: Any, prev: Any | None) -> float:
    """CKS OFI summed over top 5 levels."""
    return _ofi_depth_k(snap, prev, 5)


def ofi_depth_10(snap: Any, prev: Any | None) -> float:
    """CKS OFI summed over top 10 levels."""
    return _ofi_depth_k(snap, prev, 10)


def minute_of_session(snap: Any) -> float:
    """Minutes elapsed since the nominal KRX session open (09:00 KST).

    Returns a float in roughly [0, 390] for the regular 6.5-hour KRX session
    (09:00-15:30). Useful for time-of-day regime filtering:
      `minute_of_session > 350` → last 40 minutes of session (closing auction
        zone)
      `minute_of_session < 30`  → first 30 minutes after open

    Implementation note: ts_ns is in KST at wall clock. We mod by 86400e9 to
    isolate time-within-day, then subtract 09:00 offset.
    """
    ts = int(snap.ts_ns)
    # Convert ns since epoch to ns since start of day (KST, UTC+9)
    KST_OFFSET_NS = 9 * 3600 * 1_000_000_000
    ns_in_day = (ts + KST_OFFSET_NS) % (86400 * 1_000_000_000)
    # Subtract 09:00 offset, clip to [0, session_length_ns]
    SESSION_START_NS = 9 * 3600 * 1_000_000_000
    ns_since_open = ns_in_day - SESSION_START_NS
    return ns_since_open / 60_000_000_000.0  # ns → minutes


def book_thickness(snap: Any) -> float:
    """Sum of total bid and ask quantities — proxy for overall book liquidity."""
    return float(int(snap.total_bid_qty) + int(snap.total_ask_qty))


# ---------------------------------------------------------------------------
# Block C (2026-04-21) — Advanced microstructure primitives (new families)
#
# These sit outside the OBI/OFI/microprice cluster and expose genuinely new
# information channels:
#   - trade_imbalance_signed: Lee-Ready tick-rule signed ACML_VOL — trade-based
#   - bid/ask_depth_concentration: where in the book is liquidity concentrated
#     (BBO-heavy vs spread-out) — book shape dimension independent of OBI
#   - obi_ex_bbo: deep-book imbalance excluding the noisy top level — often
#     more persistent than obi_1 because it reflects patient liquidity
# ---------------------------------------------------------------------------


def trade_imbalance_signed(snap: Any, prev: Any | None) -> float:
    """Lee-Ready (1991) signed trade volume over last tick.

    Classification rule (tick rule):
      - If mid_t > mid_{t-1}: uptick → buyer-initiated → +ΔACML_VOL
      - If mid_t < mid_{t-1}: downtick → seller-initiated → −ΔACML_VOL
      - If mid_t == mid_{t-1}: unclassified → 0 (conservative; zero-tick rule
        is also acceptable but introduces path dependency)

    Returns: signed trade volume in shares. Use with rolling_mean / zscore for
    stable trend signals:
        zscore(trade_imbalance_signed, 300)  # 30s z-score
        rolling_mean(trade_imbalance_signed, 50)  # 5s smoothed flow

    Fundamentally different from OBI/OFI because it reflects **actual completed
    trades**, not the state of resting liquidity.
    """
    if prev is None:
        return 0.0
    dvol = int(snap.acml_vol) - int(prev.acml_vol)
    if dvol == 0:
        return 0.0
    mid_now = (float(snap.bid_px[0]) + float(snap.ask_px[0])) / 2.0
    mid_prev = (float(prev.bid_px[0]) + float(prev.ask_px[0])) / 2.0
    if mid_now > mid_prev:
        return float(dvol)      # buyer-initiated
    if mid_now < mid_prev:
        return -float(dvol)     # seller-initiated
    return 0.0                  # mid unchanged → unclassified


def bid_depth_concentration(snap: Any) -> float:
    """Fraction of total bid volume resting at the best bid (level 1).

    Formula: B_1 / total_bid
    Range: [0, 1]
      - 1.0 = all bid liquidity sits at BBO (front-loaded, aggressive)
      - 0.0 = BBO is empty (thin top, deep book)

    Distinct from OBI: OBI compares bid vs ask at BBO; this captures
    bid-side SHAPE independent of the opposing ask side.
    Ref: Bouchaud-Mezard-Potters 2002 book-shape decomposition.
    """
    b1 = float(snap.bid_qty[0])
    total = float(snap.total_bid_qty)
    if total < EPS:
        return 0.0
    return b1 / total


def ask_depth_concentration(snap: Any) -> float:
    """Fraction of total ask volume resting at the best ask (level 1). Mirror
    of bid_depth_concentration. See that primitive for semantics.
    """
    a1 = float(snap.ask_qty[0])
    total = float(snap.total_ask_qty)
    if total < EPS:
        return 0.0
    return a1 / total


def obi_ex_bbo(snap: Any) -> float:
    """Deep-book imbalance EXCLUDING the best bid/ask level.

    Formula: (Σ B_{2..5} − Σ A_{2..5}) / (Σ B_{2..5} + Σ A_{2..5})
    Range: [−1, 1]

    Rationale: obi_1 is dominated by fleeting BBO-level noise (cancelations
    and fast re-quotes). This primitive captures the "patient" liquidity
    orientation at levels 2–5, which is structurally more persistent.
    Orthogonal to obi_1 in the information sense — when both agree it is a
    strong conviction; when they disagree obi_1 may be a short-term stall.

    Ref: Gould-Bonart 2016 §queue-level dynamics; Cont-Kukanov-Stoikov 2014 §6
    (layer contributions).
    """
    # Use levels 2..5 (indices 1..4 inclusive)
    b_deep = float(np.sum(snap.bid_qty[1:5]))
    a_deep = float(np.sum(snap.ask_qty[1:5]))
    return (b_deep - a_deep) / (b_deep + a_deep + EPS)


# ---------------------------------------------------------------------------
# Rolling / standardization helpers (stateful, used via update)
# ---------------------------------------------------------------------------


@dataclass
class RollingMean:
    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        return float(np.mean(self._buf))


@dataclass
class RollingStd:
    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        if len(self._buf) < 2:
            return 0.0
        return float(np.std(self._buf))


@dataclass
class RollingZScore:
    """Standardize x against trailing window. Returns 0 until 2 samples seen."""

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        if len(self._buf) < 2:
            return 0.0
        arr = np.asarray(self._buf, dtype=np.float64)
        m = float(arr.mean())
        s = float(arr.std())
        if s < EPS:
            return 0.0
        return (float(x) - m) / s


@dataclass
class RollingRealizedVol:
    """Realized volatility of a primitive's rolling series.

    Stores last `window+1` values; returns sqrt(Σ(Δx)²) over the last `window`
    differences. Useful as `rolling_realized_vol(mid_px, 100)` to get mid-price
    volatility in KRW (or as regime filter threshold).
    """

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # We need window+1 samples to form `window` diffs
        self._buf = deque(maxlen=self.window + 1)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        if len(self._buf) < 2:
            return 0.0
        arr = np.asarray(self._buf, dtype=np.float64)
        diffs = np.diff(arr)
        return float(np.sqrt(float(np.sum(diffs * diffs))))


@dataclass
class RollingMomentum:
    """Momentum = current − oldest in window. Over `window` samples total (so
    the returned value spans window-1 steps of change)."""

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        if len(self._buf) < 2:
            return 0.0
        return float(self._buf[-1]) - float(self._buf[0])


@dataclass
class RollingPriceImpact:
    """Mid-price change per unit trade-volume over a rolling window.

    Stores (mid, cumvol) tuples; returns `(mid_now - mid_oldest) / (cumvol_now
    - cumvol_oldest + EPS)`. In KRW per share. Positive if price rose per unit
    of trade volume (demand pressure). Zero if no volume.
    """

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, mid: float, acml_vol: float) -> float:
        self._buf.append((float(mid), float(acml_vol)))
        if len(self._buf) < 2:
            return 0.0
        mid_old, vol_old = self._buf[0]
        mid_new, vol_new = self._buf[-1]
        dv = vol_new - vol_old
        return (mid_new - mid_old) / (dv + EPS)


@dataclass
class RollingArrivalRate:
    """Fraction of ticks in window that had a non-zero trade (vol_flow > 0).

    Returns value in [0, 1]. Useful as activity/volatility regime proxy.
    """

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, vol_flow_val: float) -> float:
        self._buf.append(1 if float(vol_flow_val) > 0 else 0)
        return float(sum(self._buf)) / max(1, len(self._buf))


# ---------------------------------------------------------------------------
# Whitelist (consumed by signal-evaluator §Primitive whitelist check)
# ---------------------------------------------------------------------------

PRIMITIVE_WHITELIST: dict[str, dict[str, Any]] = {
    # name → {callable, is_stateful, bounded_range_or_None, cheat_sheet_anchor}
    # --- OBI family ---
    "obi_1":            {"fn": obi_1,            "stateful": False, "bounded": (-1.0, 1.0), "ref": "obi_family#static"},
    "obi_3":            {"fn": obi_3,            "stateful": False, "bounded": (-1.0, 1.0), "ref": "obi_family#static"},
    "obi_5":            {"fn": obi_5,            "stateful": False, "bounded": (-1.0, 1.0), "ref": "obi_family#static"},
    "obi_10":           {"fn": obi_10,           "stateful": False, "bounded": (-1.0, 1.0), "ref": "obi_family#static"},
    "obi_total":        {"fn": obi_total,        "stateful": False, "bounded": (-1.0, 1.0), "ref": "obi_family#static"},
    # --- Microprice / VAMP ---
    "microprice":       {"fn": microprice,       "stateful": False, "bounded": None,        "ref": "obi_family#microstructure"},
    "microprice_dev_bps": {"fn": microprice_dev_bps, "stateful": False, "bounded": None,    "ref": "obi_family#microstructure"},
    "vamp_bbo":         {"fn": vamp_bbo,         "stateful": False, "bounded": None,        "ref": "obi_family#microstructure"},
    "vamp_5":           {"fn": vamp_5,           "stateful": False, "bounded": None,        "ref": "obi_family#microstructure"},
    "vamp_10":          {"fn": vamp_10,          "stateful": False, "bounded": None,        "ref": "obi_family#microstructure"},
    # --- Spread / Book shape ---
    "spread_bps":       {"fn": spread_bps,       "stateful": False, "bounded": None,        "ref": "obi_family#spread"},
    "book_slope_bid":   {"fn": book_slope_bid,   "stateful": False, "bounded": None,        "ref": "obi_family#spread"},
    "book_slope_ask":   {"fn": book_slope_ask,   "stateful": False, "bounded": None,        "ref": "obi_family#spread"},
    "book_thickness":   {"fn": book_thickness,   "stateful": False, "bounded": (0, None),   "ref": "regime_primitives#liquidity"},
    # --- OFI / flow ---
    "ofi_proxy":        {"fn": ofi_proxy,        "stateful": False, "bounded": (-1.0, 1.0), "ref": "ofi_family#whitelist"},
    "ofi_cks_1":        {"fn": ofi_cks_1,        "stateful": True,  "bounded": None,        "ref": "ofi_family#whitelist"},
    "ofi_depth_5":      {"fn": ofi_depth_5,      "stateful": True,  "bounded": None,        "ref": "ofi_family#depth"},
    "ofi_depth_10":     {"fn": ofi_depth_10,     "stateful": True,  "bounded": None,        "ref": "ofi_family#depth"},
    "vol_flow":         {"fn": vol_flow,         "stateful": True,  "bounded": (0, None),   "ref": "ofi_family#whitelist"},
    # --- Price / regime ---
    "mid_px":           {"fn": mid_px,           "stateful": False, "bounded": (0, None),   "ref": "regime_primitives#price"},
    "minute_of_session": {"fn": minute_of_session, "stateful": False, "bounded": (-60, 420), "ref": "regime_primitives#time"},
    # --- Block C (2026-04-21): advanced microstructure — trade-based / shape-based ---
    "trade_imbalance_signed":  {"fn": trade_imbalance_signed,  "stateful": True,  "bounded": None,       "ref": "microstructure_advanced#trade_flow"},
    "bid_depth_concentration": {"fn": bid_depth_concentration, "stateful": False, "bounded": (0.0, 1.0), "ref": "microstructure_advanced#book_shape"},
    "ask_depth_concentration": {"fn": ask_depth_concentration, "stateful": False, "bounded": (0.0, 1.0), "ref": "microstructure_advanced#book_shape"},
    "obi_ex_bbo":              {"fn": obi_ex_bbo,              "stateful": False, "bounded": (-1.0, 1.0),"ref": "microstructure_advanced#deep_book"},
}


def is_primitive(name: str) -> bool:
    return name in PRIMITIVE_WHITELIST


__all__ = list(PRIMITIVE_WHITELIST.keys()) + [
    "RollingMean", "RollingStd", "RollingZScore",
    "RollingRealizedVol", "RollingMomentum", "RollingPriceImpact", "RollingArrivalRate",
    "PRIMITIVE_WHITELIST", "is_primitive",
]
