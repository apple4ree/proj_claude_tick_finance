#!/usr/bin/env python3
"""Download daily OHLCV from Binance public API.

Pulls historical daily klines via Binance REST API (no authentication needed).
Stores results as CSV under data/binance_daily/<symbol>.csv with columns:
  open_time, open, high, low, close, volume, close_time, quote_volume,
  n_trades, taker_buy_base, taker_buy_quote

Usage:
  python scripts/download_binance_daily.py --symbol BTCUSDT --start 2023-01-01 --end 2025-12-31
  python scripts/download_binance_daily.py --all  # BTC/ETH/SOL defaults
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "data" / "binance_daily"

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _fetch_batch(symbol: str, start_ms: int, end_ms: int, limit: int = 1000) -> list[list]:
    params = {
        "symbol": symbol,
        "interval": "1d",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
    }
    url = f"{BINANCE_KLINES_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "paper-fidelity-gap/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_symbol(symbol: str, start: str, end: str) -> Path:
    start_ms = _ms(start)
    end_ms = _ms(end)
    all_rows: list[list] = []
    cursor = start_ms
    # Binance returns up to 1000 bars per call; daily = ~2.7 years per batch
    while cursor < end_ms:
        batch = _fetch_batch(symbol, cursor, end_ms)
        if not batch:
            break
        all_rows.extend(batch)
        last_open_time = batch[-1][0]
        # Advance cursor past the last bar's open_time to avoid overlap
        cursor = last_open_time + 86_400_000
        time.sleep(0.15)  # light rate-limit courtesy
        if len(batch) < 1000:
            break

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{symbol}.csv"
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "n_trades",
            "taker_buy_base", "taker_buy_quote", "_ignore",
        ])
        for r in all_rows:
            writer.writerow(r)

    first = datetime.fromtimestamp(all_rows[0][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    last = datetime.fromtimestamp(all_rows[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"  {symbol}: {len(all_rows)} bars [{first} .. {last}] -> {out_path.relative_to(REPO)}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Download Binance daily OHLCV.")
    ap.add_argument("--symbol", help="Single symbol (e.g. BTCUSDT)")
    ap.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD")
    ap.add_argument("--end", default="2025-12-31", help="End date YYYY-MM-DD")
    ap.add_argument("--all", action="store_true",
                    help=f"Download defaults: {DEFAULT_SYMBOLS}")
    args = ap.parse_args()

    if args.all:
        symbols = DEFAULT_SYMBOLS
    elif args.symbol:
        symbols = [args.symbol]
    else:
        ap.error("specify --symbol or --all")

    print(f"Downloading {len(symbols)} symbol(s) daily bars [{args.start} .. {args.end}]")
    for s in symbols:
        try:
            download_symbol(s, args.start, args.end)
        except Exception as exc:
            print(f"  {s}: FAILED — {exc}")


if __name__ == "__main__":
    main()
