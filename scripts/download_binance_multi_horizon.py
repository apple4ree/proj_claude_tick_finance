#!/usr/bin/env python3
"""Download Binance OHLCV at multiple horizons for horizon-sweep experiment.

Horizons covered: 1m, 5m, 15m, 1h (daily already exists).
To bound data size and API load, we use a recent 6-month window so that all
horizons use the same period (2025-07-01 .. 2025-12-31). This is 184 days;
at 1-minute resolution that's ~264K bars per symbol — manageable.

Output: data/binance_multi/<horizon>/<symbol>.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO / "data" / "binance_multi"
URL = "https://api.binance.com/api/v3/klines"

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Horizon label -> Binance interval code, bars per day (approx)
HORIZONS = {
    "1m": ("1m", 1440),
    "5m": ("5m", 288),
    "15m": ("15m", 96),
    "1h": ("1h", 24),
}

# Shared window to keep horizons comparable
START = "2025-07-01"
END = "2025-12-31"


def _ms(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def _fetch_batch(symbol: str, interval: str, start_ms: int, end_ms: int,
                 limit: int = 1000) -> list[list]:
    p = {"symbol": symbol, "interval": interval, "startTime": start_ms,
         "endTime": end_ms, "limit": limit}
    url = f"{URL}?{urllib.parse.urlencode(p)}"
    req = urllib.request.Request(url, headers={"User-Agent": "paper/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def download(symbol: str, horizon_label: str, interval: str, start: str, end: str) -> Path:
    out_dir = OUT_ROOT / horizon_label
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{symbol}.csv"
    start_ms = _ms(start)
    end_ms = _ms(end)

    batch_step_ms = 1000 * _interval_sec(interval) * 1000  # 1000 bars * interval in sec * 1000ms
    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        b = _fetch_batch(symbol, interval, cursor, end_ms)
        if not b:
            break
        rows.extend(b)
        last_open = b[-1][0]
        cursor = last_open + _interval_sec(interval) * 1000
        time.sleep(0.2)
        if len(b) < 1000:
            break

    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "n_trades",
            "taker_buy_base", "taker_buy_quote", "_ignore",
        ])
        for r in rows:
            w.writerow(r)

    if rows:
        first = datetime.fromtimestamp(rows[0][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        last = datetime.fromtimestamp(rows[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"  {symbol}/{horizon_label}: {len(rows)} bars [{first}..{last}] -> {out_path.relative_to(REPO)}")
    return out_path


def _interval_sec(interval: str) -> int:
    units = {"m": 60, "h": 3600, "d": 86400}
    n = int(interval[:-1])
    return n * units[interval[-1]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--horizons", nargs="+",
                    default=list(HORIZONS.keys()),
                    choices=list(HORIZONS.keys()))
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    args = ap.parse_args()

    print(f"Multi-horizon download: {args.symbols} × {args.horizons} [{args.start}..{args.end}]")
    for h in args.horizons:
        interval, _ = HORIZONS[h]
        for s in args.symbols:
            try:
                download(s, h, interval, args.start, args.end)
            except Exception as e:
                print(f"  {s}/{h}: FAILED — {e}")


if __name__ == "__main__":
    main()
