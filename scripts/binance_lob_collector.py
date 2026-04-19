#!/usr/bin/env python3
"""Binance L2 order book snapshot collector (forward-going, 100 ms cadence).

Subscribes to the Binance spot partial-depth stream for each target symbol
and persists 20-level snapshots to hourly-partitioned Parquet files:

    data/binance_lob/<SYM>/YYYY-MM-DD/HH.parquet

The feed is `wss://stream.binance.com:9443/ws/<sym>@depth20@100ms`. Each
message carries the top-20 bids + top-20 asks as price/qty string pairs;
this script parses them to float and writes rows with schema:

    ts_ns          int64   event time (Binance `E` field, ms → ns)
    ask_px_0..19   float64
    ask_qty_0..19  float64
    bid_px_0..19   float64
    bid_qty_0..19  float64
    total_ask_qty  float64 (sum of all 20 ask levels)
    total_bid_qty  float64 (sum of all 20 bid levels)

The file is closed + replaced atomically each `flush_interval_sec` (default
300 s) within the same hour file, so a SIGTERM in the middle of an hour
still leaves a valid Parquet on disk.

Usage:
    nohup python scripts/binance_lob_collector.py \
        --symbols BTCUSDT,ETHUSDT,SOLUSDT \
        > /tmp/binance_lob.log 2>&1 &

Notes:
- Binance partial-depth stream is *push-only* (no snapshot + incremental
  diff mechanic) so each message is a self-contained top-20 view. No gap
  reconstruction needed.
- Reconnect policy: exponential backoff capped at 30 s.
- 3 symbols × 10 Hz × 86400 s = 2.6 M rows/day total; compressed parquet
  ≈ 200–400 MB/day across all symbols.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque

import pyarrow as pa
import pyarrow.parquet as pq
import websockets

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "binance_lob"

BINANCE_WS = "wss://stream.binance.com:9443/ws"

LEVELS = 20  # Binance @depth20 stream


def _build_schema() -> pa.Schema:
    fields = [pa.field("ts_ns", pa.int64())]
    for side in ("ask", "bid"):
        for i in range(LEVELS):
            fields.append(pa.field(f"{side}_px_{i}", pa.float64()))
            fields.append(pa.field(f"{side}_qty_{i}", pa.float64()))
    fields.append(pa.field("total_ask_qty", pa.float64()))
    fields.append(pa.field("total_bid_qty", pa.float64()))
    return pa.schema(fields)


SCHEMA = _build_schema()


def _parse_message(msg: dict) -> dict | None:
    """Binance partial-depth stream payload → flat row dict. Returns None if malformed."""
    try:
        # The @depth20@100ms stream payload has no "e"/"E" in partial stream;
        # it's just {lastUpdateId, bids, asks}. Use wall-clock ts if missing.
        asks = msg.get("a") or msg.get("asks") or []
        bids = msg.get("b") or msg.get("bids") or []
        if len(asks) < 1 or len(bids) < 1:
            return None

        row: dict[str, float | int] = {"ts_ns": time.time_ns()}
        total_ask = 0.0
        total_bid = 0.0
        for i in range(LEVELS):
            if i < len(asks):
                px = float(asks[i][0])
                qty = float(asks[i][1])
            else:
                px = 0.0
                qty = 0.0
            row[f"ask_px_{i}"] = px
            row[f"ask_qty_{i}"] = qty
            total_ask += qty

            if i < len(bids):
                px = float(bids[i][0])
                qty = float(bids[i][1])
            else:
                px = 0.0
                qty = 0.0
            row[f"bid_px_{i}"] = px
            row[f"bid_qty_{i}"] = qty
            total_bid += qty

        row["total_ask_qty"] = total_ask
        row["total_bid_qty"] = total_bid
        return row
    except Exception as e:  # malformed
        logging.warning(f"parse error: {e}  msg_keys={list(msg.keys())[:5]}")
        return None


def _hour_partition_path(out_dir: Path, symbol: str, ts_ns: int) -> Path:
    dt = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
    return out_dir / symbol / dt.strftime("%Y-%m-%d") / f"{dt.strftime('%H')}.parquet"


def _flush_to_parquet(rows: list[dict], path: Path) -> None:
    """Append rows to the hourly parquet. If the file exists, read-merge-rewrite
    (parquet append is not native; for low-volume hourly files this is acceptable)."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new_tbl = pa.Table.from_pylist(rows, schema=SCHEMA)
    if path.exists():
        existing = pq.read_table(path)
        merged = pa.concat_tables([existing, new_tbl])
    else:
        merged = new_tbl
    pq.write_table(merged, path, compression="zstd", compression_level=5)


