# Data Format Mapping: Upbit CSV → HFTBacktest .npz

## Source: Upbit CSV (what we have)

File: `/home/dgu/tick/crypto/20260416/BTC.csv` and similar.

**Columns** (per row = one order book snapshot):
```
recv_ts_utc, recv_ts_kst, tr_id, MKSC_SHRN_ISCD, BSOP_HOUR, HOUR_CLS_CODE,
ASKP1..ASKP10, BIDP1..BIDP10,
ASKP_RSQN1..ASKP_RSQN10, BIDP_RSQN1..BIDP_RSQN10,
TOTAL_ASKP_RSQN, TOTAL_BIDP_RSQN,
OVTM_*, ANTC_*, ACML_VOL, ...
```

- `ASKP_i`: ask price at level i (1 = best)
- `ASKP_RSQN_i`: ask quantity at level i
- Same for bid side
- `recv_ts_utc`: ISO8601 UTC timestamp
- ~260K rows per day, 463MB

## Target: HFTBacktest .npz

**Structured numpy array** with dtype:
```python
event_dtype = np.dtype([
    ('ev', np.uint64),
    ('exch_ts', np.int64),
    ('local_ts', np.int64),
    ('px', np.float64),
    ('qty', np.float64),
    ('order_id', np.uint64),
    ('ival', np.int64),
    ('fval', np.float64),
], align=True)
```

**Event types** (from `hftbacktest` constants):
- `DEPTH_EVENT` — single level change (px, qty, side in `ev` flags)
- `DEPTH_SNAPSHOT_EVENT` — full book (typically delimited by CLEAR events)
- `DEPTH_CLEAR_EVENT` — reset side (sent at snapshot boundary)
- `TRADE_EVENT` — trade tape
- `BUY_EVENT` / `SELL_EVENT` — side encoding for depth changes

## Conversion Strategy

### Option A — Snapshot per row (simple, lossless, larger)

For each Upbit CSV row:
1. Emit `DEPTH_CLEAR_EVENT` for both sides (reset previous state)
2. Emit 10 `DEPTH_SNAPSHOT_EVENT` rows for ask side (BUY_EVENT flag for bid-incoming? check docs)
3. Emit 10 for bid side

Result: 21 events per CSV row → 260K × 21 = 5.5M events/day.

### Option B — Diff per row (compact, faster backtest)

Track previous snapshot. For each row, emit only `DEPTH_EVENT`s for levels that changed.

Typical KRX/crypto book: 70-90% of levels unchanged between consecutive ticks → ~3-6 events/row → 0.8-1.5M events/day. 5-10x smaller file.

### Recommended: Option A for initial POC, Option B if perf matters.

## Timestamp Handling

Upbit `recv_ts_utc` → ISO8601 string → parse to nanoseconds since Unix epoch:

```python
import pandas as pd
ts_ns = pd.Timestamp(csv_ts).value  # returns int64 ns
```

HFTBacktest uses nanosecond timestamps. Both `exch_ts` and `local_ts` can be set to `ts_ns` for our data (we don't have separate exchange timestamps). Optionally add a 1-2ms offset for `local_ts` to simulate feed latency.

## Initial Snapshot

HFTBacktest's `initial_snapshot(data)` takes a separate file/array with the starting book state. We can:
- Take the first row of the day's CSV
- Emit it as `DEPTH_CLEAR + 10 bid SNAPSHOT + 10 ask SNAPSHOT`
- Save to `<symbol>_<date>_init.npz`

## Fee Model Mapping

| Our KRX | HFTBacktest call |
|---|---|
| commission 1.5 bps each side + 18 bps sell tax = 21 bps round-trip | `asset.flat_per_trade_fee_model(maker_bps=1.5, taker_bps=1.5)` + **add 18 bps to sell-side fill externally** |
| Upbit crypto | `asset.flat_per_trade_fee_model(maker_bps=0.5, taker_bps=2.0)` (current Upbit) or 4 bps symmetric for round-trip |

## Latency Mapping

Our `LatencyModel(mean_ms=5.0, jitter_ms=1.0)` → HFTBacktest `constant_latency(5_000_000, 5_000_000)` (5ms entry + 5ms response).

For jitter, use `intp_order_latency(generated_array)` — pre-generate a NxN array of (ts, entry_lat, resp_lat) triples.

## Converter Script Skeleton

```python
# scripts/convert_upbit_to_hftbacktest.py
import numpy as np
import pandas as pd
from hftbacktest import event_dtype, DEPTH_EVENT, DEPTH_CLEAR_EVENT, BUY_EVENT, SELL_EVENT

def convert(csv_path: Path, out_path: Path):
    df = pd.read_csv(csv_path)
    events = []
    prev_bid = [(None, None)] * 10
    prev_ask = [(None, None)] * 10
    for _, row in df.iterrows():
        ts_ns = pd.Timestamp(row['recv_ts_utc']).value
        # ... diff against prev snapshot ...
        # ... emit DEPTH_EVENT for changed levels ...
    arr = np.array(events, dtype=event_dtype)
    np.savez_compressed(out_path, data=arr)
```

Full implementation: estimated 1 day of work.

## Validation

After conversion, verify:
1. Event count matches expected (Option A: 21 × rows; Option B: measure)
2. Replay the events and reconstruct the book → should match Upbit snapshots exactly (at least for Option A)
3. First 10 timestamps should match first 10 CSV rows
4. mid price trajectory should match original data
