---
stage: execution
name: baseline_A_042700_obi5
created: 2026-04-17
signal_brief_rank: 2
symbol: 042700
---

# Execution Design: baseline_A_042700_obi5

## Adverse Selection Assessment

**Severity: HIGH.**

Entry is a passive LIMIT BUY at bid. Structural risk: a fill is only granted when the bid is being
consumed — i.e., a seller is aggressively hitting the bid. This is the textbook adverse-selection
scenario. Evidence from prior iteration (strat_20260417_0002): OBI decayed from 0.581 to 0.563
between signal fire and fill confirmation with TTL=30 ticks, confirming the imbalance is transient.

Mitigation: TTL=50 ticks (short enough to discard stale fills) + bid-drop cancel at 2 ticks
(cancels if price moves adversely before fill, protecting from the worst fills).

## Entry Order

- Price: `bid` (passive LIMIT BUY at best bid)
- TTL: 50 ticks — OBI_5 is fleeting (5-level imbalance dissipates quickly). Iteration context
  confirms TTL=30 was too aggressive on fill-rate; 50 is a compromise.
- Bid-drop cancel: 2 ticks — cancel if bid drops 2 ticks (33 bps) from submission level before fill
- Rationale: passive BID entry on a fleeting OBI spike requires tight TTL to preserve signal
  freshness. Prior iteration showed decay within 30 ticks. Bid-drop cancel at 2 ticks filters the
  most adverse fills. This reduces fill rate but improves fill quality.

## Exit Structure

- Profit target: **79 bps** (LIMIT SELL) — exact brief optimal, no deviation
- Stop loss: **33 bps** (MARKET SELL) — **raised from brief's 3 bps**
  - Tick-size constraint: 042700 at ~303,000 KRW, tick_size=500 KRW → 1 tick = 16.50 bps.
    Brief SL of 3 bps falls below the 1-tick floor. No bid level exists at 3 bps below entry.
    The engine will structurally overshoot to 33 bps (2 ticks) regardless of spec value.
    Setting SL=33 bps explicitly matches the physical minimum and eliminates spurious
    invariant violations. Confirmed by lesson_20260417_001 (strat_20260417_0002 sl_overshoot=structural).
  - SL deviation: +1000% from brief's nominal 3 bps. This is a mandatory tick-size correction,
    not a strategic choice. The brief's 3 bps is physically unreachable on this symbol.
- Trailing stop: **enabled**
  - Activation: 25 bps — above round-trip cost (21 bps), gives position time to build momentum
  - Distance: 25 bps from peak — matches effective SL to maintain consistent downside exposure
  - Rationale: exit_mix shows ts=63% — trailing stop is the DOMINANT exit. Disabling it would
    eliminate the primary exit path and force reliance on time-stop exits (suppresses avg_win,
    lesson_20260414_021). Activation at 25 bps ensures trailing only engages when the position
    has cleared round-trip fees. Distance=25 bps is tighter than or equal to SL (33 bps).

## Position & Session

- Lot size: 2
- Max entries per session: 3
- Rationale: n_entry=3797 over 12 IS days = ~316 signals/day. With TTL=50 ticks, many signals
  will cancel. Max_entries=3 accommodates 1-2 TTL cancels before a live fill per session.
  Lot_size=2 amortizes fees without amplifying nominal PnL (lot scaling does not improve edge,
  lesson_20260415_008).

## Fee Math

- Round-trip cost: 21.0 bps (KRX engine standard: 1.5 bps commission × 2 + 18 bps sell tax)
- Break-even WR at PT=79, SL=33 (effective): 33 / (79 + 33) = **29.5%**
- Brief win_rate: **61.63%** — 32 percentage points above break-even. Strong edge margin.
- Required edge above break-even: well-covered. Even if realized WR degrades 20 pp in live,
  the strategy remains above break-even.

## Implementation Notes for spec-writer

1. **SL must monitor `snap.bid_px[0]`, not `snap.mid`.**
   Pattern: `pattern_sl_reference_price_and_per_symbol_spread_gate`.
   Correct implementation:
   ```python
   unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000
   if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5:
       # submit MARKET SELL
   ```

2. **SL guard: `ticks_since_entry >= 5` mandatory.**
   Prevents immediate stop-out at tick-0 post-fill where bid_px[0] has already moved by the fill
   spread. Without this, the first snap post-fill will often show bid below entry_mid by ~spread/2.

3. **Spread gate for 042700 (single-symbol strategy):**
   042700 tick_size=500 KRW, mid~303,000 KRW → floor = 500/303000 × 10000 = 16.5 bps.
   Gate = 16.5 × 1.5 = 24.8 bps. Use `spread_gate_bps = 25.0` as a minimum filter.
   (Single symbol — no per-symbol dict required, but the floor check must still pass.)

4. **Entry time gate:** Block entries before 09:30 KST (lesson_20260415_009: OBI signals are noise
   in opening 30 min) and after 14:50 KST to avoid EOD fill-at-close forced exits.

5. **TTL cancel implementation:** Track `bid_px[0]` at order submission. Cancel if current
   `bid_px[0]` drops >= 2 ticks (33 bps on 042700) before fill.

6. **Trailing stop peak tracking:** Track `peak_mid` since entry. Fire MARKET SELL when
   `(peak_mid - snap.mid) / peak_mid * 10000 >= trailing_distance_bps` AND
   `ticks_since_entry >= trailing_activation_ticks` (however activation is defined in ticks).

```json
{
  "name": "baseline_A_042700_obi5",
  "hypothesis": "OBI(5) >= 0.58 on 042700 indicates short-term buy-side pressure that resolves upward within ~3000 ticks",
  "entry_condition": "obi(5) >= 0.58",
  "market_context": "single symbol 042700, intraday momentum, 09:30-14:50 KST window",
  "signals_needed": ["obi_5"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "momentum",
  "multi_date": true,
  "parent_lesson": "lesson_20260417_001",
  "signal_brief_rank": 2,
  "entry_execution": {
    "price": "bid",
    "ttl_ticks": 50,
    "cancel_on_bid_drop_ticks": 2
  },
  "exit_execution": {
    "profit_target_bps": 79.0,
    "stop_loss_bps": 33.0,
    "trailing_stop": true,
    "trailing_activation_bps": 25.0,
    "trailing_distance_bps": 25.0
  },
  "position": {
    "lot_size": 2,
    "max_entries_per_session": 3
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 1000.0,
    "rationale": "PT held exactly at 79 bps (brief optimal). SL raised from 3 bps to 33 bps (2-tick floor) due to mandatory tick-size constraint: 042700 at ~303,000 KRW has tick_size=500 KRW = 16.5 bps/tick. The brief's 3 bps SL is physically unreachable — no bid level exists between 0 and 16.5 bps below entry. Confirmed by lesson_20260417_001 (strat_20260417_0002): sl_overshoot=structural, bug_pnl=0. Setting SL=33 bps eliminates spurious invariant violations and matches actual exit mechanics. Break-even WR at effective params=29.5%, well below brief WR=61.63%."
  },
  "alpha_draft_path": "strategies/_drafts/baseline_A_042700_obi5_alpha.md",
  "execution_draft_path": "strategies/_drafts/baseline_A_042700_obi5_execution.md"
}
```
