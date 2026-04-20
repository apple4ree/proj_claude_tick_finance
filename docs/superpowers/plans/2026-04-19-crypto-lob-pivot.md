# Crypto-Only Pivot + LOB Pipeline Implementation Plan

> **For agentic workers:** Implementation plan for full project re-orientation toward crypto data including live LOB collection. Steps use checkbox syntax.

**Goal:** Pivot the project fully to crypto data: (a) keep Binance OHLCV bar path for directional strategies, (b) add Binance L2 order book collection for LOB-aware / market-making strategies (ping-pong class), (c) remove KRX legacy + Qlib CSI500/SP500 paths entirely.

**Architecture:**
- Data: `data/binance_multi/{1d,1h,15m,5m}/<SYM>.csv` (existing) + `data/binance_lob/<sym>/<date>/<hour>.parquet` (new, forward-going)
- Engine: already supports `OrderBookSnapshot` + queue-position fills (from archived KRX engine); needs adapter to read parquet LOB
- Agents: OHLCV-only bar path + LOB-aware tick path, dual-mode in each designer prompt

**Tech Stack:** Python 3.10+, pandas, numpy, pyarrow (parquet), `websocket-client` or `websockets` (Binance stream), pydantic 2

**Policy constraint (2026-04-19):** Every `/experiment` run MUST perform ≥ 10 iterations. Single-shot runs are disallowed.

---

## Phase X1 — Cleanup (KRX + Qlib 완전 제거)

**Files to delete:**
- `data/_archive/krx_legacy/` (KRX tick features + briefs + BTC v1 artifacts)
- `data/qlib_csi500_1min/` (방금 export)
- `data/qlib_sp500_1d/` (방금 export)
- `data/signal_briefs_v2/csi500_1min.json*`
- `data/signal_briefs_v2/sp500_1d.json*`
- `scripts/_legacy/` (signal_research.py, generate_signal_brief.py, optimal_params.py)
- `scripts/qlib_export.py`
- `tests/_legacy/test_signal_brief.py`
- `~/.qlib/qlib_data/` (optional — 8 GB, keep if disk not tight, but not referenced)

**Files to modify:**
- `CLAUDE.md`: remove all KRX references, remove Qlib references, add X5 rule (n_iter ≥ 10), re-frame as **crypto OHLCV + crypto LOB dual-mode**.
- `.claude/commands/experiment.md`: remove KRX/Qlib market options, update market enum to `crypto_1d | crypto_1h | crypto_15m | crypto_5m | crypto_lob`.
- `engine/spec.py`: remove `csi500`, `sp500` from `UNIVERSE_PRESETS`, keep `TOP3_SYMBOLS`.
- `scripts/discover_alpha.py`: remove `csi500_1min`, `sp500_1d` from `MARKET_PATHS`.
- Memory files: update `project_crypto_pivot.md`, `project_standard_eval_universe.md` to reflect crypto-only.
- Remove `pyqlib` from requirements if pinned (Qlib is no longer needed).

---

## Phase X2 — Binance LOB Collector

Create `scripts/binance_lob_collector.py`:

```python
# WebSocket endpoint: wss://stream.binance.com:9443/ws/<sym>@depth20@100ms
# Subscribes per symbol, receives 20-level orderbook snapshot every 100ms
# Aggregates 1s worth of snapshots into parquet row (or keeps raw 10Hz)
# Partitioned: data/binance_lob/<sym>/YYYY-MM-DD/HH.parquet
# Schema: ts_ns, ask_px[0..19], ask_qty[0..19], bid_px[0..19], bid_qty[0..19],
#         total_ask_qty, total_bid_qty
```

Features:
- Reconnect on WS drop
- Heartbeat log every minute: symbol, recv count, latest ts
- `--symbols BTCUSDT,ETHUSDT,SOLUSDT` arg
- `--out-dir data/binance_lob` (default)
- `--max-levels 20` (default)
- `--sample-interval-ms 100` (default, matches Binance `@100ms` stream)
- Graceful shutdown on SIGTERM; flushes pending parquet buffer

Runner:
```bash
nohup python3 scripts/binance_lob_collector.py --symbols BTCUSDT,ETHUSDT,SOLUSDT \
    > /tmp/binance_lob.log 2>&1 &
```

