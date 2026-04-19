# HFTBacktest Integration Plan

**Goal**: Make our invariant checker + counterfactual PnL attribution **engine-agnostic** by demonstrating it works on HFTBacktest (nkaz001), MIT-licensed, widely-adopted tick-level LOB backtest engine.

**Paper value**: Cross-engine replication of our failure taxonomy validates that findings reflect **LLM behavior**, not engine-specific artifacts.

## Status (2026-04-17)

| Step | Status | Notes |
|---|---|---|
| S2a. Install hftbacktest 2.3.0 | ✓ Done | `pip install hftbacktest` |
| S2b. API inspection | ✓ Done | see `api_map.md` |
| S2c. Data format mapping | ✓ Done | see `data_format.md` |
| S2d. Hello-world strategy | pending | requires sample .npz data |
| S3. Invariant layer porting POC | pending | engine-agnostic refactor of `engine/invariants.py` |
| S4. Cross-engine crypto pilot | pending | Binance BTC via HFTBacktest + our invariant layer |
| S5. Paper v3 outline | pending | after POC validates the engine-agnostic claim |

## HFTBacktest Core Concepts

**Strategy API** (numba @njit):
```python
@njit
def strategy(hbt):
    while hbt.elapse(10_000_000) == 0:  # advance 10ms
        depth = hbt.depth(asset_no)    # current book
        pos   = hbt.position(asset_no) # current position
        orders = hbt.orders(asset_no)  # active orders
        # ...decision logic...
        hbt.submit_buy_order(asset_no, order_id, price, qty, GTX, LIMIT, False)
```

**Data format**: structured numpy array with dtype:
```
ev: u8          event type (DEPTH, TRADE, FILL, ...)
exch_ts: i8     exchange timestamp (ns)
local_ts: i8    local timestamp (ns)
px: f8          price
qty: f8         quantity
order_id: u8    order id
ival: i8        intrinsic value
fval: f8        float value
```

**Event types**:
- `DEPTH_EVENT` — book level change
- `DEPTH_SNAPSHOT_EVENT` — full snapshot
- `DEPTH_BBO_EVENT` — top-of-book only
- `TRADE_EVENT` — tape
- `FILL_EVENT` — our order filled

**Models**:
- `constant_latency(entry_ns, resp_ns)` — fixed latency (matches our 5ms + jitter)
- `intp_order_latency(data)` — historical interpolated latency
- `flat_per_trade_fee_model(maker, taker)` — matches our fee model
- `l3_fifo_queue_model()` — realistic queue position

## Data Conversion Plan (Upbit CSV → HFTBacktest .npz)

Our Upbit CSV has full 10-level snapshot per row. Conversion strategy:

1. **Row-to-events**: for each CSV row, detect which levels changed vs previous row
2. **Event emission**:
   - If all levels changed → emit one `DEPTH_SNAPSHOT_EVENT` with 20 levels
   - Else → emit `DEPTH_EVENT` per changed level (with side, px, qty)
3. **Timestamps**:
   - `recv_ts_utc` parsed to nanoseconds → both `exch_ts` and `local_ts` (can add ~5ms jitter for realism)
4. **Initial snapshot**: first row → `initial_snapshot(...)`
5. **Output**: single `.npz` per symbol per day

Estimated effort: ~1 day to write + verify converter.

## Invariant Layer Engine-Agnostic Refactor

Current `engine/invariants.py` is coupled to our simulator's fill records. To make it portable:

**Generalize fill interface**:
```python
@dataclass
class Fill:
    ts_ns: int
    symbol: str
    side: str      # BUY / SELL
    qty: float
    avg_price: float
    fee: float
    tag: str       # entry_obi, stop_loss, pt_limit, ...
    context: dict  # book snapshot at fill time
```

**Both engines must produce** a list of such Fill records + the spec dict. Then `check_invariants(spec, fills)` is engine-agnostic.

HFTBacktest fills must be wrapped to this shape (HFTBacktest provides `Recorder` that logs fills; parse its output).

## Paper Positioning (v3)

With cross-engine replication demonstrated:

> *We introduce an engine-agnostic measurement layer — invariant inference from spec + counterfactual PnL attribution — and demonstrate it on two independent LOB backtest engines: our custom KRX engine and HFTBacktest (MIT-licensed, Binance-native). The four failure modes we document (spec-implementation drift, domain-knowledge gaps, multi-agent handoff decay, invariant-taxonomy blindspots) are engine-consistent, ruling out engine-specific artifacts as an explanation. The layer can be adopted on top of any deterministic LOB simulator that produces `(spec, fill_list)` records.*

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| HFTBacktest uses numba — our LLM-generated strategies may not compile | Wrap LLM output in a Python-to-numba translator, or use HFTBacktest's non-jitted fallback |
| Queue-position model is stricter than ours — may produce different fills | Document as a feature, not a bug. Shows engine-consistency of the *qualitative* failure modes |
| Data conversion may lose fidelity (row-based snapshots vs event stream) | Start with `DEPTH_SNAPSHOT_EVENT` per row (lossless); optimize only if needed |
| Existing 6 strategies are KRX-coupled, not easy to re-run on crypto | Port 1–2 representative strategies for replication; accept reduced n for this cross-validation section |

## Next Session Actions

1. Obtain HFTBacktest sample data (either from their GitHub or generate from our Upbit CSV)
2. Write `scripts/convert_upbit_to_hftbacktest.py` — Upbit CSV → HFTBacktest .npz
3. Run HFTBacktest hello-world example with converted BTC data
4. Refactor `engine/invariants.py` to take generic `Fill` records (not tied to our simulator)
5. Write `scripts/check_invariants_from_fills.py` — standalone invariant checker
6. POC: run invariant checker on HFTBacktest fills → produces same-schema `invariant_violations`

## References

- HFTBacktest GitHub: https://github.com/nkaz001/hftbacktest
- HFTBacktest docs: https://hftbacktest.readthedocs.io/
- ABIDES-MARL (alternative, Nov 2025): https://arxiv.org/abs/2511.02016
- JAX-LOB (GPU-parallel alternative): https://arxiv.org/abs/2308.13289
