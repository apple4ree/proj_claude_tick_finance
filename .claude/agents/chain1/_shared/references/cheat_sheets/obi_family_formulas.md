# OBI Family — Primitive Formulas

This cheat-sheet defines the **whitelist of Chain-1-permitted primitives** that
any SignalSpec must be composed from. All primitives take one LOB snapshot as
input (see `krx_data_columns.md` for column availability) and return a scalar.

> **Rule**: SignalSpec.primitives_used must be a subset of the names listed
> here. Anything else is rejected at signal-evaluator (stage ②).

---

## Notation

- `B_k`, `A_k` : bid/ask quantity at level k (BIDP_RSQN{k}, ASKP_RSQN{k})
- `Pb_k`, `Pa_k` : bid/ask price at level k (BIDP{k}, ASKP{k})
- `mid = (Pb_1 + Pa_1) / 2`
- `spread = Pa_1 - Pb_1`
- `total_bid = TOTAL_BIDP_RSQN`, `total_ask = TOTAL_ASKP_RSQN`
- Δ-prefix indicates difference from previous tick (requires state)

---

## Static imbalance (level-based)

| Primitive | Formula | Range | Ref |
|---|---|---|---|
| `obi_1` | `(B_1 − A_1) / (B_1 + A_1)` | [−1, 1] | Cont-Kukanov-Stoikov §2 |
| `obi_k` (k ∈ {3, 5, 10}) | `(Σ_{i=1}^k B_i − Σ_{i=1}^k A_i) / (Σ_{i=1}^k B_i + Σ_{i=1}^k A_i)` | [−1, 1] | CKS §2 |
| `obi_total` | `(total_bid − total_ask) / (total_bid + total_ask)` | [−1, 1] | KIS ICDC fields |

## Microstructure-weighted prices

| Primitive | Formula | Unit | Ref |
|---|---|---|---|
| `microprice` | `(A_1·Pb_1 + B_1·Pa_1) / (A_1 + B_1)` | KRW | Stoikov 2018 |
| `microprice_dev_bps` | `(microprice − mid) / mid × 1e4` | bps | Stoikov 2018; ≡ `(spread/2) × obi_1` in bps |
| `vamp_bbo` | `(Pb_1·A_1 + Pa_1·B_1) / (B_1 + A_1)` | KRW | (same as microprice; retained for naming) |

## Flow-based (requires Δ or pre-computed)

| Primitive | Formula | Range | Ref |
|---|---|---|---|
| `ofi_proxy` | `(ΔTOTAL_BIDP_RSQN − ΔTOTAL_ASKP_RSQN) / (\|ΔTOTAL_BIDP\| + \|ΔTOTAL_ASKP\| + ε)` | [−1, 1] | approximation of OFI using KIS `TOTAL_*_RSQN_ICDC` |
| `ofi_cks_1` | `Σ over last N ticks: sign(ΔPb_1) · B_1_new − sign(ΔPa_1) · A_1_new` | unbounded | CKS 2014 proper formulation; stateful |
| `vol_flow` | `ΔACML_VOL` (shares traded between ticks) | ≥ 0 | direct from ACML_VOL |

## Spread/liquidity

| Primitive | Formula | Unit | Notes |
|---|---|---|---|
| `spread_bps` | `(Pa_1 − Pb_1) / mid × 1e4` | bps | Filter feature |
| `book_slope_bid` | `(Pb_1 − Pb_5) / (B_1 + … + B_5)` | KRW/share | Density on bid side |
| `book_slope_ask` | `(Pa_5 − Pa_1) / (A_1 + … + A_5)` | KRW/share | |

## Rolling / standardization (stateful) — **CALLABLE FROM FORMULAS**

These are supported as function-call syntax directly inside `SignalSpec.formula`.
First argument MUST be a whitelisted primitive **name** (not a nested expression).
Second argument MUST be an integer window >= 2.

| Formula syntax | Semantics |
|---|---|
| `rolling_mean(obi_1, 50)` | trailing mean of `obi_1(snap)` over last 50 ticks |
| `rolling_std(ofi_proxy, 100)` | trailing std of `ofi_proxy(snap)` |
| `zscore(ofi_proxy, 300)` | `(x − rolling_mean) / rolling_std` over 300 ticks |
| `rolling_realized_vol(mid_px, 100)` | √Σ(Δmid)² over last 100 ticks — volatility regime proxy (KRW units) |
| `rolling_momentum(microprice_dev_bps, 50)` | `x_t − x_{t−W+1}` — trend indicator over last 50 ticks |

Each unique `(helper, primitive, window)` triple auto-instantiates a state object
in the generated module; no manual state management needed in the formula.

**Composable with arithmetic/comparators**:
- `zscore(obi_1, 200) > 1.5`
- `rolling_mean(ofi_proxy, 50) - 0.3 * obi_5`
- `rolling_realized_vol(mid_px, 100) > 50` (regime filter: high vol)
- `rolling_momentum(microprice, 100) > 0` (uptrend confirmation)

## AND / OR / NOT — 자연어 가능

Formula 엔 Python keyword 외에도 대소문자 무관 `AND / OR / NOT` 자연어 표기 허용:
- `obi_1 > 0.5 AND spread_bps < 10` → 자동으로 Python `and` 로 변환
- `NOT (obi_1 > 0.9)` → `not (...)`

## Logical combinators (for compound signals)

- `AND`, `OR`, `NOT` over boolean primitives (e.g., `obi_1 > 0.5 AND spread_bps < 10`)
- `>`, `>=`, `<`, `<=`, `==` — threshold comparators
- `+`, `−`, `*`, `/`, `abs(·)`, `sign(·)` — arithmetic on scalars

---

## Explicitly forbidden

- Future-referencing values (`mid_{t+k}`, `ACML_VOL_{t+k}`, anything past `t`).
- Position/PnL state (execution layer concern, Chain 2).
- Random numbers (breaks reproducibility).
- External data sources not present in KRX H0STASP0 CSV.

---

## References

- Cont, R., Kukanov, A., Stoikov, S. (2014). *The Price Impact of Order Book Events*. [`../papers/cont_kukanov_stoikov_2014_ofi.md`]
- Stoikov, S. (2018). *The Micro-Price*. [`../papers/stoikov_2018_microprice.md`]
- KRX H0STASP0 column definitions: [`./krx_data_columns.md`]
