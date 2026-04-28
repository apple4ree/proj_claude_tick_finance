"""KRX tickdata_krx parquet loader (v2).

New data source (replaces open-trading-api CSV):
  /home/dgu/tick/tickdata_krx/<YYYYMMDD>/<symbol>_<name>_<YYYYMMDD>.parquet

Differences from v1 CSV loader:
  - Single parquet per (symbol, date)
  - 60 columns (vs 62) — minor renaming required
  - **Two event types in one file**:
      data_type == 12  →  Quote (book snapshot) — like H0STASP0
      data_type == 11  →  Trade (체결) — NEW, has askbid_type, trading_volume
  - **No ICDC fields** (TOTAL_*_RSQN_ICDC) — computed via .diff()

Loader returns a DataFrame with schema EQUIVALENT to the legacy CSV format
(BIDP1..10 / ASKP1..10 / BIDP_RSQN1..10 / ASKP_RSQN1..10 / TOTAL_*_RSQN /
TOTAL_*_RSQN_ICDC / ACML_VOL / recv_ts_kst), PLUS new columns:
  - trade_volume       (per-tick volume from most recent trade event)
  - askbid_type        (1=buy-initiated, 2=sell-initiated, 0=no recent trade)
  - transaction_power  (KIS-derived, > 0 = buy pressure)
  - last_trade_price   (current_price from most recent trade)

Trade events are merged to quote rows via `merge_asof` with strict
backward direction (no exact-time matches → no lookahead).
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

KRX_TICKDATA_ROOT = Path("/home/dgu/tick/tickdata_krx")
N_LEVELS = 10

# Default 5-second freshness window for trade attachment (microsecond units).
TRADE_TOLERANCE_US = 5_000_000

# Regular KRX session start (09:00:00.000000) packed as HHMMSSuuuuuu int
REGULAR_SESSION_START_LOCAL_TIME = 90000000000   # 09:00:00.000000

# Regular session end (15:30:00.000000)
REGULAR_SESSION_END_LOCAL_TIME = 153000000000


def _build_quote_rename_map() -> dict[str, str]:
    """Map new parquet column names → legacy CSV-equivalent names."""
    rename = {}
    for i in range(1, N_LEVELS + 1):
        rename[f"bid{i}_price"]    = f"BIDP{i}"
        rename[f"ask{i}_price"]    = f"ASKP{i}"
        rename[f"bid{i}_quantity"] = f"BIDP_RSQN{i}"
        rename[f"ask{i}_quantity"] = f"ASKP_RSQN{i}"
    rename["total_bid_quantity"]   = "TOTAL_BIDP_RSQN"
    rename["total_ask_quantity"]   = "TOTAL_ASKP_RSQN"
    rename["cumulative_trading_volume"] = "ACML_VOL"
    rename["local_time"]           = "recv_ts_kst"
    return rename


_QUOTE_RENAME_MAP = _build_quote_rename_map()


def find_parquet(symbol: str, date: str, root: Path = KRX_TICKDATA_ROOT) -> Path:
    """Return parquet path for (symbol, date). Raises FileNotFoundError."""
    pattern = str(root / date / f"{symbol}_*.parquet")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(
            f"No parquet for symbol={symbol} date={date} (pattern: {pattern})"
        )
    if len(matches) > 1:
        # Ambiguous — should not happen since codes are unique
        raise RuntimeError(f"Multiple parquet matches for {symbol}/{date}: {matches}")
    return Path(matches[0])


def load_day_v2(
    symbol: str,
    date: str,
    root: Path = KRX_TICKDATA_ROOT,
    trade_tolerance_us: int = TRADE_TOLERANCE_US,
    regular_session_only: bool = True,
) -> pd.DataFrame:
    """Load one (symbol, date) parquet and return legacy-compatible DataFrame.

    The returned DataFrame contains:
      - Quote columns matching legacy v1 (BIDP1..10, ASKP1..10, RSQN, TOTAL_*,
        ICDC, ACML_VOL, recv_ts_kst)
      - NEW trade columns: trade_volume, askbid_type, transaction_power,
        last_trade_price (from most recent trade event ≤ current quote time)

    Args:
      symbol: 6-digit KRX code (string).
      date:   YYYYMMDD string.
      root:   Tickdata root.
      trade_tolerance_us: Reject trade attachments older than this many μs.
      regular_session_only: If True, filter to 09:00:00 – 15:30:00 KRX regular session.

    Lookahead safety:
      Trade-event merge uses `direction='backward'` + `allow_exact_matches=False`
      → strict <, never attaches a same-timestamp or future trade. Tolerance
      window further bounds attachment to recent activity.
    """
    path = find_parquet(symbol, date, root)
    df_all = pd.read_parquet(path)

    # Split events
    df_quote = df_all[df_all["data_type"] == 12].copy()
    df_trade = df_all[df_all["data_type"] == 11].copy()

    # Quote: rename to legacy schema
    df_quote = df_quote.rename(columns=_QUOTE_RENAME_MAP)

    # Filter regular session (kill pre-market 08:30-09:00 + after-hours)
    if regular_session_only:
        df_quote = df_quote[
            (df_quote["recv_ts_kst"] >= REGULAR_SESSION_START_LOCAL_TIME) &
            (df_quote["recv_ts_kst"] <  REGULAR_SESSION_END_LOCAL_TIME)
        ]

    # Filter zero-book rows (pre-market or feed gaps)
    df_quote = df_quote[
        (df_quote["BIDP1"] > 0) &
        (df_quote["ASKP1"] > 0) &
        (df_quote["ASKP1"] > df_quote["BIDP1"])
    ]
    if len(df_quote) == 0:
        return _empty_legacy_df()

    # Compute ICDC (delta from previous tick) — new data lacks these
    df_quote["TOTAL_BIDP_RSQN_ICDC"] = df_quote["TOTAL_BIDP_RSQN"].diff().fillna(0).astype(np.float64)
    df_quote["TOTAL_ASKP_RSQN_ICDC"] = df_quote["TOTAL_ASKP_RSQN"].diff().fillna(0).astype(np.float64)

    # Drop columns that will be re-introduced from the trade-side merge to
    # avoid name collisions (askbid_type, transaction_power, current_price,
    # trading_volume all exist on both quote and trade rows in the raw feed).
    overlap_cols = ["askbid_type", "transaction_power", "current_price", "trading_volume"]
    df_quote = df_quote.drop(columns=[c for c in overlap_cols if c in df_quote.columns])

    # Sort by time (must be monotonic for merge_asof)
    df_quote = df_quote.sort_values("recv_ts_kst").reset_index(drop=True)

    # Trade-side preparation
    if len(df_trade) > 0 and regular_session_only:
        df_trade = df_trade[
            (df_trade["local_time"] >= REGULAR_SESSION_START_LOCAL_TIME) &
            (df_trade["local_time"] <  REGULAR_SESSION_END_LOCAL_TIME)
        ]

    # Merge_asof to attach most-recent trade to each quote tick
    if len(df_trade) > 0:
        trade_cols = ["local_time", "trading_volume", "askbid_type",
                       "transaction_power", "current_price"]
        df_trade_compact = df_trade[trade_cols].sort_values("local_time").reset_index(drop=True)
        df_trade_compact = df_trade_compact.rename(columns={
            "local_time":     "trade_local_time",
            "trading_volume": "trade_volume",
            "current_price":  "last_trade_price",
        })
        merged = pd.merge_asof(
            df_quote,
            df_trade_compact,
            left_on="recv_ts_kst",
            right_on="trade_local_time",
            direction="backward",
            allow_exact_matches=False,    # ← strict <, blocks lookahead
            tolerance=trade_tolerance_us,
        )
        # Validation: no future-leak
        leak_mask = (merged["trade_local_time"].notna() &
                      (merged["trade_local_time"] >= merged["recv_ts_kst"]))
        if leak_mask.any():
            n_leak = int(leak_mask.sum())
            raise RuntimeError(
                f"Lookahead detected in merge_asof for {symbol}/{date}: "
                f"{n_leak} rows have trade_local_time >= recv_ts_kst"
            )
    else:
        merged = df_quote.copy()
        merged["trade_volume"]      = 0
        merged["askbid_type"]       = 0
        merged["transaction_power"] = 0.0
        merged["last_trade_price"]  = 0.0
        merged["trade_local_time"]  = pd.NA

    # Fill NAs from trades that didn't match (no recent trade event)
    merged["trade_volume"]      = merged["trade_volume"].fillna(0).astype(np.int64)
    merged["askbid_type"]       = merged["askbid_type"].fillna(0).astype(np.int64)
    merged["transaction_power"] = merged["transaction_power"].fillna(0.0).astype(np.float64)
    merged["last_trade_price"]  = merged["last_trade_price"].fillna(0.0).astype(np.float64)

    return merged.reset_index(drop=True)


def _empty_legacy_df() -> pd.DataFrame:
    """Empty legacy-compatible DataFrame for early returns."""
    cols = ["recv_ts_kst", "ACML_VOL"]
    for i in range(1, N_LEVELS + 1):
        cols.extend([f"BIDP{i}", f"ASKP{i}", f"BIDP_RSQN{i}", f"ASKP_RSQN{i}"])
    cols.extend(["TOTAL_BIDP_RSQN", "TOTAL_ASKP_RSQN",
                 "TOTAL_BIDP_RSQN_ICDC", "TOTAL_ASKP_RSQN_ICDC",
                 "trade_volume", "askbid_type", "transaction_power", "last_trade_price"])
    return pd.DataFrame(columns=cols)


# ---------------------------------------------------------------------------
# CLI for verification
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="005930")
    ap.add_argument("--date", default="20260317")
    args = ap.parse_args()

    df = load_day_v2(args.symbol, args.date)
    print(f"Loaded {args.symbol}/{args.date}")
    print(f"  rows: {len(df)}")
    print(f"  cols: {len(df.columns)}")
    print(f"  has trade events: {(df['askbid_type'] > 0).sum()} / {len(df)} "
          f"({100*(df['askbid_type'] > 0).sum()/len(df):.1f}%)")
    print(f"  trade dir distribution: buy={int((df['askbid_type']==1).sum())}, "
          f"sell={int((df['askbid_type']==2).sum())}, none={int((df['askbid_type']==0).sum())}")
    print(f"  first 3 rows:")
    print(df[["recv_ts_kst", "BIDP1", "ASKP1", "BIDP_RSQN1", "ASKP_RSQN1",
              "ACML_VOL", "trade_volume", "askbid_type"]].head(3).to_string())