Expected throughput: 3 symbols × 10 snapshots/s × 24h = ~2.6M rows/day. Compressed parquet ≈ 200-400 MB/day all-symbol.

---

## Phase X3 — Engine data_loader LOB adapter

Extend `engine/data_loader.py`:

```python
def iter_events_lob(
    start_ts_ns: int, end_ts_ns: int, symbols: list[str],
    lob_root: Path = Path("data/binance_lob"),
) -> Iterator[OrderBookSnapshot]:
    """Yield per-tick OrderBookSnapshot from parquet LOB archive."""
    # Read hourly parquet files in order, reconstruct 10-level snapshot
```

- Add `CRYPTO_LOB_ROOT` constant
- Preserve `OrderBookSnapshot` interface exactly so existing `engine.simulator.Backtester` consumes LOB transparently
- Level depth: LOB has 20, snapshot uses top 10 (truncate)

Validate with `scripts/audit_principles.py` — existing 12 checks should still pass on crypto LOB input.

---

## Phase X4 — Agent prompts (LOB + market-making)

### alpha-designer.md

Add market branching:

```markdown
## Strategy paradigm selection

The `--market` field determines what signals/paradigms are available:

- `crypto_1d | crypto_1h | crypto_15m | crypto_5m` (bar-level): directional
  strategies — mean-reversion, momentum, breakout on OHLCV + taker flow.
- `crypto_lob` (tick LOB): directional OR market-making paradigms.
  Market-making signals: spread capture, book pressure imbalance,
  ping-pong between bid/ask levels.
```

Add new paradigm value: `paradigm: "market_making"` in `AlphaHandoff` schema.

### execution-designer.md

Add market-making execution mode:

```markdown
For `paradigm="market_making"`:
- `entry_execution.price` can be `"bid"` or `"bid_minus_1tick"` (passive LIMIT)
- `ttl_ticks` and `cancel_on_bid_drop_ticks` become critical
- Two-sided quoting: pair the long LIMIT with a symmetric SELL LIMIT
- Fee assumption: maker fee (often negative/rebate on Binance VIP)
```

### strategy-coder.md

Add `on_tick(snap, ctx)` template for LOB strategies. Existing bar template retained.

Pydantic schema note: `AlphaHandoff.paradigm` already allows string literals; add `market_making` to the Literal.

---

## Phase X5 — Iter ≥ 10 정책 강제

### `.claude/commands/experiment.md`

```markdown
| `--n-iterations` | **10** (new default) | Minimum 10 required |
```

Add validation block at Step 0:
```
if --n-iterations < 10:
    abort with message: "Policy 2026-04-19: /experiment requires n-iterations >= 10"
```

### CLAUDE.md Rules 섹션

Add:
```markdown
- **Iteration budget**: `/experiment --n-iterations` must be ≥ 10. Single-shot
  runs are disallowed per 2026-04-19 policy. This is to force the autonomous
  loop to actually surface lessons rather than one-shot noise.
```

---

## Phase X6 — 데이터 축적 후 첫 iter

User-time milestone. Requires:
- Collector running ≥ 2 weeks for initial IS window
- Phase X3/X4 code integration verified via unit tests
- First `/experiment --market crypto_lob --n-iterations 10` run after LOB archive has ≥ 14 days

Document in a new session after the data matures.

---

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| Binance WS rate limits | Use 100ms stream (官方 allowed), exponential backoff on disconnect |
| Parquet disk growth | Daily rotation + compression; monitor with `du` weekly |
| Agent confused by dual bar/LOB mode | Clear market-type branching in prompts; Pydantic schema validates paradigm-market compatibility |
| Policy X5 blocks accidental single-run tests | Provide `--smoke-test` bypass flag (not default) |

## Success Criteria

1. `data/binance_lob/` accumulates without gaps for 14+ days
2. `engine.runner` can backtest a dummy ping-pong strategy on collected LOB
3. `/experiment --market crypto_lob --n-iterations 10` completes end-to-end
4. `audit_principles.py` still 12/12 after engine/data_loader extension
5. Pydantic schema validation 71+ tests still pass
