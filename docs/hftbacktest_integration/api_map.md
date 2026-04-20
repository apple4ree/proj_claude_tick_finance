# HFTBacktest API ↔ Our Engine Mapping

Reference for Step 3-4 porting.

## Backtest Setup

| Concept | Our engine | HFTBacktest |
|---|---|---|
| Config / spec | `spec.yaml` + `engine/config.py` | `BacktestAsset(...).data(...).constant_latency(...).flat_per_trade_fee_model(...)` |
| Build backtest | `engine.runner.run_backtest()` | `hbt = build_hashmap_backtest([asset])` |
| Symbol / instrument | `symbols: [<id>]` list | `asset_no = 0,1,...` integer |
| Fee model | `FeeModel(commission_bps, tax_bps)` | `flat_per_trade_fee_model(maker_bps, taker_bps)` |
| Latency | `LatencyModel(mean_ms, jitter_ms, seed)` | `constant_latency(entry_ns, resp_ns)` or `intp_order_latency(...)` |

## Data Inputs

| Our | HFTBacktest |
|---|---|
| CSV per symbol per day under `data/ticks/<symbol>/<date>.csv` with 10-level snapshot columns | `.npz` with structured array dtype `{ev, exch_ts, local_ts, px, qty, order_id, ival, fval}` |
| Row-based snapshots (full 10 levels each row) | Event-based (DEPTH / TRADE / DEPTH_SNAPSHOT) |
| Timestamp in ISO8601 | Timestamp in nanoseconds since epoch |

## Strategy Runtime

| Our | HFTBacktest |
|---|---|
| `Strategy.on_tick(snap, portfolio, last_mids, current_ts_ns)` per-tick callable | `@njit def algo(hbt):` event loop with `hbt.elapse(ns)` |
| Snap access: `snap.bid_px[0]`, `snap.ask_px[0]`, `snap.bid_qty[i]`, ... | `depth = hbt.depth(asset_no); bid = depth.best_bid_tick; bid_qty = depth.bid_qty_at_tick(tick)` |
| Position: `portfolio.positions[symbol].qty` | `pos = hbt.position(asset_no)` |
| Last mid: `last_mids[symbol]` | `depth.mid_price` |

## Order Submission

| Our (returns `list[Order]`) | HFTBacktest (direct call) |
|---|---|
| `Order(sym, BUY, qty, MARKET, None, tag)` | `hbt.submit_buy_order(asset_no, order_id, best_ask_price, qty, GTC, MARKET, False)` |
| `Order(sym, BUY, qty, LIMIT, limit_price, tag)` | `hbt.submit_buy_order(asset_no, order_id, limit_price, qty, GTX, LIMIT, False)` passive |
| `Order(sym, BUY, qty, LIMIT, limit_price, tag)` + active take | `hbt.submit_buy_order(... GTC, LIMIT, False)` — fills if marketable |
| `Order(sym, None, 0, CANCEL, None, "tag")` | `hbt.cancel(asset_no, order_id, False)` |
| `Order(sym, SELL, qty, MARKET, None, tag)` | `hbt.submit_sell_order(asset_no, order_id, best_bid_price, qty, GTC, MARKET, False)` |

## Order Lifecycle

| Our | HFTBacktest |
|---|---|
| `pending_queue` with `target_ts_ns = now + latency` | Internal; exposed via `hbt.orders(asset_no)` iteration |
| `resting_limits` queue model | `hbt.submit_...(..., GTX, LIMIT)` + `l3_fifo_queue_model()` |
| Fill generates `Fill(ts, symbol, side, qty, avg_price, fee, tag, context)` | `Recorder` captures fills + state snapshots |
| `simulator._record_fill_for_invariants(fill)` | Our invariant layer reads from Recorder output |

## Order States

| Our | HFTBacktest |
|---|---|
| pending / filled / cancelled / rejected_cash / rejected_short / rejected_no_liquidity / rejected_strict_invariant | NEW, FILLED, CANCELED, EXPIRED, NONE |

## TIF (Time-in-Force)

| Our | HFTBacktest |
|---|---|
| (implicit — TTL ticks in strategy) | `GTC` — good-till-cancel, `GTX` — post-only |

## Fee Semantics

| Our | HFTBacktest |
|---|---|
| `commission_bps=1.5` (each side) + `sell_tax_bps=18.0` (sell only) → 21 bps round-trip | `flat_per_trade_fee_model(maker_bps, taker_bps)` — symmetric per side |
| Sell-side tax is Korean-specific | Crypto has symmetric maker/taker; adjust numerics accordingly |

## Invariant Checking

| Our | HFTBacktest |
|---|---|
| Inline in `simulator._record_fill_for_invariants()` | Externalize: parse Recorder fills + spec → apply generic checker |
| `strict_mode` intervenes live via `should_block_order` / `should_force_sell` | Would require modifying HFTBacktest source (complex); alternative: run HFTBacktest normally + strict_pnl via replay filter |

## Fill Context (for WIN/LOSS analysis)

| Our | HFTBacktest |
|---|---|
| `Fill.context = {obi, spread_bps, bid_px, ask_px, mid, acml_vol}` — snapshot at fill time | Recorder stores book state; derive context post-hoc from `state.npz` |
