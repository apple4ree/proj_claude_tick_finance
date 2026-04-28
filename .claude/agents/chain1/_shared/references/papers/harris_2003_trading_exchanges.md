# Harris (2003) — Trading and Exchanges: Market Microstructure for Practitioners

**Citation**: Harris, L., *Trading and Exchanges: Market Microstructure for Practitioners*, Oxford University Press (2003). Esp. Ch.6 (Order-driven markets), Ch.7 (Brokers), Ch.8 (Dealers and market makers).

## Why this matters to our project

Our KRX environment is an **order-driven market** (continuous double auction via LOB). Chain 2's fee_model, order_type choices, and queue dynamics are all instantiations of the general market-microstructure framework Harris lays out. Before claiming anything about why spreads exist, why taker fees are what they are, or how our Chain 2 execution compares to best practice, we need this baseline vocabulary.

## 1. Market types (Ch.6)

| Type | Examples | Key property |
|---|---|---|
| **Order-driven (CDA)** | KRX, Binance spot, NASDAQ | Continuous double auction; all orders visible in LOB |
| Quote-driven (dealer) | NASDAQ OTC bonds, FX | Dealers post 2-sided quotes; trade against them |
| Call-auction | KRX open/close auctions | Batch matching at single clearing price |
| Hybrid | NYSE floor, KRX session boundaries | Mix of CDA + specialist/market-maker |

**For us**: KRX regular session is CDA. Call auctions happen at 09:00 open and 15:30 close (filter by HOUR_CLS_CODE=="0" already excludes these).

## 2. Spread decomposition (Ch.8)

The bid-ask spread compensates market makers for three costs:

```
spread_total = order_processing + inventory_holding + adverse_selection
```

### 2.1 Order processing cost
Fixed per-trade infrastructure cost. For electronic markets this is small (~0.5 bps). Our KRX taker fee 1.5 bps includes this.

### 2.2 Inventory holding cost
Risk of holding unwanted inventory. Scales with volatility σ, holding time T, and risk-aversion γ:
```
C_inventory = γ · σ² · T · q²   (quadratic in inventory q)
```

**For Chain 2 Phase 2.2+**: When we add sizing or market-making, this becomes the dominant cost. Avellaneda-Stoikov 2008 formalizes it (see `avellaneda_stoikov_2008_market_making.md`).

### 2.3 Adverse selection cost
Loss from trading against informed traders. Foundational: Glosten-Milgrom 1985 (see `glosten_milgrom_1985_bid_ask_spread.md`).

Key insight: **market makers widen spreads to compensate for adverse selection**. If traders have probability π of being informed, and informed traders move price by ±Δ:
```
Adverse_selection_component = π · Δ
```

**For us**: `adverse_selection_cost_bps` in our `CostBreakdown` measures this empirically (mid move against our fill). Harris gives the theoretical context.

## 3. Order types (Ch.6.3)

Harris categorizes order types by **price behavior** and **cancel behavior**:

| Order type | Price | Execution |
|---|---|---|
| **Market** | None (accepts any) | Immediate; crosses spread |
| **Marketable limit** | Limit at/inside opposite BBO | Immediate if BBO unchanged |
| **Standing limit** | Limit outside BBO | Queued; fill when market moves |
| **Stop (market)** | Trigger + market | Waits for trigger |
| **Stop limit** | Trigger + limit | Waits + queued |
| **Peg** | Relative to reference | Auto-updates (e.g., BBO pegged) |
| **Iceberg** | Show partial size | Large order with hidden portion |

**For our Chain 2**: We implement MARKET and LIMIT_AT_BID (standing limit). Future extensions:
- **LIMIT_INSIDE_1** = marketable limit (aggressive maker). Partially implemented schema.
- **Iceberg** / **peg** — advanced; beyond current scope.

## 4. Order properties (Ch.6.4)

