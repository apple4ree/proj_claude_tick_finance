"""H0STASP0 tick data loader.

Reads KIS realtime 10-level order book CSVs and yields normalized
OrderBookSnapshot objects. Multi-symbol chronological merging is supported
for portfolio backtests.

CLI exists so agents can inspect data without pulling rows into context.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import pandas as pd

DATA_ROOT = Path("/home/dgu/tick/open-trading-api/data/realtime/H0STASP0")
CRYPTO_ROOT = Path("/home/dgu/tick/crypto")
N_LEVELS = 10

# Mutable override — set by engine.runner when spec has data_root
_active_root: Path | None = None


def set_data_root(root: Path | str) -> None:
    """Override DATA_ROOT for this process (e.g., crypto data)."""
    global _active_root
    _active_root = Path(root)


def get_data_root() -> Path:
    """Return the currently active data root."""
    return _active_root if _active_root is not None else DATA_ROOT

ASK_PX_COLS = [f"ASKP{i}" for i in range(1, N_LEVELS + 1)]
BID_PX_COLS = [f"BIDP{i}" for i in range(1, N_LEVELS + 1)]
ASK_QTY_COLS = [f"ASKP_RSQN{i}" for i in range(1, N_LEVELS + 1)]
BID_QTY_COLS = [f"BIDP_RSQN{i}" for i in range(1, N_LEVELS + 1)]


@dataclass
class OrderBookSnapshot:
    ts_ns: int
    symbol: str
    ask_px: np.ndarray
    ask_qty: np.ndarray
    bid_px: np.ndarray
    bid_qty: np.ndarray
    total_ask_qty: int
    total_bid_qty: int
    acml_vol: int
    session_cls: str
    antc_px: int
    antc_qty: int

    @property
    def mid(self) -> float:
        return (int(self.ask_px[0]) + int(self.bid_px[0])) / 2.0

    @property
    def spread(self) -> int:
        return int(self.ask_px[0]) - int(self.bid_px[0])


def _csv_path(date: str, symbol: str) -> Path:
    return get_data_root() / date / f"{symbol}.csv"


_STR_COLS = ("MKSC_SHRN_ISCD", "HOUR_CLS_CODE", "tr_id")


def load_csv(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype={c: "string" for c in _STR_COLS},
        low_memory=False,
    )
    df["ts_ns"] = pd.to_datetime(df["recv_ts_kst"], utc=False).astype("int64")
    df["MKSC_SHRN_ISCD"] = df["MKSC_SHRN_ISCD"].str.zfill(6)
    df["HOUR_CLS_CODE"] = df["HOUR_CLS_CODE"].fillna("0").astype("string")
    return df


def df_to_snapshots(df: pd.DataFrame) -> Iterator[OrderBookSnapshot]:
    ask_px = df[ASK_PX_COLS].to_numpy(dtype=np.int64)
    bid_px = df[BID_PX_COLS].to_numpy(dtype=np.int64)
    ask_qty = df[ASK_QTY_COLS].to_numpy(dtype=np.int64)
    bid_qty = df[BID_QTY_COLS].to_numpy(dtype=np.int64)
    ts = df["ts_ns"].to_numpy()
    syms = df["MKSC_SHRN_ISCD"].to_numpy()
    total_a = df["TOTAL_ASKP_RSQN"].to_numpy()
    total_b = df["TOTAL_BIDP_RSQN"].to_numpy()
    acml = df["ACML_VOL"].to_numpy()
    cls = df["HOUR_CLS_CODE"].astype(str).to_numpy()
    apx = df["ANTC_CNPR"].to_numpy()
    aqty = df["ANTC_CNQN"].to_numpy()
    for i in range(len(df)):
        yield OrderBookSnapshot(
            ts_ns=int(ts[i]),
            symbol=str(syms[i]),
            ask_px=ask_px[i],
            ask_qty=ask_qty[i],
            bid_px=bid_px[i],
            bid_qty=bid_qty[i],
            total_ask_qty=int(total_a[i]),
            total_bid_qty=int(total_b[i]),
            acml_vol=int(acml[i]),
            session_cls=str(cls[i]),
            antc_px=int(apx[i]),
            antc_qty=int(aqty[i]),
        )


def load_day(date: str, symbol: str) -> pd.DataFrame:
    return load_csv(_csv_path(date, symbol))


# ---------------------------------------------------------------------------
# Crypto LOB adapter (2026-04-19 Phase X3)
#
# Binance @depth20@100ms parquet archive → OrderBookSnapshot iterator.
# The engine core is int64-based (KRX KRW-denominated legacy); to fit crypto
# float prices (e.g. BTC 75468.85) and float qty (e.g. 1.09043) into that
# contract without rewriting the simulator, we scale by CRYPTO_PRICE_SCALE
# before loading. Return-percentage metrics are unit-invariant under this
# scaling, so downstream Sharpe / return_pct / IR numbers are preserved.
# ---------------------------------------------------------------------------

CRYPTO_LOB_ROOT = Path("data/binance_lob")
CRYPTO_PRICE_SCALE = 10 ** 8   # 8-decimal precision (satoshi-equivalent)
CRYPTO_LEVELS = 10             # engine assumes 10 levels (KRX N_LEVELS)


def _crypto_scale_int(a: np.ndarray) -> np.ndarray:
    """Multiply float array by CRYPTO_PRICE_SCALE and cast to int64."""
    return (a.astype(np.float64) * CRYPTO_PRICE_SCALE).astype(np.int64)


def iter_events_crypto_lob(
    start_ts_ns: int,
    end_ts_ns: int,
    symbols: Iterable[str],
    lob_root: Path | None = None,
) -> Iterator[OrderBookSnapshot]:
    """Stream OrderBookSnapshot rows from Binance LOB parquet archive.

    Data layout: <lob_root>/<SYM>/YYYY-MM-DD/HH.parquet with 20-level
    bid/ask columns. Only the top `CRYPTO_LEVELS` levels are yielded
    (engine assumption). Prices and quantities are scaled into int64
    by CRYPTO_PRICE_SCALE; fee / PnL / return_pct are unit-invariant.

    Args:
        start_ts_ns / end_ts_ns: inclusive/exclusive ns-precision window.
        symbols: Binance tickers, e.g. ["BTCUSDT", "ETHUSDT", "SOLUSDT"].
        lob_root: override the default data/binance_lob root.

    Yields snapshots in ts_ns order across the union of symbols (interleaved).
    """
    root = Path(lob_root) if lob_root else CRYPTO_LOB_ROOT
    if not root.exists():
        return

    # Collect relevant parquet files per symbol, filtered by date range
    start_day = pd.Timestamp(start_ts_ns, unit="ns", tz="UTC").date()
    end_day = pd.Timestamp(end_ts_ns, unit="ns", tz="UTC").date()

    frames: list[pd.DataFrame] = []
    for sym in symbols:
        sym_dir = root / sym.upper()
        if not sym_dir.exists():
            continue
        for day_dir in sorted(sym_dir.iterdir()):
            try:
                d = pd.Timestamp(day_dir.name).date()
            except Exception:
                continue
            if d < start_day or d > end_day:
                continue
            for hour_file in sorted(day_dir.glob("*.parquet")):
                try:
                    import pyarrow.parquet as pq
                    tbl = pq.read_table(hour_file)
                except Exception:
                    continue
                df = tbl.to_pandas()
                df = df[(df["ts_ns"] >= start_ts_ns) & (df["ts_ns"] < end_ts_ns)]
                if df.empty:
                    continue
                df["_symbol"] = sym.upper()
                frames.append(df)

    if not frames:
        return

    all_df = pd.concat(frames, ignore_index=True).sort_values("ts_ns").reset_index(drop=True)

    # Scale float → int64 and pack into OrderBookSnapshot (top CRYPTO_LEVELS)
    ask_px_cols = [f"ask_px_{i}" for i in range(CRYPTO_LEVELS)]
    ask_qty_cols = [f"ask_qty_{i}" for i in range(CRYPTO_LEVELS)]
    bid_px_cols = [f"bid_px_{i}" for i in range(CRYPTO_LEVELS)]
    bid_qty_cols = [f"bid_qty_{i}" for i in range(CRYPTO_LEVELS)]

    ask_px = _crypto_scale_int(all_df[ask_px_cols].to_numpy())
    ask_qty = _crypto_scale_int(all_df[ask_qty_cols].to_numpy())
    bid_px = _crypto_scale_int(all_df[bid_px_cols].to_numpy())
    bid_qty = _crypto_scale_int(all_df[bid_qty_cols].to_numpy())
    ts = all_df["ts_ns"].to_numpy()
    syms = all_df["_symbol"].to_numpy()
    total_a = (all_df["total_ask_qty"].to_numpy() * CRYPTO_PRICE_SCALE).astype(np.int64)
    total_b = (all_df["total_bid_qty"].to_numpy() * CRYPTO_PRICE_SCALE).astype(np.int64)

    for i in range(len(all_df)):
        yield OrderBookSnapshot(
            ts_ns=int(ts[i]),
            symbol=str(syms[i]),
            ask_px=ask_px[i],
            ask_qty=ask_qty[i],
            bid_px=bid_px[i],
            bid_qty=bid_qty[i],
            total_ask_qty=int(total_a[i]),
            total_bid_qty=int(total_b[i]),
            acml_vol=0,              # not tracked by partial-depth stream
            session_cls="0",         # crypto 24/7 — always "regular"
            antc_px=0,               # auction fields don't apply
            antc_qty=0,
        )


def clean_lob_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with structurally invalid order-book state.

    Filters applied (in order):
      1. Positive best prices  — ASKP1 > 0 and BIDP1 > 0
      2. Price inversion       — ASKP1 > BIDP1  (crossed/locked markets are bad data)
      3. Zero top-of-book depth — ASKP_RSQN1 > 0 and BIDP_RSQN1 > 0

    These three checks mirror the cleaning passes in the reference RL-agent
    backtest (cleaning.py) and eliminate rows that would produce nonsensical
    mid prices or mislead the queue-depth model.
    """
    mask = (
        (df["ASKP1"] > 0)
        & (df["BIDP1"] > 0)
        & (df["ASKP1"] > df["BIDP1"])
        & (df["ASKP_RSQN1"] > 0)
        & (df["BIDP_RSQN1"] > 0)
    )
    return df[mask]


