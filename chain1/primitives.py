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
# Block F (2026-04-27) — Time-of-day regime indicators
#
# Boolean flags for KRX intraday magnitude regimes. Multiplying any directional
# primitive by one of these gates the entry to a specific time window where
# |Δmid| is empirically larger (opening / closing burst) or smaller (lunch),
# which directly serves the net-PnL objective: gross expectancy must exceed
# the round-trip fee, and burst regimes are where that is most likely.
#
# Boundaries (KRX regular session is 09:00–15:30 KST = 0–390 min):
#   opening_burst : 0–30  min (~09:00–09:30) — opening auction unwind
#   lunch_lull    : 150–240 min (~11:30–13:00) — minimum-volume window
#   closing_burst : 330–390 min (~14:30–15:30) — closing auction build-up
#
# References:
#   - cheat_sheets/time_of_day_regimes.md (KRX-specific measured magnitudes)
#   - Andersen-Bollerslev 1997 "Intraday periodicity and volatility"
#   - Wood-McInish-Ord 1985 "An investigation of transactions data"
# ---------------------------------------------------------------------------


def is_opening_burst(snap: Any) -> float:
    """1.0 during the first 30 min of the KRX session (09:00–09:30 KST), else 0.0.

    KRX opening burst is the highest-magnitude window of the day — overnight
    information accumulation unwinds in this period. Use as a multiplicative
    gate on a directional signal to concentrate fills where |Δmid| is large.
    """
    m = minute_of_session(snap)
    return 1.0 if 0.0 <= m < 30.0 else 0.0


def is_lunch_lull(snap: Any) -> float:
    """1.0 during the lunch lull (11:30–13:00 KST = 150–240 min), else 0.0.

    KRX lunch is the lowest-volume / lowest-magnitude window. Use as a
    NEGATION filter (`(1 - is_lunch_lull) * directional`) — i.e., suppress
    entries during this regime because the magnitude rarely covers the fee.
    """
    m = minute_of_session(snap)
    return 1.0 if 150.0 <= m < 240.0 else 0.0


def is_closing_burst(snap: Any) -> float:
    """1.0 during the last 60 min of the KRX session (14:30–15:30 KST), else 0.0.

    KRX closing burst is the second-highest-magnitude window — closing-auction
    inventory rebalancing produces large directional moves. Like
    is_opening_burst, useful as a magnitude-concentrating gate.
    """
    m = minute_of_session(snap)
    return 1.0 if 330.0 <= m < 390.0 else 0.0


# ---------------------------------------------------------------------------
# Block G (2026-04-27, STAGED for v5) — illiquidity / momentum primitives
#
# These are implemented but NOT yet registered in PRIMITIVE_WHITELIST or
# STATEFUL_HELPERS. They become callable to the LLM only when the
# corresponding cheat sheet is added and the whitelist is opened (planned
# for the v5 launch after the v4 run completes — clean ablation).
#
# References:
#   - kyle_lambda_proxy: Kyle 1985, Amihud 2002 — illiquidity = |Δmid|/Δvol
#   - rolling_autocorr_lag1: short-horizon momentum / mean-reversion detector
# ---------------------------------------------------------------------------


def kyle_lambda_proxy(snap: Any, prev: Any | None) -> float:
    """Single-tick Kyle λ proxy: |Δmid_px| / Δacml_vol.

    Tick-level Amihud-style illiquidity measure. Larger values indicate the
    market is moving more per unit of trade volume — a high-magnitude regime.
    Use with rolling_mean to smooth (single-tick is noisy).

    Returns 0.0 on the first tick (no prev) or when Δvolume == 0.
    Reference: Kyle 1985, Amihud 2002.
    """
    if prev is None:
        return 0.0
    d_mid = abs(mid_px(snap) - mid_px(prev))
    d_vol = abs(float(snap.acml_vol) - float(prev.acml_vol))
    if d_vol < 1.0:
        return 0.0
    return d_mid / d_vol