### Time in force (TIF)
- **IOC** (Immediate-or-Cancel): fill what's possible instantly, cancel rest
- **FOK** (Fill-or-Kill): all-or-nothing immediate
- **GTC** (Good-Till-Cancel): stays in book until user cancels
- **GTX** (Good-Till-Crossing): cancels on self-cross only (hftbacktest default)
- **GTD** (Good-Till-Date): expires at specified time

**For us**: Chain 2 currently has `entry_ttl_ticks` which mimics GTD (cancel after N ticks). Production translation: market-specific TIF flag.

### Minimum quantity
Requires ≥ MinQty to fill. KRX does not have this for retail; Korean institutions use via block trading system.

### Hidden/displayed size
Not applicable to KRX retail (no iceberg support per exchange rules).

## 5. Queue priority rules (Ch.6.5)

Three common rules:

1. **Pure price priority, strict time** (KRX, most Asian): lowest ask / highest bid first; among same-price, earliest order first.
2. **Pro-rata** (some futures): same-price orders fill proportionally to size.
3. **Size-time hybrid**: larger orders get slight priority.

**For Chain 2**: hftbacktest's `risk_adverse_queue_model` assumes strict price-time (conservative for us — retail doesn't get queue jumps). `power_prob_queue_model(α)` allows softer probability-of-fill estimates.

## 6. Tick size and its effects (Ch.6.6)

Tick size = minimum price increment. Effects:

- **Larger tick**: fewer price levels, deeper queues, wider spread in bps
- **Smaller tick**: more price levels, shallower queues, tighter spread

KRX uses **gradational tick sizes** (price-dependent). Our 005930 (~185K KRW) has tick=100 KRW ≈ 5.4 bps.

**Implication**: our minimum realized spread is bounded by tick_size/2 ≈ 2.7 bps. MARKET entry always pays at least this. Maker order bypasses it.

## 7. Fee economics (Ch.7.4)

Brokers charge for:
- **Access fee**: membership with exchange
- **Connectivity**: colocation, drop-copy
- **Commission**: per-trade rate (our taker_fee_bps 1.5)
- **Regulatory fees**: SEC fee (US), TSX fee (Canada); KRX has **증권거래세 0.05% + 농특세 0.15% = 20 bps on sell side** for stocks

### Maker-taker fee model
Many exchanges (NASDAQ, Binance) offer maker rebates:
```
maker_fee < 0 (rebate)    taker_fee > 0 (fee)
```
Incentivizes liquidity provision.

**KRX does NOT have maker rebate** — both maker and taker pay 1.5 bps. This is why KRX 23 bps RT is structurally expensive vs Binance (~8 bps taker, negative maker).

### Cross-market comparison for our project
| Market | Maker | Taker | Sell tax | RT (typical) |
|---|---|---|---|---|
| KRX cash | 1.5 | 1.5 | 20 | **23** |
| NASDAQ retail | ~2 | ~3 | 0 | ~5-10 |
| Binance spot retail | 10 | 10 | 0 | ~10-20 (before VIP discount) |
| Binance futures | 2 | 4 | 0 | ~6 |
| CME futures | ~0.5 | ~0.8 | 0 | ~1.3 |

→ Our raw +12.98 bps signal is net-positive in CME or low-fee crypto-futures markets.

## 8. Connection to our Chain 2 engine

Current `chain2/cost_model.py` implements (4) and (7) correctly (for KRX). Missing ties:
- **Inventory cost** (2.2) — not modeled. When Chain 2 adds multi-lot or MM, need to add.
- **Adverse selection** (2.3) — measured empirically but not modeled ex-ante. Kyle's λ (Kyle 1985) provides ex-ante estimate.
- **Queue priority** (5) — delegated to hftbacktest; our Python-native sim uses 50% bernoulli as placeholder.

## Known caveats

- Harris 2003 pre-dates modern HFT proliferation; some numbers/microstructure claims are out of date. Still foundational for vocabulary.
- KRX-specific quirks (시간외 거래, 예상체결, 2-hour lunch break until 2000) not covered; supplement with `krx_data_columns.md`.
- Maker-taker fee literature has evolved; see Battalio et al. (2016) for updates.