def iter_events(
    date: str,
    symbols: Iterable[str],
    regular_only: bool = True,
) -> Iterator[OrderBookSnapshot]:
    frames = []
    for s in symbols:
        p = _csv_path(date, s)
        if not p.exists():
            continue
        df = load_csv(p)
        if regular_only:
            df = df[df["HOUR_CLS_CODE"] == "0"]
        frames.append(df)
    if not frames:
        return
    all_df = pd.concat(frames, ignore_index=True)
    all_df.sort_values("ts_ns", kind="mergesort", inplace=True)
    all_df = clean_lob_df(all_df)
    yield from df_to_snapshots(all_df)


def summarize(date: str, symbol: str) -> dict:
    df = load_day(date, symbol)
    return {
        "date": date,
        "symbol": symbol,
        "rows": int(len(df)),
        "ts_range_kst": [
            str(df["recv_ts_kst"].iloc[0]),
            str(df["recv_ts_kst"].iloc[-1]),
        ],
        "regular_rows": int((df["HOUR_CLS_CODE"] == "0").sum()),
        "unique_session_codes": sorted(df["HOUR_CLS_CODE"].astype(str).unique().tolist()),
        "first_best_ask": int(df["ASKP1"].iloc[0]),
        "first_best_bid": int(df["BIDP1"].iloc[0]),
        "acml_vol_last": int(df["ACML_VOL"].iloc[-1]),
    }


