"""Perfect-foresight (oracle) upper bound on daily PnL for 1 KRX symbol-day.

Computes three variants, from loosest to strictest:

(A) Raw mid-sum ceiling
    Σ |Δmid_t| over all consecutive snapshot pairs. Assumes: (i) free swapping
    long↔short at mid each tick, (ii) unlimited capital but exactly 1 share
    nominal position, (iii) NO spread cost, NO fee. Theoretical absolute max;
    violates execution reality.

(B) Market-order (taker) ceiling, spread-aware
    At each tick t with mid[t+1] > mid[t]: buy at ask[t], sell at bid[t+1]
    (cost = spread). At each tick with mid[t+1] < mid[t]: short at bid[t], cover
    at ask[t+1]. Take trade only if profitable. Assumes: 1 share, fee=0, no
    latency, every opportunity taken.

(C) Optimal held-position DP, spread-aware
    Position state ∈ {-1, 0, +1}. At each tick decide hold or flip. Flip cost
    = spread (entry + exit = one full spread round). Reward from mid move ×
    position. Solves Bellman in O(T × 3 × 3). This is the tightest "with spread"
    ceiling — strictly ≥ (B) because it allows holding through multi-tick runs.

All outputs are in KRW per 1 share. Multiply by feasible lot size to get lot PnL.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

KRX_ROOT = Path("/home/dgu/tick/open-trading-api/data/realtime/H0STASP0")


def load_midbidask(symbol: str, date: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = KRX_ROOT / date / f"{symbol}.csv"
    df = pd.read_csv(path, low_memory=False,
                     dtype={"MKSC_SHRN_ISCD": "string", "HOUR_CLS_CODE": "string"})
    df["HOUR_CLS_CODE"] = df["HOUR_CLS_CODE"].fillna("0").astype("string")
    df = df[df["HOUR_CLS_CODE"] == "0"]
    df = df[(df["BIDP1"] > 0) & (df["ASKP1"] > 0) & (df["ASKP1"] > df["BIDP1"])].reset_index(drop=True)
    bid = df["BIDP1"].to_numpy(dtype=np.float64)
    ask = df["ASKP1"].to_numpy(dtype=np.float64)
    mid = (bid + ask) / 2.0
    ts = pd.to_datetime(df["recv_ts_kst"], utc=False).astype("int64").to_numpy()
    return ts, mid, bid, ask


def variant_a_raw_mid_sum(mid: np.ndarray) -> dict:
    """Sum of |Δmid| — theoretical max without any execution friction."""
    dmid = np.diff(mid)
    total = float(np.sum(np.abs(dmid)))
    return {
        "variant": "A_raw_mid_sum",
        "pnl_per_share_krw": total,
        "n_profitable_ticks": int(np.sum(np.abs(dmid) > 0)),
        "mean_bps_per_tick": float(np.mean(np.abs(dmid) / mid[:-1]) * 1e4),
    }


def variant_b_taker(mid: np.ndarray, bid: np.ndarray, ask: np.ndarray) -> dict:
    """Per-tick taker ceiling — take every profitable one-tick round-trip."""
    # Long opportunities: buy ask[t], sell bid[t+1]
    long_pnl = np.maximum(0.0, bid[1:] - ask[:-1])
    # Short opportunities: sell bid[t], cover ask[t+1]
    short_pnl = np.maximum(0.0, bid[:-1] - ask[1:])
    # In this formulation they never overlap (since bid<ask and bid[t+1]>ask[t] and
    # bid[t]>ask[t+1] cannot both hold — one means price up, other means price down).
    # But we take whichever is positive.
    total_long = float(np.sum(long_pnl))
    total_short = float(np.sum(short_pnl))
    n_long = int(np.sum(long_pnl > 0))
    n_short = int(np.sum(short_pnl > 0))
    total = total_long + total_short
    return {
        "variant": "B_taker_spread_aware",
        "pnl_per_share_krw": total,
        "n_long_trades": n_long,
        "n_short_trades": n_short,
        "n_total_trades": n_long + n_short,
        "avg_pnl_per_trade_krw": total / max(1, n_long + n_short),
        "mean_spread_bps": float(np.mean((ask - bid) / mid) * 1e4),
    }


def variant_c_dp(mid: np.ndarray, bid: np.ndarray, ask: np.ndarray) -> dict:
    """DP — optimal policy over {-1, 0, +1} position with spread-cost flips.

    State: position ∈ {-1, 0, +1}
    Action at tick t: transition to new position p'
    Transition cost at tick t (in KRW, per share):
      current -1 → +1: pay ask[t]-bid[t] to go flat to +1 (rough)
      Actually we model the realized cash:
        Going from p -> p' at price level pₜ (= mid or spread-crossed), we pay
        (p - p') * price if p'>p (buying) or get (p - p') * price (selling).
      More carefully: to change position by Δ = p' - p shares, we buy |Δ|
      shares at ask (if Δ>0) or sell |Δ| shares at bid (if Δ<0). Cash delta:
        Δp > 0: cash -= Δp * ask[t]
        Δp < 0: cash += |Δp| * bid[t]
      Then hold through to tick t+1 and mark position at mid[t+1]:
        unrealized_at_t+1 = p' * mid[t+1]

    We want to maximize total cash + final mark. Equivalent formulation:
        per-tick reward(p', p, t) = p' * (mid[t+1] - mid[t]) - flip_cost(p, p', t)
      where flip_cost(p, p', t) =
        Δp > 0: Δp * (ask[t] - mid[t])   (half-spread paid on buys)
        Δp < 0: |Δp| * (mid[t] - bid[t]) (half-spread paid on sells)
        Δp = 0: 0

    Bellman: V[t, p'] = max_p (reward(p', p, t) + V[t-1, p])
    (starting from V[0, p] = -entry_cost from flat)
    Final profit = max_p V[T, p] (sell down to flat at final tick).
    """
    T = len(mid) - 1  # number of step transitions
    POS = np.array([-1, 0, 1], dtype=np.int64)
    n_pos = 3
    INF = -1e18

    # dp[t][p'] = max total cumulative cash + mark value after transitioning to p' at tick t
    # We iterate t = 0..T-1 (each transition uses mid[t]→mid[t+1])
    dp = np.full((T + 1, n_pos), INF)
    # At tick 0, we can start from flat (pos=0) at no cost
    # Entering any position at tick 0 costs: half-spread × |p|
    for pi, p in enumerate(POS):
        if p == 0:
            dp[0, pi] = 0.0
        elif p > 0:
            # Buy p shares at ask[0]; reward realized later via mid moves
            dp[0, pi] = - (ask[0] - mid[0]) * p  # pay half-spread per share
        else:
            dp[0, pi] = - (mid[0] - bid[0]) * abs(p)  # half-spread per share

    # Transition loop
    for t in range(T):
        half_spread_buy = ask[t + 1] - mid[t + 1]   # incoming half-spread at next tick
        half_spread_sell = mid[t + 1] - bid[t + 1]
        dmid = mid[t + 1] - mid[t]
        for pi_next, p_next in enumerate(POS):
            best = INF
            for pi_prev, p_prev in enumerate(POS):
                # Reward of holding p_prev from t to t+1
                hold_reward = p_prev * dmid
                # Flip cost at t+1 to move from p_prev to p_next
                dp_shares = p_next - p_prev
                if dp_shares > 0:
                    # Buy dp_shares: pay half-spread per share
                    flip_cost = dp_shares * half_spread_buy
                elif dp_shares < 0:
                    flip_cost = abs(dp_shares) * half_spread_sell
                else:
                    flip_cost = 0.0
                val = dp[t, pi_prev] + hold_reward - flip_cost
                if val > best:
                    best = val
            dp[t + 1, pi_next] = best

    # At tick T, we must end flat — close any open position at half-spread cost
    final = INF
    for pi_last, p_last in enumerate(POS):
        if p_last > 0:
            close_cost = p_last * (mid[-1] - bid[-1])
        elif p_last < 0:
            close_cost = abs(p_last) * (ask[-1] - mid[-1])
        else:
            close_cost = 0
        v = dp[T, pi_last] - close_cost
        if v > final:
            final = v

    # Count trades: backtrack is needed for a proper count; skip here and just
    # report the PnL plus approximate trade count via sign-flip heuristic.
    dmid_arr = np.diff(mid)
    n_runs = int(np.sum(np.diff(np.sign(dmid_arr)) != 0)) + 1  # rough
    return {
        "variant": "C_dp_optimal_spread_aware",
        "pnl_per_share_krw": float(final),
        "approx_n_monotone_runs": n_runs,
        "note": "1-share max position; spread cost charged at each flip",
    }


def run(symbol: str, date: str, book_krw: float = 20_000_000) -> None:
    print(f"=== Oracle max PnL — {symbol} {date} ===")
    ts, mid, bid, ask = load_midbidask(symbol, date)
    print(f"ticks (valid session, BIDP1>0): {len(mid):,}")
    print(f"session start→end mid: {mid[0]:,.0f} → {mid[-1]:,.0f} KRW "
          f"(close/open {(mid[-1]/mid[0]-1)*100:+.3f}%)")
    print(f"intraday range: low {mid.min():,.0f}  high {mid.max():,.0f}  "
          f"({(mid.max()-mid.min())/mid[0]*100:.3f}% range)")
    print(f"mean spread: {np.mean(ask-bid):.1f} KRW ({np.mean((ask-bid)/mid)*1e4:.2f} bps)")
    print()

    a = variant_a_raw_mid_sum(mid)
    b = variant_b_taker(mid, bid, ask)
    c = variant_c_dp(mid, bid, ask)

    # Shares that fit in book_krw at avg mid
    avg_mid = float(np.mean(mid))
    max_shares = int(book_krw / avg_mid)
    print(f"avg mid: {avg_mid:,.0f} KRW  → 1M KRW = {int(1_000_000/avg_mid)} shares  "
          f"→ book {book_krw/1e6:.0f}M KRW = {max_shares} shares max")
    print()

    for result in [a, b, c]:
        pnl = result["pnl_per_share_krw"]
        pnl_on_book = pnl * max_shares
        pct_on_book = pnl_on_book / book_krw * 100
        print(f"--- Variant {result['variant']} ---")
        for k, v in result.items():
            if k != "variant":
                if isinstance(v, float):
                    print(f"    {k}: {v:,.3f}")
                else:
                    print(f"    {k}: {v:,}" if isinstance(v, int) else f"    {k}: {v}")
        print(f"    * per-share PnL:   {pnl:>12,.0f} KRW")
        print(f"    * on {book_krw/1e6:.0f}M book (max_shares={max_shares}): "
              f"{pnl_on_book:>15,.0f} KRW ({pct_on_book:+.2f}%)")
        print()

    # Comparison: what fee break-evens at each level?
    # Trades × avg trade value × fee_rate = pnl_on_book
    n_trades = b.get("n_total_trades", 0)
    if n_trades > 0:
        avg_trade_val = avg_mid * max_shares  # per trade
        # For variant B: the break-even fee rate (fraction)
        be_fee_B = b["pnl_per_share_krw"] * max_shares / (n_trades * avg_trade_val)
        print(f"Variant B: break-even fee rate (per fill, of traded value) = {be_fee_B*1e4:.3f} bps")
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="005930")
    p.add_argument("--date", default="20260326")
    p.add_argument("--book-krw", type=float, default=20_000_000)
    args = p.parse_args()
    run(args.symbol, args.date, args.book_krw)
