"""KRX H0STASP0 → hftbacktest event stream adapter.

KRX KIS realtime CSV (~100ms periodic snapshots, 10 levels bid/ask) is converted
into hftbacktest's event-stream format via DiffOrderBookSnapshot: consecutive
snapshots are differenced so that only changed/inserted/deleted levels produce
DEPTH_EVENTs.

ACML_VOL deltas between snapshots are synthesized into TRADE_EVENTs (crude
approximation — KIS H0STCNT0 trade TR would give proper trade stream).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from hftbacktest.data import correct_local_timestamp, correct_event_order
from hftbacktest.data.utils.difforderbooksnapshot import (
    DiffOrderBookSnapshot,
    CHANGED,
    INSERTED,
    IN_THE_BOOK_DELETION,
)
from hftbacktest.types import (
    event_dtype,
    DEPTH_EVENT,
    TRADE_EVENT,
    BUY_EVENT,
    SELL_EVENT,
)

KRX_DATA_ROOT = Path("/home/dgu/tick/open-trading-api/data/realtime/H0STASP0")
N_LEVELS = 10
ASK_PX_COLS = [f"ASKP{i}" for i in range(1, N_LEVELS + 1)]
BID_PX_COLS = [f"BIDP{i}" for i in range(1, N_LEVELS + 1)]
ASK_QTY_COLS = [f"ASKP_RSQN{i}" for i in range(1, N_LEVELS + 1)]
BID_QTY_COLS = [f"BIDP_RSQN{i}" for i in range(1, N_LEVELS + 1)]


def krx_tick_size(price: float) -> float:
    """KRX cash equity tick size (gradational). 2026 standard rules."""
    if price < 2_000:     return 1.0
    if price < 5_000:     return 5.0
    if price < 20_000:    return 10.0
    if price < 50_000:    return 50.0
    if price < 200_000:   return 100.0
    if price < 500_000:   return 500.0
    return 1_000.0


def convert(
    symbol: str,
    date: str,
    output_path: Optional[Path] = None,
    synth_trades: bool = True,
    base_latency_ns: int = 5_000_000,
    buffer_size: int = 3_000_000,
) -> np.ndarray:
    """Convert KRX CSV → hftbacktest event array.

    Args:
        symbol: KRX symbol code ("005930" Samsung)
        date: YYYYMMDD string
        output_path: If set, saves as .npz (compressed)
        synth_trades: Synthesize TRADE_EVENTs from ACML_VOL deltas
        base_latency_ns: Added to local_ts to avoid zero feed latency (ns)
        buffer_size: Pre-allocated event buffer

    Returns:
        Event array (post correct_local_timestamp + correct_event_order)
    """
    path = KRX_DATA_ROOT / date / f"{symbol}.csv"
    print(f"[krx→hftb] reading {path}")
    df = pd.read_csv(path, low_memory=False,
                     dtype={"MKSC_SHRN_ISCD": "string",
                            "HOUR_CLS_CODE": "string",
                            "tr_id": "string"})
    df["ts_ns"] = pd.to_datetime(df["recv_ts_kst"], utc=False).astype("int64")
    # Keep HOUR_CLS_CODE == "0" rows with valid top-of-book. KRX pre-open CSV rows
    # are tagged HOUR_CLS_CODE=0 but carry all-zero prices before 09:00 KST —
    # exclude those; they contribute nothing to the event stream and skew tick_size
    # detection.
    df["HOUR_CLS_CODE"] = df["HOUR_CLS_CODE"].fillna("0").astype("string")
    df = df[df["HOUR_CLS_CODE"] == "0"]
    df = df[(df["BIDP1"] > 0) & (df["ASKP1"] > 0) & (df["ASKP1"] > df["BIDP1"])].reset_index(drop=True)
    print(f"  valid session rows (BIDP1>0, ASKP1>BIDP1): {len(df):,}")

    # Determine representative tick size from first valid row's bid_px1
    first_px = float(df["BIDP1"].iloc[0])
    tick_size = krx_tick_size(first_px)
    lot_size = 1.0  # KRX cash equities trade in integer shares
    print(f"  tick_size={tick_size:.0f} KRW  lot_size={lot_size:.0f}")

    diff = DiffOrderBookSnapshot(N_LEVELS, tick_size, lot_size)
    tmp = np.empty(buffer_size, event_dtype)
    row_num = 0

    prev_acml = None
    prev_mid = None

    for idx, r in df.iterrows():
        exch_ts = int(r["ts_ns"])
        local_ts = exch_ts + base_latency_ns

        # Prepare bid/ask arrays — KRX supplies 10 fixed levels (may include zeros
        # on sparse books); filter zeros so DiffOrderBookSnapshot doesn't treat them
        # as real levels at price=0.
        bid_px = np.array([float(r[c]) for c in BID_PX_COLS])
        bid_qty = np.array([float(r[c]) for c in BID_QTY_COLS])
        ask_px = np.array([float(r[c]) for c in ASK_PX_COLS])
        ask_qty = np.array([float(r[c]) for c in ASK_QTY_COLS])

        # Sanity: need valid top-of-book
        if bid_px[0] <= 0 or ask_px[0] <= 0 or ask_px[0] <= bid_px[0]:
            continue

        # Filter zero-qty or zero-price trailing levels
        bid_mask = (bid_px > 0) & (bid_qty > 0)
        ask_mask = (ask_px > 0) & (ask_qty > 0)
        bid_px_f = bid_px[bid_mask]
        bid_qty_f = bid_qty[bid_mask]
        ask_px_f = ask_px[ask_mask]
        ask_qty_f = ask_qty[ask_mask]

        bid, ask, bid_del, ask_del = diff.snapshot(
            bid_px_f, bid_qty_f, ask_px_f, ask_qty_f
        )

        # Emit depth events: bids (INSERTED / CHANGED)
        for entry in bid:
            if entry[2] == INSERTED or entry[2] == CHANGED:
                tmp[row_num] = (
                    DEPTH_EVENT | BUY_EVENT,
                    exch_ts, local_ts,
                    float(entry[0]), float(entry[1]),
                    0, 0, 0,
                )
                row_num += 1
        # asks
        for entry in ask:
            if entry[2] == INSERTED or entry[2] == CHANGED:
                tmp[row_num] = (
                    DEPTH_EVENT | SELL_EVENT,
                    exch_ts, local_ts,
                    float(entry[0]), float(entry[1]),
                    0, 0, 0,
                )
                row_num += 1
        # bid deletions
        for entry in bid_del:
            if entry[1] == IN_THE_BOOK_DELETION:
                tmp[row_num] = (
                    DEPTH_EVENT | BUY_EVENT,
                    exch_ts, local_ts,
                    float(entry[0]), 0.0,
                    0, 0, 0,
                )
                row_num += 1
        # ask deletions
        for entry in ask_del:
            if entry[1] == IN_THE_BOOK_DELETION:
                tmp[row_num] = (
                    DEPTH_EVENT | SELL_EVENT,
                    exch_ts, local_ts,
                    float(entry[0]), 0.0,
                    0, 0, 0,
                )
                row_num += 1

        # Synthesized trade events from ACML_VOL delta (crude)
        if synth_trades:
            acml = float(r["ACML_VOL"])
            mid = (bid_px[0] + ask_px[0]) / 2.0
            if prev_acml is not None:
                vol_delta = acml - prev_acml
                if vol_delta > 0:
                    if prev_mid is not None and mid > prev_mid:
                        side_flag = BUY_EVENT
                        trade_px = float(ask_px[0])
                    elif prev_mid is not None and mid < prev_mid:
                        side_flag = SELL_EVENT
                        trade_px = float(bid_px[0])
                    else:
                        # No mid move — default to mid price, sign ambiguous;
                        # skip to avoid misleading queue model
                        side_flag = None
                    if side_flag is not None:
                        tmp[row_num] = (
                            TRADE_EVENT | side_flag,
                            exch_ts, local_ts,
                            trade_px, vol_delta,
                            0, 0, 0,
                        )
                        row_num += 1
            prev_acml = acml
            prev_mid = mid

        if row_num > buffer_size - 100:
            print(f"  WARNING: buffer near full at input row {idx}, expanding")
            tmp = np.concatenate([tmp, np.empty(buffer_size, event_dtype)])
            buffer_size = len(tmp)

    events = tmp[:row_num].copy()
    print(f"  events emitted: {row_num:,}")

    print(f"  correcting local ts (base_latency={base_latency_ns}ns)")
    events = correct_local_timestamp(events, base_latency_ns)

    print("  correcting event order")
    sorted_exch = np.argsort(events["exch_ts"], kind="stable")
    sorted_local = np.argsort(events["local_ts"], kind="stable")
    events = correct_event_order(events, sorted_exch, sorted_local)
    print(f"  final events (after ordering): {len(events):,}")

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(output_path, data=events)
        print(f"  saved → {output_path}")

    return events


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True, help="KRX code, e.g. 005930")
    p.add_argument("--date", required=True, help="YYYYMMDD, e.g. 20260326")
    p.add_argument("--out", required=True, help="output .npz path")
    p.add_argument("--no-synth-trades", action="store_true",
                   help="skip synthetic TRADE_EVENTs from ACML_VOL delta")
    p.add_argument("--base-latency-ns", type=int, default=5_000_000,
                   help="artificial latency added to local_ts (ns)")
    args = p.parse_args()

    convert(
        symbol=args.symbol,
        date=args.date,
        output_path=Path(args.out),
        synth_trades=not args.no_synth_trades,
        base_latency_ns=args.base_latency_ns,
    )