def list_symbols(date: str) -> list[str]:
    d = get_data_root() / date
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.csv"))


def list_dates() -> list[str]:
    root = get_data_root()
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def main() -> None:
    ap = argparse.ArgumentParser(description="H0STASP0 tick data loader")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("summary", help="single-file summary as JSON")
    s1.add_argument("--date", required=True)
    s1.add_argument("--symbol", required=True)

    s2 = sub.add_parser("list-symbols", help="list symbols for a date")
    s2.add_argument("--date", required=True)

    sub.add_parser("list-dates", help="list available dates")

    s4 = sub.add_parser("iter-check", help="dry-run multi-symbol iterator")
    s4.add_argument("--date", required=True)
    s4.add_argument("--symbols", nargs="+", required=True)

    args = ap.parse_args()
    if args.cmd == "summary":
        print(json.dumps(summarize(args.date, args.symbol), ensure_ascii=False))
    elif args.cmd == "list-symbols":
        print(json.dumps(list_symbols(args.date)))
    elif args.cmd == "list-dates":
        print(json.dumps(list_dates()))
    elif args.cmd == "iter-check":
        n = 0
        last_ts = 0
        ordered = True
        first_ts = None
        last_seen = None
        for ev in iter_events(args.date, args.symbols):
            if first_ts is None:
                first_ts = ev.ts_ns
            if ev.ts_ns < last_ts:
                ordered = False
            last_ts = ev.ts_ns
            last_seen = ev
            n += 1
        out = {"events": n, "chronological": ordered}
        if n > 0:
            out["first_ts_ns"] = first_ts
            out["last_ts_ns"] = last_ts
            out["last_symbol"] = last_seen.symbol
        print(json.dumps(out))


if __name__ == "__main__":
    main()