@dataclass
class RollingAutocorrLag1:
    """Lag-1 autocorrelation of a primitive over a rolling window.

    Stores last `window` values; returns Pearson corr(x_t, x_{t-1}) over the
    window. Positive → momentum (consecutive ticks agree in direction).
    Negative → mean-reversion (alternating direction, e.g., bid-ask bounce).
    Useful as `rolling_autocorr_lag1(mid_returns, 200)` to gate to momentum
    regimes where horizon-extension yields larger |Δmid|.
    """

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Need window+1 to form `window` (x_t, x_{t-1}) pairs
        self._buf = deque(maxlen=self.window + 1)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        if len(self._buf) < 3:
            return 0.0
        arr = np.asarray(self._buf, dtype=np.float64)
        x_t = arr[1:]
        x_tm1 = arr[:-1]
        m1 = float(x_t.mean())
        m0 = float(x_tm1.mean())
        s1 = float(x_t.std())
        s0 = float(x_tm1.std())
        if s1 < EPS or s0 < EPS:
            return 0.0
        cov = float(np.mean((x_t - m1) * (x_tm1 - m0)))
        return cov / (s1 * s0)


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
    """Signed trade volume — direct or Lee-Ready tick rule fallback.

    Path 1 (NEW 2026-04-26, tickdata_krx v2 only):
      If snap.askbid_type ∈ {1, 2} (direct exchange classification), return
      ±snap.trade_volume directly. Highest accuracy (~95%+ vs Lee-Ready's ~85%).

    Path 2 (legacy, tick rule):
      Use mid-direction as Lee-Ready proxy:
        - mid_t > mid_{t-1}: uptick → buyer-initiated → +ΔACML_VOL
        - mid_t < mid_{t-1}: downtick → seller-initiated → −ΔACML_VOL
        - else: unclassified → 0

    The interface is unchanged so existing specs continue to work; v2 data
    silently upgrades the accuracy.

    Returns: signed trade volume in shares.
    """
    # Path 1: direct from feed (v2 only)
    if snap.askbid_type == 1:
        return float(snap.trade_volume)
    if snap.askbid_type == 2:
        return -float(snap.trade_volume)
    # Path 2: tick rule fallback (v1 or v2 with no recent trade)
    if prev is None:
        return 0.0
    dvol = int(snap.acml_vol) - int(prev.acml_vol)
    if dvol == 0:
        return 0.0
    mid_now = (float(snap.bid_px[0]) + float(snap.ask_px[0])) / 2.0
    mid_prev = (float(prev.bid_px[0]) + float(prev.ask_px[0])) / 2.0
    if mid_now > mid_prev:
        return float(dvol)
    if mid_now < mid_prev:
        return -float(dvol)
    return 0.0


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


# ---------------------------------------------------------------------------
# Block E (2026-04-26) — Direct trade-event primitives (tickdata_krx v2 only)
#
# These primitives use the new feed's pre-classified trade events
# (askbid_type, trading_volume, transaction_power) instead of inferring
# trade direction via Lee-Ready tick rule. They produce 0.0 on v1 CSV data
# (askbid_type defaults to 0 in Snap dataclass), so existing v1-era specs
# remain backwards-compatible.
# ---------------------------------------------------------------------------


def lee_ready_proper(snap: Any) -> float:
    """Direct Lee-Ready signed volume (no tick-rule estimation needed).

    Uses the most recent trade event's askbid_type (1=buy, 2=sell) attached
    to this quote tick by the v2 loader's merge_asof.

    Returns: signed trade volume in shares
      > 0  → most recent trade was buyer-initiated
      < 0  → most recent trade was seller-initiated
      = 0  → no recent trade within tolerance window

    Differs from `trade_imbalance_signed`: that primitive uses Lee-Ready tick
    rule (mid-direction) as a proxy. This uses the exchange's direct
    classification — strictly more accurate when the v2 feed is in use.

    Direction: Category A at moderate magnitude; Category B2 (exhaustion)
    when extreme via z-score.
    Reference: Lee-Ready (1991) §IV — direct quote-rule classification.
    """
    if snap.askbid_type == 1:
        return float(snap.trade_volume)
    if snap.askbid_type == 2:
        return -float(snap.trade_volume)
    return 0.0


