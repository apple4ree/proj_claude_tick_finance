# Lee & Ready (1991) — Inferring Trade Direction from Intraday Data

**Citation**: Lee, Charles M. C. and Ready, Mark J., "Inferring Trade Direction from Intraday Data," *Journal of Finance* 46(2), 733–746 (1991).

## Problem Addressed

Equity exchanges pre-decimalization (and most Asian markets today, including KRX) publish **trade prints** and **BBO quotes** but rarely a clean buy/sell-initiated flag. Researchers must infer the initiator from the publicly-observable data. This classification matters for measuring:
- Informed vs uninformed flow
- Price impact and adverse selection
- Order flow imbalance beyond pure quote state (OFI)

## The Algorithm (Lee-Ready Tick Rule)

For trade `T_t` printed at price `P_t`:

1. **Quote rule**: if `P_t > mid_t` → buyer-initiated; if `P_t < mid_t` → seller-initiated.
2. If `P_t == mid_t` (trade at midpoint), fall back to **tick rule**:
   - `P_t > P_{t-1}` → uptick → buyer-initiated
   - `P_t < P_{t-1}` → downtick → seller-initiated
   - `P_t == P_{t-1}` → unchanged, inherit prior classification (zero-tick rule)
3. Their empirical verification against TAQ+ITCH ground truth: ~85% classification accuracy.

## KRX Adaptation (used in `trade_imbalance_signed`)

The KRX H0STASP0 feed gives us a **pure book feed**: no trade prints per tick — only `ACML_VOL` (cumulative session volume). At each 100 ms snapshot we can compute `ΔV = ACML_VOL_t − ACML_VOL_{t-1}`, but we do **not** know the trade price. We only know the pre/post book state.

We therefore apply a **mid-based tick rule** (degenerate form of Lee-Ready):

```
if mid_t > mid_{t-1}:     signed = +ΔV   (prices rose → buyer-initiated)
elif mid_t < mid_{t-1}:   signed = −ΔV
else:                     signed = 0     (unclassified; conservative)
```

This is less accurate than the full quote+tick rule (we lose trade-price info), but unbiased at the population level and good enough for imbalance signals when smoothed.

## Relevance to Chain 1

- OFI captures **quote-state mutations** (queue up/down).
- Trade-flow (signed `ΔV`) captures **realized transactions** — the more decisive information event.
- Empirically, OFI and signed trade flow are **correlated ≈ 0.6** (stock-specific), so they carry overlapping but non-identical information.
- Smoothed `zscore(trade_imbalance_signed, 300)` tends to outperform `zscore(ofi_proxy, 300)` at horizons > 10 ticks because it excludes phantom OFI from cancel storms.

## Known Caveats

- **Trade-at-mid ambiguity**: when mid is unchanged the sign is 0; ~20% of ticks on KRX mid-day. Loses signal but is unbiased.
- **Small-trade contamination**: HFT iceberg executions can show as small ΔV with rapidly-changing mid — classification gets noisy.
- **Opening auction**: first 30 s of session have anomalous ΔV spikes with mid moving discontinuously. Use `minute_of_session > 1` as a guard.
