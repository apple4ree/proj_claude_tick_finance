# Fee-Aware Sizing & Break-Even Cheatsheet

> **Primary consumer**: both `alpha-designer` (brief-realism computation) and `execution-designer` (PT/SL calibration).
> **Focus**: Making sure edge > fee at every bar decision, not just in aggregate.

---

## 0. Core formula

```
Break-even PT  =  (1 / WR) × SL × WR + fee_round_trip
  simplified:  minimum profitable PT = fee_RT / (1 − 2 × loss_freq)
  or:          minimum edge per trade = PT × WR − SL × (1-WR) − fee_RT > 0
```

**Practical shortcut**:
```
Minimum required WR  =  (SL + fee) / (PT + SL)
```

예: PT=300, SL=100, fee=8 bps → min WR = (100+8)/(300+100) = **27%**. Actual WR 이 27% 밑이면 long-run 손실.

---

## 1. Fee structure (Binance 기준, 2026-04 시점)

| Fee type | Binance Spot | Binance USDT Perpetual |
|---|---|---|
| **Taker** | 10 bps / side (default) → 7.5 bps with BNB 25% discount | 5 bps / side → 3.75 bps with BNB |
| **Maker** | 10 bps / side (default) → 7.5 bps with BNB | 2 bps / side → 1.5 bps with BNB |
| **VIP 1+** | maker 2~6 bps, taker 4~9 bps | maker 0~1.6 bps, taker 3~3.6 bps |
| **VIP 9 (MM)** | maker -1 bp (rebate), taker 1.5 bps | maker -1 bp, taker 1.7 bps |

**Round-trip fee (default retail, taker × 2)**:
- Spot BNB discount: **15 bps**
- Perp BNB discount: **7.5 bps**
- VIP 1 perp: **~7 bps**

**기본 프로젝트 가정**: fee_RT = **4 bps** (perp-like) in `/experiment` default. 이는 conservative maker-heavy 또는 VIP 1-2 tier 근사.

---

## 2. When edge is *smaller* than fee — structural dead-ends

Iter1 Qlib CSI500 1min 실험에서 확인:
- 1-hour horizon fwd return mean ≈ 22-43 bps
- Fee 8 bps → ev_bps_after_fee = **-3 ~ -7 bps** (edge가 fee에 잠식)

**Rule of thumb**:
```
If (brief.ev_bps_raw < 2 × fee_RT):
    likely fee-dominated; consider
      - longer horizon (more edge, less fee frequency)
      - passive LIMIT to escape taker fee
      - abandon this signal family
```

---

## 3. Lot size scaling

**흔한 오해**: "lot 10배 키우면 수익 10배". 실제로는 slippage + fee 가 lot size에 scale.

**수식**:
```
per-trade edge after fee = gross_edge_bps − fee_RT − slippage(lot_size)
slippage(lot)  ≈  (walk_book_depth_crossed) / best_ask × 1e4
```

Binance LOB depth 20-level, BTC/USDT 최상위 level 평균 depth ≈ 1-5 BTC. **Lot size 1 BTC 이하면 slippage ≈ 0 bps**. 10 BTC 이상이면 walk-book으로 10+ bps slippage.

**Practical**:
- BTC 개인: lot = 0.01-0.1 BTC (slippage 무시 가능)
- BTC 소형 펀드 (10 BTC per trade): slippage ≈ 5-10 bps 추가 비용
- lot 10 BTC 이상은 TWAP/VWAP 분할 필요

---

## 4. Maker vs taker trade-off

**Taker (MARKET / aggressive LIMIT)**:
- Fee: 4-10 bps
- Fill: 100% immediate
- Adverse selection: low (you crossed the spread)

**Maker (passive LIMIT at bid, wait)**:
- Fee: 0-2 bps (possibly negative rebate)
- Fill: 30-70% (depends on queue position + market movement)
- Adverse selection: **high** — 체결된다는 건 가격이 반대로 움직였다는 증거 (fill after price move → queuer on losing side)

**수식** (passive fill EV):
```
passive_EV = gross_edge − fee_maker − adverse_selection_cost
           ≈ gross_edge − 1bp − 3-10bp  (크립토 1min 기준)
```

Passive가 taker보다 나은 조건:
- gross_edge × fill_rate > taker_edge × 1.0
- 즉 **fill_rate 70% 에서 maker advantage = 4 bps fee savings**, but **adverse selection 5 bps 소실** → net wash 또는 약한 negative.

**언제 passive가 명확히 나은가**:
- Market-making paradigm (둘 다 passive + OBI 선택)
- Very low volatility regime (adverse selection 작음)
- VIP maker rebate 접근 가능

---

## 5. Decision matrix

| Signal type | Fee assumption | Order type | 이유 |
|---|---|---|---|
| Daily horizon (1d) | 4 bps taker OK | MARKET | 1 trade / N days, fee amortizable |
| Hourly (1h) | 4 bps OK | MARKET | Edge typically 20-100 bps, fee 4 bps manageable |
| 15-min / 5-min | 2 bps (VIP) or 0 bps (maker) | Passive LIMIT preferred | Edge 5-20 bps 수준, taker fee 20-40% edge 잠식 |
| Tick / HFT | Maker only (often rebate) | Passive LIMIT with aggressive cancel | Edge 1-3 bps ~ half-spread; taker 4 bps 즉사 |

---

## 6. Quick formulas reference

```
Break-even WR     = (SL + fee) / (PT + SL)
Kelly fraction    = (WR × avg_win - (1-WR) × avg_loss) / avg_win
Min PT            = fee_RT + 2 bp buffer  (lowest PT that has positive EV even at 50% WR)
Fee-to-edge ratio = fee_RT / (brief.ev_bps_after_fee + fee_RT) × 100  (%)
                    > 50% → fee-dominated regime, consider abandonment
```

---

## 7. Anti-patterns

1. **fee를 무시하거나 0 가정** — 특히 ping-pong 설계 시. 4 bps 왕복이면 spread 0.13 bps edge 전략은 **절대 수익 안 남**.
2. **Maker fee 가정 하에 aggressive LIMIT 사용** — aggressive LIMIT은 대부분 taker로 체결. Maker fee 기대했으면 실제로 taker 받음.
3. **Slippage = 0 가정으로 lot 과대 확장** — backtest 수익이 5× 늘었다고 real 5× 아님.
4. **VIP tier 가정으로 기본 실험** — 일반 retail 실험은 default fee로. VIP 실험은 별도 market flag.

---

## 8. How this is used

`alpha-designer` (brief realism 계산):
- `spread_cross_cost_bps`: MARKET entry면 half-spread + half-fee 추가 반영
- `adjusted_ev_bps` 계산 시 fee_RT 이미 brief_ev_bps_raw에서 차감되었는지 확인
- `decision = "reject"` if ev after all costs < 0

`execution-designer` (PT/SL 설정):
- Break-even WR 먼저 계산 → realistic WR 과 비교
- Min PT > fee_RT + buffer
- Lot size 결정 시 slippage 추정