def transaction_power_signal(snap: Any) -> float:
    """KIS-derived transaction power, centered at 0.

    transaction_power > 100 = buyer-pressure dominant
    transaction_power < 100 = seller-pressure dominant
    Returns (raw - 100) so positive = buy-pressure, negative = sell-pressure.

    Direction: Category A (pressure proxy).
    """
    if snap.transaction_power == 0.0:
        return 0.0
    return float(snap.transaction_power) - 100.0


def aggressive_buy_indicator(snap: Any) -> float:
    """Binary buy-pressure indicator from most recent trade.

    Returns 1.0 if last trade was buy-initiated, -1.0 if sell, 0.0 if none.
    Use with rolling_mean for smoothed buy-vs-sell ratio:
      rolling_mean(aggressive_buy_indicator, 100)  → recent buy fraction

    Direction: Category A.
    """
    if snap.askbid_type == 1:
        return 1.0
    if snap.askbid_type == 2:
        return -1.0
    return 0.0


def trade_price_dev_bps(snap: Any) -> float:
    """Last trade price deviation from current mid (bps).

    > 0 → last trade hit the ask side (buy pressure)
    < 0 → last trade hit the bid side (sell pressure)
    Equivalent to a per-trade microstructure pressure signal that doesn't
    require state.

    Direction: Category A. Use raw threshold like 1.0 bps for trigger.
    Reference: Hasbrouck (1991) §III on permanent vs transient impact.
    """
    if snap.last_trade_price <= 0:
        return 0.0
    mid = (float(snap.bid_px[0]) + float(snap.ask_px[0])) / 2.0
    if mid <= 0:
        return 0.0
    return (float(snap.last_trade_price) - mid) / mid * 1e4


def vpin_proxy_per_tick(snap: Any) -> float:
    """Per-tick VPIN ingredient: |signed_trade_vol| / total_trade_vol.

    Returns 0 if no recent trade. When non-zero:
      ~ 1.0 → fully one-sided (extreme toxicity)
      ~ 0   → balanced (uninformed flow)
    Use with rolling_mean for smoothed VPIN approximation:
      rolling_mean(vpin_proxy_per_tick, 50)  → ~ Easley-LdP-O'Hara VPIN

    Direction: Category C (regime/state filter). High VPIN = avoid entry
    against informed flow.
    Reference: Easley, López de Prado, O'Hara (2012).
    """
    if snap.askbid_type == 0 or snap.trade_volume == 0:
        return 0.0
    # Per single trade event, ratio is always 1 (it's all buy or all sell).
    # The per-tick value is binary, but rolling_mean over many ticks gives
    # the proper toxicity statistic.
    return 1.0


def queue_imbalance_best(snap: Any) -> float:
    """Gould-Bonart (2016) queue imbalance at the BBO.

    Formula: B_1 / (B_1 + A_1)        ∈ [0, 1]
    Linearly equivalent to obi_1 (= 2·QI − 1) but with a probabilistic
    interpretation: under the Gould-Bonart conditional model, QI ≈ P(next
    mid move is upward | current state). Useful when an LLM wants to use
    a probability-style threshold (e.g., QI > 0.7) instead of a [-1,1]
    imbalance threshold.

    Direction semantics: Category A (pressure/flow). high QI → up.
    """
    b = float(snap.bid_qty[0])
    a = float(snap.ask_qty[0])
    return b / (b + a + EPS)