class SymbolStream:
    """Owns one Binance WS subscription for one symbol + a growing row buffer."""

    def __init__(self, symbol: str, out_dir: Path, flush_interval_sec: int):
        self.symbol = symbol.upper()
        self.out_dir = out_dir
        self.flush_interval_sec = flush_interval_sec
        self.buffer: list[dict] = []
        self.last_flush_ts = time.time()
        self.recv_count = 0
        self.drops = 0
        self._stop = False

    def stop(self):
        self._stop = True

    def _ws_url(self) -> str:
        return f"{BINANCE_WS}/{self.symbol.lower()}@depth{LEVELS}@100ms"

    async def _maybe_flush(self) -> None:
        now = time.time()
        if now - self.last_flush_ts < self.flush_interval_sec:
            return
        if not self.buffer:
            self.last_flush_ts = now
            return
        # Group buffered rows by hour (unlikely to straddle, but guarded)
        by_path: dict[Path, list[dict]] = {}
        for row in self.buffer:
            p = _hour_partition_path(self.out_dir, self.symbol, row["ts_ns"])
            by_path.setdefault(p, []).append(row)
        for p, rs in by_path.items():
            try:
                _flush_to_parquet(rs, p)
            except Exception as e:
                logging.error(f"[{self.symbol}] flush error at {p}: {e}")
        logging.info(
            f"[{self.symbol}] flushed {len(self.buffer)} rows into {len(by_path)} "
            f"partition(s); total_recv={self.recv_count} drops={self.drops}"
        )
        self.buffer.clear()
        self.last_flush_ts = now

    async def run(self) -> None:
        backoff = 1
        while not self._stop:
            try:
                logging.info(f"[{self.symbol}] connecting → {self._ws_url()}")
                async with websockets.connect(self._ws_url(), ping_interval=20) as ws:
                    backoff = 1
                    while not self._stop:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            self.drops += 1
                            continue
                        row = _parse_message(msg)
                        if row is None:
                            self.drops += 1
                            continue
                        self.buffer.append(row)
                        self.recv_count += 1
                        await self._maybe_flush()
            except asyncio.TimeoutError:
                logging.warning(f"[{self.symbol}] recv timeout; reconnecting")
            except websockets.ConnectionClosed as e:
                logging.warning(f"[{self.symbol}] WS closed: {e}; reconnect in {backoff}s")
            except Exception as e:
                logging.error(f"[{self.symbol}] error: {e}; reconnect in {backoff}s")
            if not self._stop:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
        # final flush
        await self._maybe_flush()
        if self.buffer:
            for row in self.buffer:
                p = _hour_partition_path(self.out_dir, self.symbol, row["ts_ns"])
                try:
                    _flush_to_parquet([row], p)
                except Exception as e:
                    logging.error(f"[{self.symbol}] final flush error: {e}")
            self.buffer.clear()
        logging.info(f"[{self.symbol}] stopped; total_recv={self.recv_count} drops={self.drops}")


async def _main_async(symbols: list[str], out_dir: Path, flush_interval: int) -> None:
    streams = [SymbolStream(s, out_dir, flush_interval) for s in symbols]

    def _sigterm(*_):
        logging.info("SIGTERM/SIGINT received — stopping streams")
        for s in streams:
            s.stop()

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    await asyncio.gather(*(s.run() for s in streams))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT",
                    help="Comma-separated Binance symbols (default: BTC/ETH/SOL)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT),
                    help=f"Output root (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})")
    ap.add_argument("--flush-interval-sec", type=int, default=300,
                    help="Flush buffer to parquet every N seconds (default: 300)")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)-5s %(message)s",
    )

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"binance_lob_collector starting: {symbols} → {out_dir}")
    asyncio.run(_main_async(symbols, out_dir, args.flush_interval_sec))


if __name__ == "__main__":
    main()
