"""BTCUSDT 168h mean-reversion strategy.

Alpha: roc_168h (168-bar rate-of-change of close price) <= roc_168h_threshold
Entry: MARKET BUY at bar close when roc_168h <= threshold and flat
Exit (whichever fires first):
  1. Profit target  — close >= entry_price * (1 + pt_bps / 1e4)
  2. Stop loss      — close <= entry_price * (1 - sl_bps / 1e4)
  3. Trailing stop  — after gain >= trailing_activation_bps, drop from peak
                      >= trailing_distance_bps triggers MARKET SELL
  4. Time stop      — held for time_stop_ticks bars without other exit

Implements BOTH:
  - on_tick(snap, ctx) → engine.simulator tick-level interface
  - generate_signal(df, **params) → intraday_full_artifacts.py bar interface

The generate_signal interface is the primary execution path for 1h bar data.
The on_tick interface is included for engine compatibility; it produces 0
events when the tick engine finds no data for crypto dates (as expected).
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

from engine.data_loader import OrderBookSnapshot
from engine.simulator import BUY, MARKET, SELL, Context, Order

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PENDING_TICKS = 10   # bar-level: assume rejection after 10 bars

_KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# bar-level interface (used by intraday_full_artifacts.py)
# ---------------------------------------------------------------------------


def generate_signal(df: pd.DataFrame, **params) -> pd.Series:
    """Generate +1 / 0 signal for the 168h mean-reversion strategy.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV bar dataframe with at minimum a ``close`` column.
    **params : extracted from spec.yaml[params]
        roc_168h_threshold, profit_target_bps, stop_loss_bps,
        trailing_stop, trailing_activation_bps, trailing_distance_bps,
        max_entries_per_session, lot_size, (optional) time_stop_ticks

    Returns
    -------
    pd.Series
        Integer series in {+1, 0}: +1 = hold long, 0 = flat.
        Aligned to ``df.index``.
    """
    roc_threshold = float(params.get("roc_168h_threshold", -0.056226))
    pt_bps = float(params.get("profit_target_bps", 1312.07))
    sl_bps = float(params.get("stop_loss_bps", 450.79))
    trailing = bool(params.get("trailing_stop", True))
    trail_act_bps = float(params.get("trailing_activation_bps", 600.0))
    trail_dist_bps = float(params.get("trailing_distance_bps", 300.0))
    max_entries = int(params.get("max_entries_per_session", 1))
    time_stop = int(params.get("time_stop_ticks", 168))

    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    signal = np.zeros(n, dtype=int)
    exit_tags: list[str] = [""] * n  # per-bar exit-reason; "" when no exit

    roc_168 = np.full(n, np.nan)
    for i in range(168, n):
        if close[i - 168] > 0:
            roc_168[i] = close[i] / close[i - 168] - 1.0

    # State
    in_position = False
    entry_price = 0.0
    peak_price = 0.0
    trailing_armed = False
    bars_held = 0
    entries_today = 0
    prev_date: str = ""

    for i in range(n):
        # Detect date boundary for session reset
        if hasattr(df, "iloc"):
            ts = df.index[i] if isinstance(df.index[0], pd.Timestamp) else None
            ot = df["open_time"].iloc[i] if "open_time" in df.columns else None
        else:
            ot = None
        if ot is not None:
            if isinstance(ot, pd.Timestamp):
                date_str = ot.strftime("%Y-%m-%d")
            else:
                date_str = str(ot)[:10]
            if date_str != prev_date:
                prev_date = date_str
                entries_today = 0

        px = close[i]

        if in_position:
            bars_held += 1
            # Update peak
            if px > peak_price:
                peak_price = px

            gain_bps = (px - entry_price) / entry_price * 1e4
            loss_bps = (entry_price - px) / entry_price * 1e4

            # Arm trailing stop once gain reaches activation threshold
            if trailing and gain_bps >= trail_act_bps:
                trailing_armed = True

            exit_now = False
            exit_reason = ""

            # 1. Profit target
            if gain_bps >= pt_bps:
                exit_now = True
                exit_reason = "pt_hit"

            # 2. Stop loss
            elif loss_bps >= sl_bps:
                exit_now = True
                exit_reason = "sl_hit"

            else:
                # 3. Trailing stop (only after armed) — independent of time stop
                if trailing_armed:
                    drop_bps = (peak_price - px) / peak_price * 1e4 if peak_price > 0 else 0.0
                    if drop_bps >= trail_dist_bps:
                        exit_now = True
                        exit_reason = "trailing_stop"

                # 4. Time stop — always checked independently; overrides hanging trailing
                if not exit_now and time_stop > 0 and bars_held >= time_stop:
                    exit_now = True
                    exit_reason = "time_stop"

            if exit_now:
                in_position = False
                trailing_armed = False
                bars_held = 0
                signal[i] = 0
                exit_tags[i] = exit_reason
            else:
                signal[i] = 1

        else:
            # Entry: need 168 bars of history, roc signal fires, session limit
            if (i >= 168
                    and not np.isnan(roc_168[i])
                    and roc_168[i] <= roc_threshold
                    and entries_today < max_entries):
                in_position = True
                entry_price = px
                peak_price = px
                trailing_armed = False
                bars_held = 0
                entries_today += 1
                signal[i] = 1
            else:
                signal[i] = 0

    signal_series = pd.Series(signal, index=df.index, dtype=int)
    exit_tag_series = pd.Series(exit_tags, index=df.index, dtype=object)
    # Returning a tuple is the new (2026-04-19) bar-runner contract; downstream
    # generate_fills uses exit_tag_series to label SELL fills with the actual
    # exit reason (pt_hit / sl_hit / trailing_stop / time_stop) rather than the
    # opaque legacy "exit_signal".
    return signal_series, exit_tag_series


# ---------------------------------------------------------------------------
# tick-level interface (used by engine.runner / Backtester)
# ---------------------------------------------------------------------------

class Strategy:
    """BTCUSDT 168h mean-reversion — tick-engine interface.

    When the tick engine iterates over crypto dates, it finds no per-date
    CSV files in the KRX directory structure, so on_tick is never called and
    total_events = 0. This is expected behaviour for this strategy.

    The generate_signal() function above is the primary execution path.
    """

    def __init__(self, spec: dict) -> None:
        p = spec.get("params") or {}
        # --- tunable params ---
        self.roc_threshold = float(p.get("roc_168h_threshold", -0.056226))
        self.lot_size = int(p.get("lot_size", 1))
        self.max_entries = int(p.get("max_entries_per_session", 1))
        self.pt_bps = float(p.get("profit_target_bps", 1312.07))
        self.sl_bps = float(p.get("stop_loss_bps", 450.79))
        self.trailing_stop = bool(p.get("trailing_stop", True))
        self.trail_act_bps = float(p.get("trailing_activation_bps", 600.0))
        self.trail_dist_bps = float(p.get("trailing_distance_bps", 300.0))
        self.time_stop_ticks = int(p.get("time_stop_ticks", 168))

        # --- internal state (per symbol) ---
        self._close_history: dict[str, deque] = {}
        self._tick_count: dict[str, int] = {}
        self._entries_today: dict[str, int] = {}
        self._last_date: dict[str, str] = {}

        # Position tracking
        self._entry_price: dict[str, float] = {}
        self._peak_price: dict[str, float] = {}
        self._trailing_armed: dict[str, bool] = {}
        self._bars_held: dict[str, int] = {}

        # Latency guard
        self._pending_buy: dict[str, int] = {}   # sym → tick when submitted
        self._pending_sell: dict[str, int] = {}  # sym → tick when submitted

    def _history(self, sym: str) -> deque:
        if sym not in self._close_history:
            self._close_history[sym] = deque(maxlen=169)
        return self._close_history[sym]

    def on_tick(self, snap: OrderBookSnapshot, ctx: Context) -> list[Order]:
        sym = snap.symbol
        # Derive approximate close price from mid (ask+bid)/2
        mid = (float(snap.ask_px[0]) + float(snap.bid_px[0])) / 2.0
        if mid <= 0:
            return []

        tc = self._tick_count.get(sym, 0) + 1
        self._tick_count[sym] = tc

        # Session date reset
        date_str = datetime.fromtimestamp(snap.ts_ns / 1e9, tz=_KST).strftime("%Y%m%d")
        if self._last_date.get(sym) != date_str:
            self._last_date[sym] = date_str
            self._entries_today[sym] = 0

        hist = self._history(sym)
        hist.append(mid)

        pos = ctx.portfolio.positions.get(sym)
        pos_qty = pos.qty if pos else 0

        # ------------------------------------------------------------------ #
        # LATENCY GUARD — resolve pending states
        # ------------------------------------------------------------------ #
        if pos_qty > 0 and sym in self._pending_buy:
            del self._pending_buy[sym]
            # Entry confirmed — initialise exit tracking
            if sym not in self._entry_price:
                self._entry_price[sym] = mid
                self._peak_price[sym] = mid
                self._trailing_armed[sym] = False
                self._bars_held[sym] = 0

        if pos_qty == 0 and sym in self._pending_sell:
            del self._pending_sell[sym]
            # Exit confirmed — reset state
            self._entry_price.pop(sym, None)
            self._peak_price.pop(sym, None)
            self._trailing_armed.pop(sym, None)
            self._bars_held.pop(sym, None)

        # Timeout stale pending orders (assumed rejected)
        if sym in self._pending_buy and tc - self._pending_buy[sym] >= _MAX_PENDING_TICKS:
            del self._pending_buy[sym]
            self._entry_price.pop(sym, None)
            self._peak_price.pop(sym, None)
            self._trailing_armed.pop(sym, None)
            self._bars_held.pop(sym, None)

        if sym in self._pending_sell and tc - self._pending_sell[sym] >= _MAX_PENDING_TICKS:
            del self._pending_sell[sym]

        # Block all new orders while any order is in flight
        if sym in self._pending_buy or sym in self._pending_sell:
            # Still update peak while blocked
            if pos_qty > 0 and sym in self._peak_price:
                if mid > self._peak_price[sym]:
                    self._peak_price[sym] = mid
            return []

        # ------------------------------------------------------------------ #
        # HOLDING: exit logic
        # ------------------------------------------------------------------ #
        if pos_qty > 0:
            entry_px = self._entry_price.get(sym, mid)
            peak_px = self._peak_price.get(sym, mid)

            # Update peak
            if mid > peak_px:
                self._peak_price[sym] = mid
                peak_px = mid

            # Increment bars held
            bars_held = self._bars_held.get(sym, 0) + 1
            self._bars_held[sym] = bars_held

            gain_bps = (mid - entry_px) / entry_px * 1e4 if entry_px > 0 else 0.0
            loss_bps = (entry_px - mid) / entry_px * 1e4 if entry_px > 0 else 0.0

            # Arm trailing stop
            if self.trailing_stop and gain_bps >= self.trail_act_bps:
                self._trailing_armed[sym] = True

            exit_tag: str | None = None

            # 1. Profit target
            if gain_bps >= self.pt_bps:
                exit_tag = "profit_target"

            # 2. Stop loss
            elif loss_bps >= self.sl_bps:
                exit_tag = "stop_loss"

            else:
                # 3. Trailing stop (only when armed) — independent of time stop
                if self._trailing_armed.get(sym, False):
                    drop_bps = (peak_px - mid) / peak_px * 1e4 if peak_px > 0 else 0.0
                    if drop_bps >= self.trail_dist_bps:
                        exit_tag = "trailing_stop"

                # 4. Time stop — always checked independently; overrides hanging trailing
                if exit_tag is None and self.time_stop_ticks > 0 and bars_held >= self.time_stop_ticks:
                    exit_tag = "time_stop"

            if exit_tag is not None:
                self._pending_sell[sym] = tc
                return [Order(sym, SELL, qty=pos_qty, order_type=MARKET, tag=exit_tag)]

            return []

        # ------------------------------------------------------------------ #
        # FLAT: entry logic
        # ------------------------------------------------------------------ #

        # Entry gate: need 168 bars of history
        if len(hist) < 169:
            return []

        # Session entry limit
        if self._entries_today.get(sym, 0) >= self.max_entries:
            return []

        # Compute 168-bar ROC
        old_price = hist[0]
        if old_price <= 0:
            return []

        roc = (mid - old_price) / old_price

        if roc <= self.roc_threshold:
            self._pending_buy[sym] = tc
            self._entry_price[sym] = mid
            self._peak_price[sym] = mid
            self._trailing_armed[sym] = False
            self._bars_held[sym] = 0
            self._entries_today[sym] = self._entries_today.get(sym, 0) + 1
            return [Order(sym, BUY, qty=self.lot_size, order_type=MARKET, tag="entry_roc168")]

        return []