def microprice_velocity(snap: Any, prev: Any | None) -> float:
    """Stoikov-style fair-value drift rate (bps per tick).

    Δmicroprice / mid_t × 1e4   over the last tick.
    Positive = microprice moving up (bid-pressure increasing); negative = down.

    Captures the speed at which fair value is shifting — large |velocity|
    is an adverse-selection signal (informed flow arriving) per Glosten-
    Milgrom (1985) and Stoikov (2018) §3.4.

    Direction semantics: Category A at moderate magnitude (signal direction);
    Category B2 (exhaustion) at extreme |velocity| > 2σ.
    """
    if prev is None:
        return 0.0
    mp_now = microprice(snap)
    mp_prev = microprice(prev)
    if mp_prev <= 0:
        return 0.0
    return (mp_now - mp_prev) / mp_prev * 1e4


def spread_change_bps(snap: Any, prev: Any | None) -> float:
    """Δspread (bps) over the last tick. Signed: positive = widening.

    A sudden widening signals adverse selection arriving (Glosten-Milgrom
    1985); gradual widening reflects inventory pressure (Avellaneda-Stoikov
    2008). Sustained narrowing follows informed-flow exhaustion.

    Direction semantics: Category C (regime/state indicator). Best used
    as a filter, e.g., `spread_change_bps > 1.0` excludes adverse-arrival
    moments.
    """
    if prev is None:
        return 0.0
    return spread_bps(snap) - spread_bps(prev)


def book_imbalance_velocity(snap: Any, prev: Any | None) -> float:
    """Δobi_1 over the last tick. Speed of imbalance shift.

    Large positive → bid side accumulating fast; large negative → bid being
    consumed or ask side stacking. Captures HF micro-momentum (Cartea-
    Jaimungal 2015 §HF momentum).

    Direction semantics: Category A (pressure-derivative). Sign and magnitude
    both informative.
    """
    if prev is None:
        return 0.0
    return obi_1(snap) - obi_1(prev)


def signed_volume_cumulative(snap: Any, prev: Any | None) -> float:
    """Per-tick signed trade volume (Lee-Ready tick rule).

    Naming clarification: this is the same quantity as
    `trade_imbalance_signed` (= sign(Δmid) · ΔACML_VOL) but provided under
    the name used by Hasbrouck (1991) and Lee-Ready (1991). Use this name
    when invoking the rolling-sum helper to compute Hasbrouck's cumulative
    signed flow over a window:
        rolling_mean(signed_volume_cumulative, 50)  # smoothed signed flow
        rolling_sum(signed_volume_cumulative, 100)   # cumulative signed flow

    Direction semantics: Category A (raw flow), B2 (extreme z-scored).
    """
    return trade_imbalance_signed(snap, prev)


def book_pressure_asymmetry(snap: Any) -> float:
    """Book-wide directional pressure using raw totals (not ICDC).

    Formula: (total_bid_qty − total_ask_qty) / (total_bid_qty + total_ask_qty)
    Range [-1, 1].

    Distinct from `obi_total` which uses TOTAL_*_RSQN_ICDC (KIS-published
    increments). This primitive uses TOTAL_*_RSQN scalars directly — full
    snapshot of book-wide depth, less sensitive to ICDC publication latency.

    Direction semantics: Category A (pressure).
    Reference: Cont-Kukanov-Stoikov (2014) §6 layer aggregation.
    """
    b = float(snap.total_bid_qty)
    a = float(snap.total_ask_qty)
    return (b - a) / (b + a + EPS)


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
class RollingRangeBps:
    """Parkinson-style high-low range in bps over a rolling window.

    Stores last `window` values of a primitive (typically `mid_px`); returns
    `1e4 * (max - min) / max(|mean|, EPS)` in bps. Captures realized magnitude
    directly — orthogonal to realized volatility (which is RMS of diffs) and
    more sensitive to tail moves. Use as `rolling_range_bps(mid_px, 200)` to
    identify high-magnitude windows for gating entries.

    Reference: Parkinson 1980, Garman-Klass 1980 — high-low range estimators.
    """

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        if len(self._buf) < 2:
            return 0.0
        arr = np.asarray(self._buf, dtype=np.float64)
        hi = float(arr.max())
        lo = float(arr.min())
        denom = max(abs(float(arr.mean())), EPS)
        return 1.0e4 * (hi - lo) / denom


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
class RollingMax:
    """Maximum of last `window` values. Useful for `recent_high` references."""

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        return float(max(self._buf))


