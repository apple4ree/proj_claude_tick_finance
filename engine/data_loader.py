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
N_LEVELS = 10

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
    return DATA_ROOT / date / f"{symbol}.csv"


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
    d = DATA_ROOT / date
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.csv"))


def list_dates() -> list[str]:
    return sorted(p.name for p in DATA_ROOT.iterdir() if p.is_dir())


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
