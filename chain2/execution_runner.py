"""Chain 2 execution runner (Phase 2.0).

Takes a Chain 1 SignalSpec (entry trigger, fixed) + ExecutionSpec (order type,
PT/SL/time_stop, fees) and runs a per-tick simulation on KRX LOB snapshots.

Differences from Chain 1 backtest_runner:
  - Entry is a *position open* event (MARKET cross OR LIMIT post simulation).
  - Exit is dynamic: PT / SL / trailing / time_stop whichever triggers first,
    always via MARKET cross in Phase 2.0.
  - Fees (maker/taker) and KRX sell-tax are deducted per round-trip.
  - Adverse-selection cost is recorded separately (signed) as diagnostic.

Engine is intentionally simple (no queue model, no latency) — Phase 2.x may
swap in hftbacktest for the 3 best ExecutionSpecs after Stage A/B.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
KRX_DATA_ROOT = Path("/home/dgu/tick/open-trading-api/data/realtime/H0STASP0")

if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import (  # noqa: E402
    SignalSpec,
    ExecutionSpec,
    OrderType,
    TrailingMode,
    Direction,
    GeneratedCode,
    BacktestResult_v2,
    PerSymbolResult_v2,
    CostBreakdown,
)

from chain2.cost_model import get_fee_config, compute_roundtrip_costs
from chain1.backtest_runner import load_day, iter_snaps, load_signal_fn, Snap  # reuse


# ---------------------------------------------------------------------------
# Internal state for one open position
# ---------------------------------------------------------------------------


@dataclass
class _Position:
    """One open round-trip being tracked through ticks."""
    entry_tick_idx: int
    entry_time_ns: int
    entry_price: float           # fill price in KRW
    entry_mid: float             # mid at entry
    direction: int               # +1 long, -1 short
    entry_is_maker: bool
    entry_spread_bps: float      # half-spread crossed at entry (0 if maker)
    max_pnl_bps: float = 0.0     # for trailing
    ticks_held: int = 0
    # adverse_sel_1tick will be recorded separately


# ---------------------------------------------------------------------------
# Entry decision
# ---------------------------------------------------------------------------


def _signal_triggers_entry(signal_value: float, spec: SignalSpec) -> int | None:
    """Return +1 (long), -1 (short), or None (no entry)."""
    thr = spec.threshold
    if abs(signal_value) <= thr:
        return None
    if spec.direction == Direction.LONG_IF_POS:
        return +1 if signal_value > thr else -1
    else:
        return -1 if signal_value > thr else +1


# ---------------------------------------------------------------------------
# Maker fill simulation (Phase 2.0 simplified)
# ---------------------------------------------------------------------------


def _attempt_maker_fill(
    i: int,
    direction: int,
    snaps_future: list[Snap],
    ask_px_i: float,
    bid_px_i: float,
    maker_fill_rate: float,
    ttl_ticks: int,
) -> tuple[bool, int, float, float] | None:
    """Simulate a LIMIT order posted at BBO on tick `i` and see whether it fills
    within `ttl_ticks`.

    Returns (filled, fill_tick_idx, fill_price, entry_mid) or None if not filled.
    Fill criterion (simplified): on a subsequent tick, the opposite side crosses
    our posted price. Apply `maker_fill_rate` as a bernoulli trial at the first
    crossing to reflect queue position.

    Caller passes future snapshots (`snaps_future`) up to `ttl_ticks` ahead.
    """
    if direction == +1:
        # Long entry: post at bid. Fill when ask drops to <= our bid.
        post_price = bid_px_i
        for k, snap_k in enumerate(snaps_future[:ttl_ticks], start=1):
            if snap_k.ask_px[0] <= post_price:
                # Queue position model: bernoulli with maker_fill_rate
                if np.random.random() < maker_fill_rate:
                    fill_mid = (snap_k.bid_px[0] + snap_k.ask_px[0]) / 2.0
                    return True, i + k, float(post_price), float(fill_mid)
                else:
                    return None
        return None
    else:
        # Short entry: post at ask. Fill when bid rises to >= our ask.
        post_price = ask_px_i
        for k, snap_k in enumerate(snaps_future[:ttl_ticks], start=1):
            if snap_k.bid_px[0] >= post_price:
                if np.random.random() < maker_fill_rate:
                    fill_mid = (snap_k.bid_px[0] + snap_k.ask_px[0]) / 2.0
                    return True, i + k, float(post_price), float(fill_mid)
                else:
                    return None
        return None


# ---------------------------------------------------------------------------
# Core backtest for one (symbol, date) with full ExecutionSpec
# ---------------------------------------------------------------------------


def backtest_symbol_date_v2(
    signal_fn: Callable,
    signal_spec: SignalSpec,
    exec_spec: ExecutionSpec,
    symbol: str,
    date: str,
    trace_records: list[dict] | None = None,
    rng_seed: int | None = None,
) -> PerSymbolResult_v2:
    """Chain 2 per-(symbol, date) runner.

    Uses `signal_fn(snap)` to decide entries, applies ExecutionSpec to decide
    entry price, exit conditions, and costs. Produces PerSymbolResult_v2 with
    aggregated cost breakdown.
    """
    if rng_seed is not None:
        np.random.seed(rng_seed)

    df = load_day(symbol, date)
    n_ticks = len(df)
    if n_ticks == 0:
        return PerSymbolResult_v2(
            symbol=symbol, date=date, n_ticks=0, n_trades=0, n_wins=0, n_losses=0,
            wr=0.5, net_pnl_bps_sum=0.0, net_pnl_bps_per_trade=0.0,
            n_maker_fills=0, n_taker_fills=0,
            cost_breakdown=CostBreakdown(
                spread_cost_bps=0.0, maker_fee_cost_bps=0.0, taker_fee_cost_bps=0.0,
                sell_tax_cost_bps=0.0, adverse_selection_cost_bps=0.0, slippage_cost_bps=0.0,
            ),
        )

    mid = (df["BIDP1"].to_numpy(dtype=np.float64) + df["ASKP1"].to_numpy(dtype=np.float64)) / 2.0
    ask_px_arr = df["ASKP1"].to_numpy(dtype=np.float64)
    bid_px_arr = df["BIDP1"].to_numpy(dtype=np.float64)

    fee = get_fee_config(exec_spec.fee_market.value)
    open_pos: _Position | None = None

    # Accumulators
    n_trades = 0
    n_wins = 0
    n_losses = 0
    net_pnl_sum = 0.0                 # signed, bps (already includes all deductions)
    n_maker_fills = 0
    n_taker_fills = 0
    # Cost accumulators (sum of per-trade costs; divided by n_trades at end for avg)
    cost_spread = 0.0
    cost_maker_fee = 0.0
    cost_taker_fee = 0.0
    cost_sell_tax = 0.0
    cost_adverse = 0.0      # signed
    cost_slippage = 0.0

    # Materialize all snaps for random-access future lookup (needed for maker fill sim)
    all_snaps: list[Snap] = []
    prev_snap = None
    for snap in iter_snaps(df):
        setattr(snap, "prev", prev_snap)
        prev_snap = snap
        all_snaps.append(snap)

    i = 0
    while i < n_ticks:
        snap_i = all_snaps[i]

        # --- If a position is open, update it and check exits ---
        if open_pos is not None:
            mid_i = mid[i]
            unrealized_pnl_bps = (mid_i - open_pos.entry_mid) / open_pos.entry_mid * 1e4 * open_pos.direction
            open_pos.ticks_held += 1
            open_pos.max_pnl_bps = max(open_pos.max_pnl_bps, unrealized_pnl_bps)

            exit_triggered = None  # "pt" | "sl" | "time" | "trailing"
            if exec_spec.pt_bps > 0 and unrealized_pnl_bps >= exec_spec.pt_bps:
                exit_triggered = "pt"
            elif exec_spec.sl_bps > 0 and unrealized_pnl_bps <= -exec_spec.sl_bps:
                exit_triggered = "sl"
            elif exec_spec.trailing_mode == TrailingMode.FIXED_BPS \
                    and exec_spec.trailing_distance_bps > 0 \
                    and open_pos.max_pnl_bps - unrealized_pnl_bps >= exec_spec.trailing_distance_bps:
                exit_triggered = "trailing"
            elif open_pos.ticks_held >= exec_spec.time_stop_ticks:
                exit_triggered = "time"

            if exit_triggered is not None:
                # Exit at MARKET: long sells at bid_px, short buys at ask_px
                if open_pos.direction == +1:
                    exit_price = bid_px_arr[i]
                    exit_spread_bps = (ask_px_arr[i] - bid_px_arr[i]) / 2.0 / mid_i * 1e4
                else:
                    exit_price = ask_px_arr[i]
                    exit_spread_bps = (ask_px_arr[i] - bid_px_arr[i]) / 2.0 / mid_i * 1e4

                # Raw realized PnL (bps) — based on fill prices (includes half-spread reality)
                # Signed PnL in bps:
                raw_pnl_bps = (exit_price - open_pos.entry_price) / open_pos.entry_price * 1e4 * open_pos.direction

                # Costs (bps)
                exit_is_maker = False  # Phase 2.0: exits are MARKET
                cb = compute_roundtrip_costs(
                    fee=fee,
                    entry_is_maker=open_pos.entry_is_maker,
                    exit_is_maker=exit_is_maker,
                    entry_spread_bps=open_pos.entry_spread_bps,
                    exit_spread_bps=0.0,  # ⚠️ exit_spread already baked into exit_price; do NOT double-count
                    position_is_long=(open_pos.direction == +1),
                    slippage_bps=0.0,
                )
                # NOTE on spread accounting:
                #  - entry_spread_bps was extra cost we paid vs mid at entry (already NOT in entry_price
                #    if maker; IS in entry_price if taker). To keep raw_pnl_bps fair and spread-neutral,
                #    we use mid-to-mid PnL plus explicit spread_cost deduction. Let's switch to that.
                # Recompute raw_pnl on MID basis (cleaner, matches Chain 1 formula):
                raw_pnl_bps_mid = (mid_i - open_pos.entry_mid) / open_pos.entry_mid * 1e4 * open_pos.direction
                # Then add the explicit spread costs (entry + exit) as deductions
                # which cb["spread_cost_bps"] already has. So use raw_pnl_bps_mid below.

                fee_deductions = (
                    cb["maker_fee_cost_bps"]
                    + cb["taker_fee_cost_bps"]
                    + cb["sell_tax_cost_bps"]
                    + cb["slippage_cost_bps"]
                )
                spread_deduction = cb["spread_cost_bps"]
                # For exit side, add this tick's half-spread as a taker cost (since exit is MARKET)
                spread_deduction_exit = exit_spread_bps
                total_spread_deduction = spread_deduction + spread_deduction_exit

                net_pnl_bps = raw_pnl_bps_mid - total_spread_deduction - fee_deductions

                # Adverse selection: mid move against us 1 tick after fill
                adv_bps = 0.0
                if open_pos.entry_tick_idx + 1 < n_ticks:
                    mid_post = mid[open_pos.entry_tick_idx + 1]
                    adv_bps = -(mid_post - open_pos.entry_mid) / open_pos.entry_mid * 1e4 * open_pos.direction

                # Record
                n_trades += 1
                if net_pnl_bps > 0:
                    n_wins += 1
                else:
                    n_losses += 1
                net_pnl_sum += net_pnl_bps
                cost_spread += total_spread_deduction
                cost_maker_fee += cb["maker_fee_cost_bps"]
                cost_taker_fee += cb["taker_fee_cost_bps"]
                cost_sell_tax += cb["sell_tax_cost_bps"]
                cost_adverse += adv_bps
                cost_slippage += cb["slippage_cost_bps"]
                if open_pos.entry_is_maker:
                    n_maker_fills += 1
                else:
                    n_taker_fills += 1

                if trace_records is not None:
                    trace_records.append({
                        "symbol": symbol, "date": date,
                        "entry_tick_idx": open_pos.entry_tick_idx,
                        "exit_tick_idx": i,
                        "direction": open_pos.direction,
                        "entry_mid": open_pos.entry_mid,
                        "entry_price": open_pos.entry_price,
                        "exit_price": exit_price,
                        "mid_exit": mid_i,
                        "raw_pnl_bps_mid": raw_pnl_bps_mid,
                        "net_pnl_bps": net_pnl_bps,
                        "exit_reason": exit_triggered,
                        "ticks_held": open_pos.ticks_held,
                        "entry_is_maker": open_pos.entry_is_maker,
                        "cb_spread": total_spread_deduction,
                        "cb_fee_total": fee_deductions,
                        "cb_adv_signed": adv_bps,
                    })

                open_pos = None
                # fall through to possibly trigger a new entry this same tick

        # --- If no position is open, check for entry ---
        if open_pos is None:
            try:
                s = float(signal_fn(snap_i))
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"signal() failed at {symbol} {date} tick {i}: {e}") from e

            predicted = _signal_triggers_entry(s, signal_spec)
            # Realistic market constraint: on long-only markets (KRX cash equity
            # without 대차거래), we cannot enter a short position — we don't
            # have inventory to sell. Skip short-signal triggers entirely.
            if predicted is not None and exec_spec.long_only and predicted == -1:
                predicted = None
            if predicted is not None:
                mid_i = mid[i]
                if exec_spec.order_type == OrderType.MARKET:
                    # Taker: buy at ask (long) or sell at bid (short)
                    if predicted == +1:
                        entry_price = ask_px_arr[i]
                    else:
                        entry_price = bid_px_arr[i]
                    entry_half_spread_bps = (ask_px_arr[i] - bid_px_arr[i]) / 2.0 / mid_i * 1e4
                    open_pos = _Position(
                        entry_tick_idx=i,
                        entry_time_ns=snap_i.ts_ns,
                        entry_price=float(entry_price),
                        entry_mid=float(mid_i),
                        direction=predicted,
                        entry_is_maker=False,
                        entry_spread_bps=float(entry_half_spread_bps),
                    )
                elif exec_spec.order_type in (OrderType.LIMIT_AT_BID, OrderType.LIMIT_AT_ASK):
                    # Simulate maker fill
                    future = all_snaps[i + 1 : i + 1 + exec_spec.entry_ttl_ticks]
                    result = _attempt_maker_fill(
                        i=i,
                        direction=predicted,
                        snaps_future=future,
                        ask_px_i=float(ask_px_arr[i]),
                        bid_px_i=float(bid_px_arr[i]),
                        maker_fill_rate=exec_spec.maker_fill_rate,
                        ttl_ticks=exec_spec.entry_ttl_ticks,
                    )
                    if result is not None:
                        filled, fill_idx, fill_price, fill_mid = result
                        open_pos = _Position(
                            entry_tick_idx=fill_idx,
                            entry_time_ns=all_snaps[fill_idx].ts_ns,
                            entry_price=float(fill_price),
                            entry_mid=float(fill_mid),
                            direction=predicted,
                            entry_is_maker=True,
                            entry_spread_bps=0.0,  # maker saves half-spread
                        )
                        # Skip ahead to fill tick so we don't re-trigger signals in between
                        i = fill_idx
                else:
                    raise NotImplementedError(f"order_type {exec_spec.order_type} not implemented in Phase 2.0")

        i += 1

    # --- End of day: close any lingering position at MARKET ---
    if open_pos is not None and n_ticks > 0:
        i_close = n_ticks - 1
        mid_close = mid[i_close]
        if open_pos.direction == +1:
            exit_price = bid_px_arr[i_close]
        else:
            exit_price = ask_px_arr[i_close]
        exit_spread_bps = (ask_px_arr[i_close] - bid_px_arr[i_close]) / 2.0 / mid_close * 1e4
        raw_pnl_bps_mid = (mid_close - open_pos.entry_mid) / open_pos.entry_mid * 1e4 * open_pos.direction
        cb = compute_roundtrip_costs(
            fee=fee,
            entry_is_maker=open_pos.entry_is_maker,
            exit_is_maker=False,
            entry_spread_bps=open_pos.entry_spread_bps,
            exit_spread_bps=0.0,
            position_is_long=(open_pos.direction == +1),
        )
        fee_deductions = (
            cb["maker_fee_cost_bps"] + cb["taker_fee_cost_bps"]
            + cb["sell_tax_cost_bps"] + cb["slippage_cost_bps"]
        )
        total_spread_deduction = cb["spread_cost_bps"] + exit_spread_bps
        net_pnl_bps = raw_pnl_bps_mid - total_spread_deduction - fee_deductions
        n_trades += 1
        if net_pnl_bps > 0: n_wins += 1
        else: n_losses += 1
        net_pnl_sum += net_pnl_bps
        cost_spread += total_spread_deduction
        cost_maker_fee += cb["maker_fee_cost_bps"]
        cost_taker_fee += cb["taker_fee_cost_bps"]
        cost_sell_tax += cb["sell_tax_cost_bps"]
        cost_slippage += cb["slippage_cost_bps"]
        if open_pos.entry_is_maker: n_maker_fills += 1
        else: n_taker_fills += 1

    wr = n_wins / (n_wins + n_losses) if (n_wins + n_losses) > 0 else 0.5
    net_pnl_per_trade = net_pnl_sum / n_trades if n_trades > 0 else 0.0

    def _avg(x: float) -> float:
        return x / n_trades if n_trades > 0 else 0.0

    cb_result = CostBreakdown(
        spread_cost_bps=_avg(cost_spread),
        maker_fee_cost_bps=_avg(cost_maker_fee),
        taker_fee_cost_bps=_avg(cost_taker_fee),
        sell_tax_cost_bps=_avg(cost_sell_tax),
        adverse_selection_cost_bps=_avg(cost_adverse),
        slippage_cost_bps=_avg(cost_slippage),
    )

    return PerSymbolResult_v2(
        symbol=symbol, date=date, n_ticks=n_ticks,
        n_trades=n_trades, n_wins=n_wins, n_losses=n_losses,
        wr=float(wr),
        net_pnl_bps_sum=float(net_pnl_sum),
        net_pnl_bps_per_trade=float(net_pnl_per_trade),
        n_maker_fills=int(n_maker_fills),
        n_taker_fills=int(n_taker_fills),
        cost_breakdown=cb_result,
    )


# ---------------------------------------------------------------------------
# Aggregated runner
# ---------------------------------------------------------------------------


def run_execution_backtest(
    signal_spec: SignalSpec,
    code: GeneratedCode,
    exec_spec: ExecutionSpec,
    symbols: list[str],
    dates: list[str],
    rng_seed: int | None = 42,
) -> BacktestResult_v2:
    """Run Chain 2 backtest for one (SignalSpec, ExecutionSpec) across (symbols × dates)."""
    signal_fn = load_signal_fn(code.code_path, code.entry_function)

    per_symbol: list[PerSymbolResult_v2] = []
    trace_records: list[dict] = []

    for sym in symbols:
        for dte in dates:
            try:
                r = backtest_symbol_date_v2(
                    signal_fn, signal_spec, exec_spec, sym, dte,
                    trace_records=trace_records, rng_seed=rng_seed,
                )
                per_symbol.append(r)
            except FileNotFoundError:
                # Missing data for this (sym, date) — skip silently
                continue

    # Aggregate
    agg_trades = sum(r.n_trades for r in per_symbol)
    agg_wins = sum(r.n_wins for r in per_symbol)
    agg_losses = sum(r.n_losses for r in per_symbol)
    agg_wr = agg_wins / (agg_wins + agg_losses) if (agg_wins + agg_losses) > 0 else 0.5
    agg_net_sum = sum(r.net_pnl_bps_sum for r in per_symbol)
    agg_net_per_trade = agg_net_sum / agg_trades if agg_trades > 0 else 0.0

    # Weighted-avg cost breakdown (per-trade)
    def wavg(field: str) -> float:
        total = 0.0
        for r in per_symbol:
            total += getattr(r.cost_breakdown, field) * r.n_trades
        return total / agg_trades if agg_trades > 0 else 0.0

    agg_cb = CostBreakdown(
        spread_cost_bps=wavg("spread_cost_bps"),
        maker_fee_cost_bps=wavg("maker_fee_cost_bps"),
        taker_fee_cost_bps=wavg("taker_fee_cost_bps"),
        sell_tax_cost_bps=wavg("sell_tax_cost_bps"),
        adverse_selection_cost_bps=wavg("adverse_selection_cost_bps"),
        slippage_cost_bps=wavg("slippage_cost_bps"),
    )

    # Sharpe / MDD — simplified (Phase 2.0): use trade-level distribution
    pnl_series = np.array([t["net_pnl_bps"] for t in trace_records]) if trace_records else np.array([])
    if len(pnl_series) > 1 and float(pnl_series.std()) > 0:
        sharpe = float(pnl_series.mean()) / float(pnl_series.std()) * np.sqrt(250)  # annualized approx
    else:
        sharpe = 0.0
    if len(pnl_series) > 0:
        equity = np.cumsum(pnl_series)
        running_max = np.maximum.accumulate(equity)
        drawdown = running_max - equity
        mdd = float(drawdown.max()) if len(drawdown) > 0 else 0.0
    else:
        mdd = 0.0

    n_maker = sum(r.n_maker_fills for r in per_symbol)
    n_taker = sum(r.n_taker_fills for r in per_symbol)

    return BacktestResult_v2(
        agent_name="chain2.execution_runner",
        iteration_idx=exec_spec.iteration_idx,
        spec_id=exec_spec.spec_id,
        signal_spec_id=signal_spec.spec_id,
        execution_spec_id=exec_spec.spec_id,
        per_symbol=per_symbol,
        aggregate_n_trades=int(agg_trades),
        aggregate_wr=float(agg_wr),
        aggregate_net_pnl_bps_per_trade=float(agg_net_per_trade),
        aggregate_sharpe=float(sharpe),
        aggregate_max_drawdown_bps=float(mdd),
        n_fills=int(agg_trades),
        n_maker_fills=int(n_maker),
        n_taker_fills=int(n_taker),
        cost_breakdown=agg_cb,
    )


if __name__ == "__main__":
    print("Chain 2 execution_runner — import `run_execution_backtest` for programmatic use.")