@dataclass
class RollingMin:
    """Minimum of last `window` values. Useful for `recent_low` references."""

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        return float(min(self._buf))


@dataclass
class RollingSum:
    """Cumulative sum over a rolling window of `window` values.

    Use case: cumulative signed trade flow per Hasbrouck (1991) §IV.
        rolling_sum(signed_volume_cumulative, 100)  → 10-second flow
    """

    window: int
    _buf: deque = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=self.window)

    def update(self, x: float) -> float:
        self._buf.append(float(x))
        return float(sum(self._buf))


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
    # --- Block D (2026-04-25): paper-grounded velocity / probability / cumulative primitives ---
    "queue_imbalance_best":    {"fn": queue_imbalance_best,    "stateful": False, "bounded": (0.0, 1.0), "ref": "microstructure_advanced#queue_imbalance"},
    "microprice_velocity":     {"fn": microprice_velocity,     "stateful": True,  "bounded": None,       "ref": "microstructure_advanced#velocity"},
    "spread_change_bps":       {"fn": spread_change_bps,       "stateful": True,  "bounded": None,       "ref": "microstructure_advanced#spread_dynamics"},
    "book_imbalance_velocity": {"fn": book_imbalance_velocity, "stateful": True,  "bounded": (-2.0, 2.0),"ref": "microstructure_advanced#velocity"},
    "signed_volume_cumulative":{"fn": signed_volume_cumulative,"stateful": True,  "bounded": None,       "ref": "microstructure_advanced#trade_flow"},
    "book_pressure_asymmetry": {"fn": book_pressure_asymmetry, "stateful": False, "bounded": (-1.0, 1.0),"ref": "microstructure_advanced#book_shape"},
    # --- Block E (2026-04-26): direct trade-event primitives (tickdata_krx v2) ---
    "lee_ready_proper":         {"fn": lee_ready_proper,         "stateful": False, "bounded": None,        "ref": "microstructure_advanced#trade_events"},
    "transaction_power_signal": {"fn": transaction_power_signal, "stateful": False, "bounded": None,        "ref": "microstructure_advanced#trade_events"},
    "aggressive_buy_indicator": {"fn": aggressive_buy_indicator, "stateful": False, "bounded": (-1.0, 1.0), "ref": "microstructure_advanced#trade_events"},
    "trade_price_dev_bps":      {"fn": trade_price_dev_bps,      "stateful": False, "bounded": None,        "ref": "microstructure_advanced#trade_events"},
    "vpin_proxy_per_tick":      {"fn": vpin_proxy_per_tick,      "stateful": False, "bounded": (0.0, 1.0),  "ref": "microstructure_advanced#vpin"},
    # --- Block F (2026-04-27): time-of-day regime gates for magnitude concentration ---
    "is_opening_burst":         {"fn": is_opening_burst,         "stateful": False, "bounded": (0.0, 1.0),  "ref": "time_of_day_regimes#opening"},
    "is_lunch_lull":            {"fn": is_lunch_lull,            "stateful": False, "bounded": (0.0, 1.0),  "ref": "time_of_day_regimes#lunch"},
    "is_closing_burst":         {"fn": is_closing_burst,         "stateful": False, "bounded": (0.0, 1.0),  "ref": "time_of_day_regimes#closing"},
}


def is_primitive(name: str) -> bool:
    return name in PRIMITIVE_WHITELIST


__all__ = list(PRIMITIVE_WHITELIST.keys()) + [
    "RollingMean", "RollingStd", "RollingZScore",
    "RollingRealizedVol", "RollingMomentum", "RollingPriceImpact", "RollingArrivalRate",
    "RollingMax", "RollingMin", "RollingSum", "RollingRangeBps",
    "PRIMITIVE_WHITELIST", "is_primitive",
]
