# KRX H0STASP0 — Usable Columns (for Chain 1 signal design)

Raw CSV: `/home/dgu/tick/open-trading-api/data/realtime/H0STASP0/<YYYYMMDD>/<SYMBOL>.csv`
Cadence: ~100ms periodic snapshot (not event-driven).
Total columns: 62. Chain 1 primitives may reference **only** the columns listed below.

---

## Meta (filter/index only, not signal input)

| Column | Purpose |
|---|---|
| `recv_ts_kst` | timestamp (ISO8601, ms, KST) — used for alignment only |
| `MKSC_SHRN_ISCD` | symbol code |
| `HOUR_CLS_CODE` | session code; filter to `"0"` (regular session) |

## Depth levels (10 × 2 sides)

| Columns | Meaning |
|---|---|
| `BIDP1 … BIDP10` | bid prices level 1..10 (KRW) |
| `ASKP1 … ASKP10` | ask prices |
| `BIDP_RSQN1 … BIDP_RSQN10` | bid quantities (shares) |
| `ASKP_RSQN1 … ASKP_RSQN10` | ask quantities |

## Aggregate book

| Column | Meaning |
|---|---|
| `TOTAL_BIDP_RSQN` / `TOTAL_ASKP_RSQN` | total bid/ask qty across all levels |
| `TOTAL_BIDP_RSQN_ICDC` / `TOTAL_ASKP_RSQN_ICDC` | Δ from previous snapshot (KIS pre-computed). **Primary source for `ofi_proxy`** |

## Trade flow proxy

| Column | Meaning |
|---|---|
| `ACML_VOL` | cumulative traded volume (shares) — diff for tick-level vol_flow |

## Session-phase (ignore in Chain 1)

`ANTC_*` series: anticipated trade price/qty during pre-open auction. Zero in regular session; not used.

---

## Data-quality gates (always applied before feeding to a primitive)

1. `HOUR_CLS_CODE == "0"` — regular session only
2. `BIDP1 > 0 AND ASKP1 > 0 AND ASKP1 > BIDP1` — valid top-of-book
3. For flow primitives: skip first tick of session (no prior snapshot to diff)

---

## Tick size (price granularity, KRX-specific, gradational)

| Price range (KRW) | Tick size |
|---|---|
| < 2,000 | 1 |
| 2,000 – 4,999 | 5 |
| 5,000 – 19,999 | 10 |
| 20,000 – 49,999 | 50 |
| 50,000 – 199,999 | 100 |
| 200,000 – 499,999 | 500 |
| ≥ 500,000 | 1,000 |

Relevant when converting between KRW-denominated and bps-denominated quantities.

---

## Not usable (forbidden by Chain 1 scope)

- Trade-by-trade prints (only ACML_VOL aggregate available — this is a KIS H0STASP0 limitation)
- Order-level (Market-By-Order) depth (KRX does not publish)
- Queue position (we only see aggregate qty per level)
