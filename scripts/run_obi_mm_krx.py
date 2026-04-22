"""Port of hftbacktest 'Market Making with Alpha - OBI' notebook to KRX data.

Runs the standardized-OBI market-making strategy on Samsung 005930 2026-03-26
(107,851 regular-session snapshots → 643,462 events after adapter).

Compared to the original BTCUSDT notebook:
  - ROIVectorMarketDepth is replaced with HashMapMarketDepth to avoid pre-sizing
    a huge tick grid (KRW prices span 100_000 ~ 300_000 with tick=100 → 2,000 ticks
    still manageable but HashMap is simpler for the first port).
  - Units are KRW instead of USD; the `_dollar` suffix is replaced with `_krw`.
  - Fees default to zero (pure signal test). Realistic KRX fees can be layered after.
  - Latency is constant (5ms entry + 5ms response) since we lack KRX latency history.
  - Queue model is RiskAdverse first (conservative fills from trades only) — later
    try PowerProbQueueModel for more realistic maker fills.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from numba import njit, uint64
from numba.typed import Dict

from hftbacktest import (
    BacktestAsset,
    HashMapMarketDepthBacktest,
    GTX,
    LIMIT,
    BUY,
    SELL,
    Recorder,
)
from hftbacktest.stats import LinearAssetRecord


@njit
def obi_mm(
    hbt,
    stat,
    half_spread,
    skew,
    c1,
    looking_depth_frac,
    interval,
    window,
    order_qty_krw,
    max_position_krw,
    grid_num,
    grid_interval,
):
    asset_no = 0
    imbalance_timeseries = np.full(30_000_000, np.nan, np.float64)

    tick_size = hbt.depth(0).tick_size
    lot_size = hbt.depth(0).lot_size

    t = 0

    while hbt.elapse(interval) == 0:
        hbt.clear_inactive_orders(asset_no)

        depth = hbt.depth(asset_no)
        position = hbt.position(asset_no)
        orders = hbt.orders(asset_no)

        best_bid = depth.best_bid
        best_ask = depth.best_ask

        if best_bid <= 0 or best_ask <= 0 or best_ask <= best_bid:
            t += 1
            if t >= len(imbalance_timeseries):
                break
            continue

        mid_price = (best_bid + best_ask) / 2.0

        # Sum ask qty from best_ask upto mid*(1+looking_depth_frac)
        sum_ask_qty = 0.0
        best_ask_tick = depth.best_ask_tick
        upto_tick_ask = int(np.floor(mid_price * (1 + looking_depth_frac) / tick_size))
        for price_tick in range(best_ask_tick, upto_tick_ask + 1):
            sum_ask_qty += depth.ask_qty_at_tick(price_tick)

        # Sum bid qty from best_bid downto mid*(1-looking_depth_frac)
        sum_bid_qty = 0.0
        best_bid_tick = depth.best_bid_tick
        downto_tick_bid = int(np.ceil(mid_price * (1 - looking_depth_frac) / tick_size))
        for price_tick in range(best_bid_tick, downto_tick_bid - 1, -1):
            sum_bid_qty += depth.bid_qty_at_tick(price_tick)

        imbalance_timeseries[t] = sum_bid_qty - sum_ask_qty

        # Standardize over trailing window
        start = max(0, t + 1 - window)
        m = np.nanmean(imbalance_timeseries[start:t + 1])
        s = np.nanstd(imbalance_timeseries[start:t + 1])
        if s > 0:
            alpha = (imbalance_timeseries[t] - m) / s
        else:
            alpha = 0.0

        # Compute order price
        order_qty = max(round((order_qty_krw / mid_price) / lot_size) * lot_size, lot_size)
        fair_price = mid_price + c1 * alpha
        normalized_position = position / order_qty
        reservation_price = fair_price - skew * normalized_position

        bid_price = min(np.round(reservation_price - half_spread), best_bid)
        ask_price = max(np.round(reservation_price + half_spread), best_ask)
        bid_price = np.floor(bid_price / tick_size) * tick_size
        ask_price = np.ceil(ask_price / tick_size) * tick_size

        # Build grid
        new_bid_orders = Dict.empty(np.uint64, np.float64)
        if position * mid_price < max_position_krw and np.isfinite(bid_price):
            for i in range(grid_num):
                bid_px_tick = round(bid_price / tick_size)
                new_bid_orders[uint64(bid_px_tick)] = bid_price
                bid_price -= grid_interval

        new_ask_orders = Dict.empty(np.uint64, np.float64)
        if position * mid_price > -max_position_krw and np.isfinite(ask_price):
            for i in range(grid_num):
                ask_px_tick = round(ask_price / tick_size)
                new_ask_orders[uint64(ask_px_tick)] = ask_price
                ask_price += grid_interval

        order_values = orders.values()
        while order_values.has_next():
            order = order_values.get()
            if order.cancellable:
                if (
                    (order.side == BUY and order.order_id not in new_bid_orders)
                    or (order.side == SELL and order.order_id not in new_ask_orders)
                ):
                    hbt.cancel(asset_no, order.order_id, False)

        for order_id, order_price in new_bid_orders.items():
            if order_id not in orders:
                hbt.submit_buy_order(asset_no, order_id, order_price, order_qty, GTX, LIMIT, False)

        for order_id, order_price in new_ask_orders.items():
            if order_id not in orders:
                hbt.submit_sell_order(asset_no, order_id, order_price, order_qty, GTX, LIMIT, False)

        t += 1
        if t >= len(imbalance_timeseries):
            break
        stat.record(hbt)


def run(
    event_file: str,
    out_npz: str,
    symbol: str,
    tick_size: float,
    lot_size: float,
    half_spread: float,
    skew: float,
    c1: float,
    looking_depth_frac: float,
    interval_ns: int,
    window_ticks: int,
    order_qty_krw: float,
    max_position_krw: float,
    grid_num: int,
    maker_fee: float,
    taker_fee: float,
    entry_latency_ns: int,
    response_latency_ns: int,
) -> None:
    asset = (
        BacktestAsset()
        .data([event_file])
        .linear_asset(1.0)
        .constant_latency(entry_latency_ns, response_latency_ns)
        .risk_adverse_queue_model()
        .no_partial_fill_exchange()
        .trading_value_fee_model(maker_fee, taker_fee)
        .tick_size(tick_size)
        .lot_size(lot_size)
    )

    hbt = HashMapMarketDepthBacktest([asset])
    recorder = Recorder(1, 30_000_000)

    print(f"[obi_mm] symbol={symbol} tick={tick_size} lot={lot_size}")
    print(f"         half_spread={half_spread} skew={skew} c1={c1} depth={looking_depth_frac}")
    print(f"         interval={interval_ns/1e9:.3f}s window={window_ticks} ticks")
    print(f"         order_qty_krw={order_qty_krw:.0f} max_position_krw={max_position_krw:.0f}")
    print(f"         maker_fee={maker_fee} taker_fee={taker_fee}")
    print(f"         entry_latency={entry_latency_ns/1e6:.1f}ms response={response_latency_ns/1e6:.1f}ms")

    t0 = time.time()
    obi_mm(
        hbt,
        recorder.recorder,
        float(half_spread),
        float(skew),
        float(c1),
        float(looking_depth_frac),
        int(interval_ns),
        int(window_ticks),
        float(order_qty_krw),
        float(max_position_krw),
        int(grid_num),
        float(tick_size),  # grid_interval defaults to 1 tick
    )
    wall = time.time() - t0
    hbt.close()
    Path(out_npz).parent.mkdir(parents=True, exist_ok=True)
    recorder.to_npz(out_npz)
    print(f"[obi_mm] done in {wall:.1f}s; saved → {out_npz}")

    # Quick stats
    data = np.load(out_npz)['0']
    rec = LinearAssetRecord(data).resample('5m')
    stats = rec.stats(book_size=max_position_krw)
    print("\n=== Stats summary ===")
    try:
        s = stats.summary()
        print(s)
    except Exception as e:
        print(f"(stats.summary failed: {e})")
        print(f"n_records: {len(data)}  final_position: {data['position'][-1]:.2f}  "
              f"final_balance: {data['balance'][-1]:.0f}  fee: {data['fee'][-1]:.0f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--event-file", default="data/hftb_events/005930_20260326.npz")
    p.add_argument("--out-npz", default="data/hftb_stats/obi_mm_005930_20260326.npz")
    p.add_argument("--symbol", default="005930")
    p.add_argument("--tick-size", type=float, default=100.0,
                   help="Samsung 005930 tick size (KRW)")
    p.add_argument("--lot-size", type=float, default=1.0)
    p.add_argument("--half-spread", type=float, default=150.0,
                   help="Half-width of quote in KRW (150 KRW ≈ 7.5 bps at 200K)")
    p.add_argument("--skew", type=float, default=100.0,
                   help="Inventory skew amplitude in KRW")
    p.add_argument("--c1", type=float, default=200.0,
                   help="Alpha coefficient (KRW per z-score unit)")
    p.add_argument("--looking-depth-frac", type=float, default=0.005,
                   help="0.005 = 0.5% of mid for depth aggregation")
    p.add_argument("--interval-sec", type=float, default=1.0)
    p.add_argument("--window-minutes", type=float, default=30.0,
                   help="Window for OBI standardization")
    p.add_argument("--order-qty-krw", type=float, default=2_000_000.0,
                   help="Per-order notional in KRW (2M ≈ 10 shares at 200K)")
    p.add_argument("--max-position-krw", type=float, default=20_000_000.0,
                   help="Max inventory notional")
    p.add_argument("--grid-num", type=int, default=1)
    p.add_argument("--maker-fee", type=float, default=0.0,
                   help="Fraction of traded value; KRX retail MM = 0; use 0.00015 for taker on cash equity")
    p.add_argument("--taker-fee", type=float, default=0.0)
    p.add_argument("--entry-latency-ms", type=float, default=5.0)
    p.add_argument("--response-latency-ms", type=float, default=5.0)
    args = p.parse_args()

    window_ticks = int(args.window_minutes * 60 / args.interval_sec)
    run(
        event_file=args.event_file,
        out_npz=args.out_npz,
        symbol=args.symbol,
        tick_size=args.tick_size,
        lot_size=args.lot_size,
        half_spread=args.half_spread,
        skew=args.skew,
        c1=args.c1,
        looking_depth_frac=args.looking_depth_frac,
        interval_ns=int(args.interval_sec * 1e9),
        window_ticks=window_ticks,
        order_qty_krw=args.order_qty_krw,
        max_position_krw=args.max_position_krw,
        grid_num=args.grid_num,
        maker_fee=args.maker_fee,
        taker_fee=args.taker_fee,
        entry_latency_ns=int(args.entry_latency_ms * 1e6),
        response_latency_ns=int(args.response_latency_ms * 1e6),
    )
