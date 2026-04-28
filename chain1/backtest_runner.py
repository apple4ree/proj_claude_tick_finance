"""Chain 1 backtest runner (stage ③).

Deterministic implementation of the execution=1 rule described in
`.claude/agents/chain1/backtest-runner/AGENTS.md` §6 Reasoning Flow.

For each (symbol, date) pair:
  - Iterate over KRX regular-session snapshots in chronological order.
  - Evaluate signal(snap) per tick.
  - If |signal| > THRESHOLD: predict direction per SignalSpec.direction.
  - Look ahead prediction_horizon_ticks to measure mid change.
  - Classify outcome: win / loss / zero (zero excluded from WR).

Produces a BacktestResult Pydantic artifact.

No LLM calls. Pure numpy/pandas.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
KRX_DATA_ROOT = Path("/home/dgu/tick/open-trading-api/data/realtime/H0STASP0")

if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from schemas import (  # noqa: E402
    SignalSpec, GeneratedCode, BacktestResult, PerSymbolResult, HorizonPoint, Direction,
)

DEFAULT_HORIZON_GRID: tuple[int, ...] = (1, 5, 20, 50, 100, 200)

N_LEVELS = 10
ASK_PX_COLS = [f"ASKP{i}" for i in range(1, N_LEVELS + 1)]
BID_PX_COLS = [f"BIDP{i}" for i in range(1, N_LEVELS + 1)]
ASK_QTY_COLS = [f"ASKP_RSQN{i}" for i in range(1, N_LEVELS + 1)]
BID_QTY_COLS = [f"BIDP_RSQN{i}" for i in range(1, N_LEVELS + 1)]


# ---------------------------------------------------------------------------
# Snapshot container (duck-typed; compatible with chain1.primitives)
# ---------------------------------------------------------------------------


@dataclass
class Snap:
    ts_ns: int
    bid_px: np.ndarray
    ask_px: np.ndarray
    bid_qty: np.ndarray
    ask_qty: np.ndarray
    total_bid_qty: int
    total_ask_qty: int
    total_bid_icdc: float
    total_ask_icdc: float
    acml_vol: int
    # Trade-event fields (NEW 2026-04-26 with tickdata_krx v2 loader).
    # 0 / 0.0 defaults preserve backwards compatibility with v1 CSV loader.
    trade_volume: int = 0          # per-tick trade quantity (most recent trade ≤ this tick)
    askbid_type: int = 0           # 1=buy-initiated, 2=sell-initiated, 0=no recent trade
    transaction_power: float = 0.0 # KIS transaction_power; >100=buy-pressure, <100=sell-pressure
    last_trade_price: float = 0.0  # last trade's executed price


# ---------------------------------------------------------------------------
# Data loading (KRX H0STASP0 CSV)
# ---------------------------------------------------------------------------


USE_TICKDATA_V2 = True   # 2026-04-26 default to new tickdata_krx parquet loader


def load_day(symbol: str, date: str) -> pd.DataFrame:
    """Load (symbol, date) ticks. Default v2 (parquet); fallback v1 (CSV).

    v2 schema is legacy-compatible: BIDP1..10/ASKP1..10/RSQN/TOTAL_*/ICDC/ACML_VOL/
    recv_ts_kst, plus NEW trade-event columns (trade_volume, askbid_type,
    transaction_power, last_trade_price).
    """
    if USE_TICKDATA_V2:
        from engine.data_loader_v2 import load_day_v2
        return load_day_v2(symbol, date)
    # Legacy CSV path (open-trading-api/data/realtime/H0STASP0)
    path = KRX_DATA_ROOT / date / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(
        path, low_memory=False,
        dtype={"MKSC_SHRN_ISCD": "string", "HOUR_CLS_CODE": "string"},
    )
    df["HOUR_CLS_CODE"] = df["HOUR_CLS_CODE"].fillna("0").astype("string")
    df = df[df["HOUR_CLS_CODE"] == "0"]
    df = df[(df["BIDP1"] > 0) & (df["ASKP1"] > 0) & (df["ASKP1"] > df["BIDP1"])]
    df = df.reset_index(drop=True)
    return df


def iter_snaps(df: pd.DataFrame) -> Iterable[Snap]:
    bid_px = df[BID_PX_COLS].to_numpy(dtype=np.int64)
    ask_px = df[ASK_PX_COLS].to_numpy(dtype=np.int64)
    bid_qty = df[BID_QTY_COLS].to_numpy(dtype=np.int64)
    ask_qty = df[ASK_QTY_COLS].to_numpy(dtype=np.int64)
    total_b = df["TOTAL_BIDP_RSQN"].to_numpy(dtype=np.int64)
    total_a = df["TOTAL_ASKP_RSQN"].to_numpy(dtype=np.int64)
    total_b_icdc = df["TOTAL_BIDP_RSQN_ICDC"].to_numpy(dtype=np.float64)
    total_a_icdc = df["TOTAL_ASKP_RSQN_ICDC"].to_numpy(dtype=np.float64)
    acml = df["ACML_VOL"].to_numpy(dtype=np.int64)
    # recv_ts_kst is now an int64 (HHMMSSuuuuuu packed) from v2; legacy v1 used datetime string.
    ts_raw = df["recv_ts_kst"]
    if pd.api.types.is_integer_dtype(ts_raw):
        ts = ts_raw.to_numpy(dtype=np.int64)
    else:
        ts = pd.to_datetime(ts_raw, utc=False).astype("int64").to_numpy()
    # Trade-event columns (v2 only; v1 yields zeros via Snap defaults)
    has_trade_cols = "trade_volume" in df.columns
    if has_trade_cols:
        trade_vol = df["trade_volume"].to_numpy(dtype=np.int64)
        askbid    = df["askbid_type"].to_numpy(dtype=np.int64)
        tx_power  = df["transaction_power"].to_numpy(dtype=np.float64)
        last_trd  = df["last_trade_price"].to_numpy(dtype=np.float64)
    else:
        trade_vol = np.zeros(len(df), dtype=np.int64)
        askbid    = np.zeros(len(df), dtype=np.int64)
        tx_power  = np.zeros(len(df), dtype=np.float64)
        last_trd  = np.zeros(len(df), dtype=np.float64)
    for i in range(len(df)):
        yield Snap(
            ts_ns=int(ts[i]),
            bid_px=bid_px[i], ask_px=ask_px[i],
            bid_qty=bid_qty[i], ask_qty=ask_qty[i],
            total_bid_qty=int(total_b[i]),
            total_ask_qty=int(total_a[i]),
            total_bid_icdc=float(total_b_icdc[i]),
            total_ask_icdc=float(total_a_icdc[i]),
            acml_vol=int(acml[i]),
            trade_volume=int(trade_vol[i]),
            askbid_type=int(askbid[i]),
            transaction_power=float(tx_power[i]),
            last_trade_price=float(last_trd[i]),
        )


# ---------------------------------------------------------------------------
# Dynamic load of generated signal code
# ---------------------------------------------------------------------------


def load_signal_fn(code_path: str, entry_function: str = "signal") -> Callable:
    p = Path(code_path)
    if not p.exists():
        raise FileNotFoundError(p)
    spec = importlib.util.spec_from_file_location(f"signal_mod_{p.stem}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, entry_function):
        raise AttributeError(f"{code_path}: no `{entry_function}()` function")
    return getattr(mod, entry_function)


# ---------------------------------------------------------------------------
# Core per-symbol backtest under execution=1
# ---------------------------------------------------------------------------


def backtest_symbol_date(
    signal_fn: Callable,
    spec: SignalSpec,
    symbol: str,
    date: str,
    trace_records: list[dict] | None = None,
    horizon_grid: tuple[int, ...] | None = None,
    calibration_table: dict | None = None,
) -> PerSymbolResult:
    """Run one (symbol, date). `trace_records` (if provided) gets per-trade rows appended.

    If `horizon_grid` is provided, metrics are computed in one pass for every
    horizon in the grid ∪ {spec.prediction_horizon_ticks}. The PerSymbolResult's
    primary fields (wr/expectancy_bps/...) correspond to the spec's primary
    horizon; other horizons land in `horizon_curve`.

    To keep trade counts comparable across horizons, entries are restricted to
    ticks where `i + max(all_horizons) < n_ticks`.

    If `calibration_table` is provided AND the spec uses exactly one primitive
    that has calibration entries, signal value is z-score normalized using
    per-symbol stats. spec.threshold is then interpreted in z-score units.
    Calibration applies to the FINAL signal value (after formula evaluation),
    treating the formula output as a single primitive's effective value.
    """
    df = load_day(symbol, date)
    n_ticks = len(df)
    if n_ticks == 0:
        return PerSymbolResult(
            symbol=symbol, date=date, n_ticks=0, n_trades=0, n_wins=0, n_losses=0,
            wr=0.5, sum_win_bps=0.0, sum_loss_bps=0.0, expectancy_bps=0.0,
            horizon_curve=[],
        )

    # Pre-compute mid series for horizon lookahead
    mid = (df["BIDP1"].to_numpy(dtype=np.float64) + df["ASKP1"].to_numpy(dtype=np.float64)) / 2.0

    primary_H = spec.prediction_horizon_ticks
    threshold = spec.threshold
    direction = spec.direction

    if horizon_grid is None:
        all_horizons: tuple[int, ...] = (primary_H,)
    else:
        all_horizons = tuple(sorted(set(horizon_grid) | {primary_H}))
    max_H = max(all_horizons)

    # Per-horizon accumulators
    stats = {h: {"n_trades": 0, "n_wins": 0, "n_losses": 0,
                  "sum_win": 0.0, "sum_loss": 0.0} for h in all_horizons}

    # Per-symbol calibration setup (D1, 2026-04-25)
    # Active only when calibration_table provided AND spec uses single primitive
    # AND that primitive has a calibration entry for this symbol.
    calib_active = False
    calib_mean = 0.0
    calib_std = 1.0
    if calibration_table is not None:
        prims = list(spec.primitives_used)
        if len(prims) == 1:
            sym_stats = calibration_table.get("stats", {}).get(symbol, {}).get(prims[0])
            if sym_stats is not None and sym_stats.get("std", 0) > 1e-12:
                calib_active = True
                calib_mean = float(sym_stats["mean"])
                calib_std = float(sym_stats["std"])

    prev_snap: Snap | None = None

    # Use `setattr` to bolt prev into each snap for stateful primitives that
    # want 1-tick history via snap._prev (optional signal convention).
    for i, snap in enumerate(iter_snaps(df)):
        # Expose prev via a dunder-free attribute `prev` for stateful primitives
        setattr(snap, "prev", prev_snap)
        prev_snap = snap

        if i + max_H >= n_ticks:
            break  # no horizon available for the longest target

        # Evaluate signal
        try:
            s = float(signal_fn(snap))
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"signal() failed at {symbol} {date} tick {i}: {e}") from e

        # Per-symbol calibration (z-score normalization) — D1
        # Threshold is then interpreted as z-score units.
        if calib_active:
            s = (s - calib_mean) / calib_std

        # Decision rule under execution=1
        if abs(s) <= threshold:
            continue

        # Decode predicted direction
        if direction == Direction.LONG_IF_POS:
            predicted = +1 if s > threshold else -1
        else:  # LONG_IF_NEG
            predicted = -1 if s > threshold else +1

        mid_t = mid[i]

        # Evaluate outcome at each horizon in the grid
        for H in all_horizons:
            mid_th = mid[i + H]
            delta_bps = (mid_th - mid_t) / mid_t * 1e4
            if delta_bps == 0.0:
                continue  # zero-change: not counted in WR (per-horizon)
            signed = delta_bps * predicted
            st = stats[H]
            st["n_trades"] += 1
            if signed > 0:
                st["n_wins"] += 1
                st["sum_win"] += signed
            else:
                st["n_losses"] += 1
                st["sum_loss"] += abs(signed)

        # Trace records (kept at primary horizon only, unchanged schema)
        if trace_records is not None:
            mid_th_p = mid[i + primary_H]
            delta_bps_p = (mid_th_p - mid_t) / mid_t * 1e4
            signed_p = delta_bps_p * predicted
            if delta_bps_p != 0.0:
                trace_records.append({
                    "symbol": symbol, "date": date, "tick_idx": i,
                    "ts_ns": snap.ts_ns, "signal_value": s,
                    "predicted_dir": predicted, "delta_bps": delta_bps_p,
                    "signed_bps": signed_p, "mid_t": mid_t, "mid_th": mid_th_p,
                })

    # Build horizon_curve
    horizon_curve: list[HorizonPoint] = []
    for H in all_horizons:
        st = stats[H]
        n = st["n_trades"]
        denom = st["n_wins"] + st["n_losses"]
        wr = st["n_wins"] / denom if denom > 0 else 0.5
        exp = (st["sum_win"] - st["sum_loss"]) / n if n > 0 else 0.0
        horizon_curve.append(HorizonPoint(
            horizon=int(H),
            n_trades=int(n),
            n_wins=int(st["n_wins"]),
            n_losses=int(st["n_losses"]),
            wr=float(wr),
            sum_win_bps=float(st["sum_win"]),
            sum_loss_bps=float(st["sum_loss"]),
            expectancy_bps=float(exp),
        ))

    # Primary (spec.prediction_horizon_ticks) fields for backward compatibility
    p = stats[primary_H]
    p_denom = p["n_wins"] + p["n_losses"]
    p_wr = p["n_wins"] / p_denom if p_denom > 0 else 0.5
    p_exp = (p["sum_win"] - p["sum_loss"]) / p["n_trades"] if p["n_trades"] > 0 else 0.0

    return PerSymbolResult(
        symbol=symbol, date=date, n_ticks=n_ticks,
        n_trades=int(p["n_trades"]),
        n_wins=int(p["n_wins"]),
        n_losses=int(p["n_losses"]),
        wr=float(p_wr),
        sum_win_bps=float(p["sum_win"]),
        sum_loss_bps=float(p["sum_loss"]),
        expectancy_bps=float(p_exp),
        horizon_curve=horizon_curve if horizon_grid is not None else [],
    )


def backtest_symbol_date_regime(
    signal_fn: Callable,
    spec: SignalSpec,
    symbol: str,
    date: str,
    trace_records: list[dict] | None = None,
    calibration_table: dict | None = None,
    execution_mode: str = "mid_to_mid",
) -> PerSymbolResult:
    """Regime-state backtest for one (symbol, date). New paradigm 2026-04-27.

    State machine:
        FLAT  + signal=True   →  ENTER  at mid[i]
        LONG  + signal=True   →  HOLD
        LONG  + signal=False  →  EXIT   at mid[i]
        FLAT  + signal=False  →  STAY FLAT

    End-of-session: force-close any open position.

    Direction:
        long_if_pos: predicted = +1 (long entry)
        long_if_neg: predicted = -1 (short entry — but execution=1 still treats
                                    as price-direction bet)

    Per-trade gross_bps = (mid_exit - mid_entry) / mid_entry * 1e4 * predicted

    Returns PerSymbolResult populated with both legacy fields (for backward
    compat: n_trades = n_regimes, wr = fraction of regimes positive,
    expectancy_bps = mean per-regime gross) and new regime-state fields.
    """
    df = load_day(symbol, date)
    n_ticks = len(df)
    if n_ticks == 0:
        return PerSymbolResult(
            symbol=symbol, date=date, n_ticks=0, n_trades=0, n_wins=0, n_losses=0,
            wr=0.5, sum_win_bps=0.0, sum_loss_bps=0.0, expectancy_bps=0.0,
            horizon_curve=[],
            n_regimes=0, signal_duty_cycle=0.0, mean_duration_ticks=0.0,
            execution_mode=execution_mode,
        )

    bid1 = df["BIDP1"].to_numpy(dtype=np.float64)
    ask1 = df["ASKP1"].to_numpy(dtype=np.float64)
    mid = (bid1 + ask1) / 2.0

    threshold = spec.threshold
    direction = spec.direction
    sign = +1 if direction == Direction.LONG_IF_POS else -1

    # Per-symbol calibration (D1)
    calib_active = False
    calib_mean = 0.0
    calib_std = 1.0
    if calibration_table is not None:
        prims = list(spec.primitives_used)
        if len(prims) == 1:
            sym_stats = calibration_table.get("stats", {}).get(symbol, {}).get(prims[0])
            if sym_stats is not None and sym_stats.get("std", 0) > 1e-12:
                calib_active = True
                calib_mean = float(sym_stats["mean"])
                calib_std = float(sym_stats["std"])

    in_position = False
    entry_idx = -1
    entry_mid = 0.0
    n_signal_on = 0  # ticks where signal evaluated True
    regimes: list[dict] = []

    prev_snap: Snap | None = None
    for i, snap in enumerate(iter_snaps(df)):
        setattr(snap, "prev", prev_snap)
        prev_snap = snap

        try:
            s_raw = signal_fn(snap)
            if calib_active:
                s_raw = (s_raw - calib_mean) / calib_std
            # Interpret as state: True/False
            if isinstance(s_raw, (bool,)):
                signal_on = bool(s_raw)
            else:
                signal_on = abs(float(s_raw)) > threshold
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"signal() failed at {symbol} {date} tick {i}: {e}") from e

        if signal_on:
            n_signal_on += 1

        if signal_on and not in_position:
            in_position = True
            entry_idx = i
            entry_mid = mid[i]
            entry_bid = bid1[i]
            entry_ask = ask1[i]
        elif not signal_on and in_position:
            exit_mid = mid[i]
            exit_bid = bid1[i]
            exit_ask = ask1[i]
            gross_bps = (exit_mid - entry_mid) / entry_mid * 1e4 * sign

            # Maker execution gross: long enters at BID + exits at ASK; short reversed.
            # Net effect: realized adds (full_spread_avg) bps over mid_to_mid.
            # KRX RT fee floor stays 23 bps (sell tax mechanical, not affected by
            # maker classification). So net = mid_to_mid + spread - 23.
            if sign == +1:  # long
                # buy at bid, sell at ask
                gross_maker_bps = (exit_ask - entry_bid) / entry_bid * 1e4
            else:  # short
                # sell at ask, buy at bid
                gross_maker_bps = (entry_ask - exit_bid) / entry_ask * 1e4

            spread_entry_bps = (entry_ask - entry_bid) / entry_mid * 1e4
            spread_exit_bps = (exit_ask - exit_bid) / exit_mid * 1e4

            regimes.append({"entry_idx": entry_idx, "exit_idx": i,
                            "duration": i - entry_idx, "gross_bps": gross_bps,
                            "gross_maker_bps": gross_maker_bps,
                            "spread_entry_bps": spread_entry_bps,
                            "spread_exit_bps": spread_exit_bps,
                            "entry_mid": entry_mid, "exit_mid": exit_mid})
            if trace_records is not None:
                trace_records.append({
                    "symbol": symbol, "date": date,
                    "entry_idx": entry_idx, "exit_idx": i,
                    "duration_ticks": i - entry_idx,
                    "entry_mid": entry_mid, "exit_mid": exit_mid,
                    "gross_bps": gross_bps,
                    "gross_maker_bps": gross_maker_bps,
                    "spread_entry_bps": spread_entry_bps,
                    "spread_exit_bps": spread_exit_bps,
                    "predicted_dir": sign,
                })
            in_position = False

    # NO end-of-session force-close (2026-04-27 design choice).
    # If signal remains True until session end, the regime is INCOMPLETE — not
    # counted in n_regimes. This means signal-always-on specs (buy-and-hold
    # artifacts) yield 0 regimes per session, cleanly identifying them.
    n_unclosed = 1 if in_position else 0

    # Aggregates
    n_regimes = len(regimes)
    if n_regimes == 0:
        return PerSymbolResult(
            symbol=symbol, date=date, n_ticks=n_ticks, n_trades=0, n_wins=0, n_losses=0,
            wr=0.5, sum_win_bps=0.0, sum_loss_bps=0.0, expectancy_bps=0.0,
            horizon_curve=[],
            n_regimes=0, signal_duty_cycle=n_signal_on / n_ticks if n_ticks > 0 else 0.0,
            mean_duration_ticks=0.0,
            execution_mode=execution_mode,
        )

    grosses = [r["gross_bps"] for r in regimes]
    grosses_maker = [r["gross_maker_bps"] for r in regimes]
    spreads_entry = [r["spread_entry_bps"] for r in regimes]
    spreads_exit = [r["spread_exit_bps"] for r in regimes]
    durations = [r["duration"] for r in regimes]
    # Match fixed-H convention: zero-movement regimes (gross == 0) are excluded
    # from WR (cannot resolve win/loss) but still counted in n_regimes/expectancy.
    nonzero_g = [g for g in grosses if g != 0.0]
    n_wins = sum(1 for g in nonzero_g if g > 0)
    n_losses = sum(1 for g in nonzero_g if g < 0)
    sum_win = sum(g for g in nonzero_g if g > 0)
    sum_loss = sum(-g for g in nonzero_g if g < 0)
    denom = n_wins + n_losses
    wr = n_wins / denom if denom > 0 else 0.5
    expectancy = sum(grosses) / n_regimes if n_regimes > 0 else 0.0
    expectancy_maker = sum(grosses_maker) / n_regimes if n_regimes > 0 else 0.0
    avg_spread_entry = sum(spreads_entry) / n_regimes
    avg_spread_exit = sum(spreads_exit) / n_regimes

    # If execution_mode == "maker_optimistic", the primary expectancy_bps is the
    # maker-realized one. Otherwise mid_to_mid (legacy).
    if execution_mode == "maker_optimistic":
        primary_expectancy = expectancy_maker
    else:
        primary_expectancy = expectancy

    return PerSymbolResult(
        symbol=symbol, date=date, n_ticks=n_ticks,
        n_trades=int(n_regimes),
        n_wins=int(n_wins),
        n_losses=int(n_losses),
        wr=float(wr),
        sum_win_bps=float(sum_win),
        sum_loss_bps=float(sum_loss),
        expectancy_bps=float(primary_expectancy),
        horizon_curve=[],
        n_regimes=int(n_regimes),
        signal_duty_cycle=float(n_signal_on / n_ticks) if n_ticks > 0 else 0.0,
        mean_duration_ticks=float(sum(durations) / n_regimes) if n_regimes > 0 else 0.0,
        execution_mode=execution_mode,
        expectancy_maker_bps=float(expectancy_maker),
        avg_spread_at_entry_bps=float(avg_spread_entry),
        avg_spread_at_exit_bps=float(avg_spread_exit),
    )


def run_backtest(
    spec: SignalSpec,
    code: GeneratedCode,
    symbols: list[str],
    dates: list[str],
    save_trace: bool = False,
    trace_path: str | None = None,
    horizon_grid: tuple[int, ...] | None = None,
    calibration_table: dict | None = None,
    mode: str = "regime_state",  # 2026-04-27: default switched from "fixed_h" to "regime_state"
    execution_mode: str = "mid_to_mid",  # 2026-04-27 Path B: 'mid_to_mid' | 'maker_optimistic'
) -> BacktestResult:
    """Full backtest for one SignalSpec across (symbols × dates).

    If `horizon_grid` is provided, per-symbol and aggregate horizon_curve
    are populated in a single pass (no extra backtest runs needed).
    Primary (aggregate_wr/aggregate_expectancy_bps) reflects the spec's
    primary horizon — backward compatible.

    If `calibration_table` is provided, per-symbol z-score normalization
    of single-primitive specs is applied (D1, 2026-04-25). The threshold
    in spec is then in z-score units. See chain1/calibration.py.
    """
    signal_fn = load_signal_fn(code.code_path, code.entry_function)

    per_symbol: list[PerSymbolResult] = []
    trace_records: list[dict] | None = [] if save_trace else None

    if mode == "regime_state":
        for sym in symbols:
            for dte in dates:
                res = backtest_symbol_date_regime(
                    signal_fn, spec, sym, dte, trace_records,
                    calibration_table=calibration_table,
                    execution_mode=execution_mode,
                )
                per_symbol.append(res)
    elif mode == "fixed_h":
        for sym in symbols:
            for dte in dates:
                res = backtest_symbol_date(
                    signal_fn, spec, sym, dte, trace_records,
                    horizon_grid=horizon_grid,
                    calibration_table=calibration_table,
                )
                per_symbol.append(res)
    else:
        raise ValueError(f"unknown backtest mode: {mode!r} (expected 'fixed_h' or 'regime_state')")

    agg_trades = sum(r.n_trades for r in per_symbol)
    agg_wins = sum(r.n_wins for r in per_symbol)
    agg_losses = sum(r.n_losses for r in per_symbol)
    agg_wr = agg_wins / (agg_wins + agg_losses) if (agg_wins + agg_losses) > 0 else 0.5
    agg_sum_win = sum(r.sum_win_bps for r in per_symbol)
    agg_sum_loss = sum(r.sum_loss_bps for r in per_symbol)
    agg_exp = (agg_sum_win - agg_sum_loss) / agg_trades if agg_trades > 0 else 0.0

    # Aggregate horizon curve across symbols × dates (if multi-horizon pass)
    agg_curve: list[HorizonPoint] = []
    if horizon_grid is not None and per_symbol and per_symbol[0].horizon_curve:
        agg_map: dict[int, dict[str, float]] = {}
        for r in per_symbol:
            for hp in r.horizon_curve:
                d = agg_map.setdefault(hp.horizon, {
                    "n_trades": 0.0, "n_wins": 0.0, "n_losses": 0.0,
                    "sum_win": 0.0, "sum_loss": 0.0,
                })
                d["n_trades"] += hp.n_trades
                d["n_wins"] += hp.n_wins
                d["n_losses"] += hp.n_losses
                d["sum_win"] += hp.sum_win_bps
                d["sum_loss"] += hp.sum_loss_bps
        for h in sorted(agg_map):
            d = agg_map[h]
            denom = d["n_wins"] + d["n_losses"]
            wr = d["n_wins"] / denom if denom > 0 else 0.5
            n = d["n_trades"]
            exp = (d["sum_win"] - d["sum_loss"]) / n if n > 0 else 0.0
            agg_curve.append(HorizonPoint(
                horizon=int(h),
                n_trades=int(n),
                n_wins=int(d["n_wins"]),
                n_losses=int(d["n_losses"]),
                wr=float(wr),
                sum_win_bps=float(d["sum_win"]),
                sum_loss_bps=float(d["sum_loss"]),
                expectancy_bps=float(exp),
            ))

    trace_out: str | None = None
    if save_trace and trace_records is not None and trace_path:
        Path(trace_path).parent.mkdir(parents=True, exist_ok=True)
        trace_obj = {
            "spec_id": spec.spec_id,
            "iteration_idx": spec.iteration_idx,
            "threshold": float(spec.threshold),
            "direction": spec.direction.value,
            "prediction_horizon_ticks": int(spec.prediction_horizon_ticks),
            "n_records": len(trace_records),
            "records": trace_records,
        }
        # Write JSON (user-requested format: trace.json)
        import json as _json
        with open(trace_path, "w") as f:
            _json.dump(trace_obj, f, indent=None, default=str)
        trace_out = trace_path

    # Regime-state extra aggregates (only meaningful when mode == "regime_state")
    agg_n_regimes: int | None = None
    agg_signal_duty: float | None = None
    agg_mean_dur: float | None = None
    agg_exp_maker: float | None = None
    agg_avg_spread: float | None = None
    if mode == "regime_state":
        agg_n_regimes = sum((r.n_regimes or 0) for r in per_symbol)
        # Tick-weighted duty cycle (sessions weighted by their tick count)
        total_ticks = sum(r.n_ticks for r in per_symbol)
        if total_ticks > 0:
            agg_signal_duty = sum((r.signal_duty_cycle or 0.0) * r.n_ticks
                                  for r in per_symbol) / total_ticks
        # Regime-weighted mean duration
        if agg_n_regimes and agg_n_regimes > 0:
            agg_mean_dur = sum((r.mean_duration_ticks or 0.0) * (r.n_regimes or 0)
                               for r in per_symbol) / agg_n_regimes
            # Maker / spread aggregates (regime-weighted)
            agg_exp_maker = sum((r.expectancy_maker_bps or 0.0) * (r.n_regimes or 0)
                                for r in per_symbol) / agg_n_regimes
            agg_avg_spread = sum(((r.avg_spread_at_entry_bps or 0.0) +
                                  (r.avg_spread_at_exit_bps or 0.0)) / 2.0 *
                                 (r.n_regimes or 0) for r in per_symbol) / agg_n_regimes
        else:
            agg_mean_dur = 0.0

    return BacktestResult(
        agent_name="backtest-runner",
        iteration_idx=spec.iteration_idx,
        spec_id=spec.spec_id,
        per_symbol=per_symbol,
        aggregate_n_trades=int(agg_trades),
        aggregate_wr=float(agg_wr),
        aggregate_expectancy_bps=float(agg_exp),
        trace_path=trace_out,
        horizon_curve=agg_curve,
        backtest_mode=mode,
        aggregate_n_regimes=agg_n_regimes,
        aggregate_signal_duty_cycle=agg_signal_duty,
        aggregate_mean_duration_ticks=agg_mean_dur,
        execution_mode=execution_mode if mode == "regime_state" else None,
        aggregate_expectancy_maker_bps=agg_exp_maker,
        aggregate_avg_spread_bps=agg_avg_spread,
    )


# ---------------------------------------------------------------------------
# CLI (useful for Phase B sanity)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-json", required=True, help="Path to a SignalSpec JSON file")
    ap.add_argument("--code-path", required=True)
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--dates", nargs="+", required=True)
    ap.add_argument("--save-trace", action="store_true")
    ap.add_argument("--trace-path", default=None)
    ap.add_argument("--horizon-grid", type=int, nargs="+", default=None,
                    help="If provided, compute horizon_curve over these horizons in one pass.")
    args = ap.parse_args()

    spec_dict = json.loads(Path(args.spec_json).read_text())
    spec = SignalSpec(**spec_dict)
    code = GeneratedCode(
        agent_name="manual", iteration_idx=spec.iteration_idx,
        spec_id=spec.spec_id, code_path=args.code_path,
        entry_function="signal", template_used="manual",
    )
    hg = tuple(args.horizon_grid) if args.horizon_grid else None
    result = run_backtest(
        spec, code, args.symbols, args.dates,
        save_trace=args.save_trace, trace_path=args.trace_path,
        horizon_grid=hg,
    )
    print(result.model_dump_json(indent=2))
