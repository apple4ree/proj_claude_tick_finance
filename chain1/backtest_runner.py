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


# ---------------------------------------------------------------------------
# Data loading (KRX H0STASP0 CSV)
# ---------------------------------------------------------------------------


def load_day(symbol: str, date: str) -> pd.DataFrame:
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
    ts = pd.to_datetime(df["recv_ts_kst"], utc=False).astype("int64").to_numpy()
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
) -> PerSymbolResult:
    """Run one (symbol, date). `trace_records` (if provided) gets per-trade rows appended.

    If `horizon_grid` is provided, metrics are computed in one pass for every
    horizon in the grid ∪ {spec.prediction_horizon_ticks}. The PerSymbolResult's
    primary fields (wr/expectancy_bps/...) correspond to the spec's primary
    horizon; other horizons land in `horizon_curve`.

    To keep trade counts comparable across horizons, entries are restricted to
    ticks where `i + max(all_horizons) < n_ticks`.
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


def run_backtest(
    spec: SignalSpec,
    code: GeneratedCode,
    symbols: list[str],
    dates: list[str],
    save_trace: bool = False,
    trace_path: str | None = None,
    horizon_grid: tuple[int, ...] | None = None,
) -> BacktestResult:
    """Full backtest for one SignalSpec across (symbols × dates).

    If `horizon_grid` is provided, per-symbol and aggregate horizon_curve
    are populated in a single pass (no extra backtest runs needed).
    Primary (aggregate_wr/aggregate_expectancy_bps) reflects the spec's
    primary horizon — backward compatible.
    """
    signal_fn = load_signal_fn(code.code_path, code.entry_function)

    per_symbol: list[PerSymbolResult] = []
    trace_records: list[dict] | None = [] if save_trace else None

    for sym in symbols:
        for dte in dates:
            res = backtest_symbol_date(
                signal_fn, spec, sym, dte, trace_records,
                horizon_grid=horizon_grid,
            )
            per_symbol.append(res)

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
