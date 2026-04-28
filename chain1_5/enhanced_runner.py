"""Chain 1.5 runner — SignalSpec + ExitPolicy + max_hold_ticks on KRX snapshots.

Pre-fee, mid-to-mid (same simplification as Chain 1). The ONLY extension is
early-exit logic (PT/SL/trailing) and an optional extra regime gate.

Differences from Chain 1 (backtest_runner):
  - Exit is NOT fixed at H ticks; H is upper bound (max_hold_ticks)
  - PT/SL/trailing can close a position early
  - Optional extra regime filter skips entries

Differences from Chain 2 (execution_runner):
  - No fees, no spread, no sell_tax — entry and exit both at mid
  - No order type / maker model — assumes instant fill at mid
  - long_only=False by default (signal-agnostic); Chain 2 will add market realism

This layer exists to optimize exit policy WITHOUT confounding it with
execution-layer costs.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import (  # noqa: E402
    SignalSpec,
    EnhancedSignalSpec,
    ExitPolicy,
    ExitTrailingMode,
    GeneratedCode,
    Direction,
)

from chain1.backtest_runner import load_day, iter_snaps, load_signal_fn, Snap  # reuse


@dataclass
class EnhancedResult:
    """Pre-fee Chain 1.5 measurement per (signal × exit policy) combination."""
    spec_id: str
    base_signal_spec_id: str
    per_symbol_date: list[dict]
    aggregate_n_trades: int
    aggregate_wr: float
    aggregate_expectancy_bps: float
    aggregate_avg_hold_ticks: float
    exit_reason_dist: dict[str, int]          # {"pt":N, "sl":N, "trail":N, "time":N}
    per_trade_traces: list[dict]              # optional, if save_trace=True


def _evaluate_gate(gate_expr: str | None, snap_i: int, mid: np.ndarray) -> bool:
    """Evaluate an optional extra regime gate per tick. Currently supports a
    minimal DSL; extend as needed. Returns True if gate passes (allow entry).

    Recognized forms (case-sensitive, no whitespace inside operators):
        "rolling_realized_vol(mid_px, W) < X"
        "rolling_realized_vol(mid_px, W) > X"

    TODO: full expression evaluation via AST + primitive dispatch.
    """
    if gate_expr is None:
        return True
    # Minimal: always allow. Advanced parsing deferred — see TODO.
    # For now, Phase 1 uses extra_regime_gate = None and relies on
    # SignalSpec.formula's own gate (e.g., iter013 already has low_vol filter).
    return True


def run_enhanced_backtest(
    base_signal_spec: SignalSpec,
    base_code: GeneratedCode,
    enh_spec: EnhancedSignalSpec,
    symbols: list[str],
    dates: list[str],
    save_trace: bool = False,
) -> EnhancedResult:
    """Run Chain 1.5 backtest (mid-to-mid + exit policy) over (symbols × dates)."""
    signal_fn = load_signal_fn(base_code.code_path, base_code.entry_function)

    all_n_trades = 0
    all_n_wins = 0
    all_n_losses = 0
    sum_signed_bps = 0.0
    sum_hold_ticks = 0
    exit_reasons = {"pt": 0, "sl": 0, "trail": 0, "time": 0, "zero_move": 0}
    per_sd: list[dict] = []
    trace_rows: list[dict] = []

    threshold = base_signal_spec.threshold
    direction_mode = base_signal_spec.direction
    max_H = enh_spec.max_hold_ticks
    pt = enh_spec.exit_policy.pt_bps
    sl = enh_spec.exit_policy.sl_bps
    trail_on = enh_spec.exit_policy.trailing_mode == ExitTrailingMode.FIXED_BPS
    trail_dist = enh_spec.exit_policy.trailing_distance_bps

    for sym in symbols:
        for dte in dates:
            try:
                df = load_day(sym, dte)
            except FileNotFoundError:
                continue
            n_ticks = len(df)
            if n_ticks == 0:
                continue
            mid = (df["BIDP1"].to_numpy(dtype=np.float64) + df["ASKP1"].to_numpy(dtype=np.float64)) / 2.0

            sd_n_trades = 0
            sd_n_wins = 0
            sd_n_losses = 0
            sd_sum_signed = 0.0
            sd_sum_hold = 0

            prev_snap = None
            i = 0
            all_snaps_iter = iter(iter_snaps(df))
            snaps: list[Snap] = []
            for s in all_snaps_iter:
                setattr(s, "prev", prev_snap)
                prev_snap = s
                snaps.append(s)

            # IMPORTANT: signal_fn relies on module-level stateful helpers
            # (zscore, rolling_mean, ...). These require EVERY tick's signal
            # to be evaluated so rolling windows build correctly. If we
            # naively skip ticks while a position is open, rolling state goes
            # stale and signal values corrupt.
            #
            # Fix: evaluate signal_fn on every tick to keep state current,
            # but GATE new-position openings so we only open one at a time.
            open_until_tick = -1   # index through which we must not open new

            while i < n_ticks:
                if i + max_H >= n_ticks:
                    break
                snap_i = snaps[i]

                # Always evaluate signal to keep rolling helpers fresh.
                try:
                    s = float(signal_fn(snap_i))
                except Exception as e:  # noqa: BLE001
                    raise RuntimeError(f"signal() fail {sym} {dte} tick {i}: {e}") from e

                # Skip entry if still holding a position
                if i <= open_until_tick:
                    i += 1
                    continue

                # Extra regime gate (Phase 1: stub, always True)
                if not _evaluate_gate(enh_spec.extra_regime_gate, i, mid):
                    i += 1
                    continue

                if abs(s) <= threshold:
                    i += 1
                    continue

                if direction_mode == Direction.LONG_IF_POS:
                    predicted = +1 if s > threshold else -1
                else:
                    predicted = -1 if s > threshold else +1

                mid_entry = mid[i]
                max_pnl_bps = 0.0
                exit_reason = "time"
                exit_signed = 0.0
                ticks_held = 0

                # Walk forward up to max_H, applying early-exit checks
                for k in range(1, max_H + 1):
                    if i + k >= n_ticks:
                        break
                    unrealized = (mid[i + k] - mid_entry) / mid_entry * 1e4 * predicted
                    if unrealized > max_pnl_bps:
                        max_pnl_bps = unrealized

                    # PT check
                    if pt > 0 and unrealized >= pt:
                        exit_reason = "pt"
                        exit_signed = unrealized
                        ticks_held = k
                        break
                    # SL check
                    if sl > 0 and unrealized <= -sl:
                        exit_reason = "sl"
                        exit_signed = unrealized
                        ticks_held = k
                        break
                    # Trailing check
                    if trail_on and trail_dist > 0 and max_pnl_bps - unrealized >= trail_dist:
                        exit_reason = "trail"
                        exit_signed = unrealized
                        ticks_held = k
                        break

                # If no early exit triggered: close at max_H
                if ticks_held == 0:
                    ticks_held = max_H
                    if i + max_H < n_ticks:
                        exit_signed = (mid[i + max_H] - mid_entry) / mid_entry * 1e4 * predicted
                    else:
                        exit_signed = 0.0

                # Chain 1 convention: zero-move is NOT counted in n_trades or WR.
                # This keeps Chain 1.5 numbers comparable to Chain 1's measurement.
                if exit_signed == 0.0 and exit_reason == "time":
                    exit_reasons["zero_move"] += 1
                    # Block next entries for the same hold period (we've
                    # "held" this non-trade), but don't count it as a trade.
                    open_until_tick = i + ticks_held - 1
                    i += 1
                    continue

                exit_reasons[exit_reason] += 1

                sd_n_trades += 1
                if exit_signed > 0:
                    sd_n_wins += 1
                elif exit_signed < 0:
                    sd_n_losses += 1
                sd_sum_signed += exit_signed
                sd_sum_hold += ticks_held

                if save_trace:
                    trace_rows.append({
                        "symbol": sym, "date": dte, "entry_tick": i,
                        "predicted_dir": predicted,
                        "ticks_held": ticks_held, "exit_reason": exit_reason,
                        "signed_bps": exit_signed,
                    })

                # Block new entries until this trade closes, but continue
                # tick-by-tick iteration so signal rolling state stays current.
                open_until_tick = i + ticks_held - 1
                i += 1

            wr_sd = sd_n_wins / (sd_n_wins + sd_n_losses) if (sd_n_wins + sd_n_losses) > 0 else 0.5
            exp_sd = sd_sum_signed / sd_n_trades if sd_n_trades > 0 else 0.0
            avg_hold_sd = sd_sum_hold / sd_n_trades if sd_n_trades > 0 else 0.0
            per_sd.append({
                "symbol": sym, "date": dte, "n_ticks": n_ticks,
                "n_trades": sd_n_trades, "n_wins": sd_n_wins, "n_losses": sd_n_losses,
                "wr": wr_sd, "expectancy_bps": exp_sd, "avg_hold_ticks": avg_hold_sd,
            })

            all_n_trades += sd_n_trades
            all_n_wins += sd_n_wins
            all_n_losses += sd_n_losses
            sum_signed_bps += sd_sum_signed
            sum_hold_ticks += sd_sum_hold

    agg_wr = all_n_wins / (all_n_wins + all_n_losses) if (all_n_wins + all_n_losses) > 0 else 0.5
    agg_exp = sum_signed_bps / all_n_trades if all_n_trades > 0 else 0.0
    agg_hold = sum_hold_ticks / all_n_trades if all_n_trades > 0 else 0.0

    return EnhancedResult(
        spec_id=enh_spec.spec_id,
        base_signal_spec_id=enh_spec.base_signal_spec_id,
        per_symbol_date=per_sd,
        aggregate_n_trades=int(all_n_trades),
        aggregate_wr=float(agg_wr),
        aggregate_expectancy_bps=float(agg_exp),
        aggregate_avg_hold_ticks=float(agg_hold),
        exit_reason_dist=exit_reasons,
        per_trade_traces=trace_rows if save_trace else [],
    )
