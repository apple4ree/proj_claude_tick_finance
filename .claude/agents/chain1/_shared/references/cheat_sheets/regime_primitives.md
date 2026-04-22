# Regime Primitives — 시장 상태 기반 filter / trigger

Block A (2026-04-21) 추가. OBI/OFI 신호가 **언제 더 강한가** 를 판정하거나,
expected |Δmid| 이 큰 구간을 선별할 때 사용.

---

## Whitelist (stateless, single-snapshot)

| Primitive | 반환 | 설명 | 대표 사용 |
|---|---|---|---|
| `mid_px` | float (KRW) | `(bid_px[0] + ask_px[0]) / 2` — 가격 scalar | `rolling_realized_vol(mid_px, 100)`, `rolling_momentum(mid_px, 50)` |
| `minute_of_session` | float [0, 390] | KRX 세션 개장 (09:00 KST) 이후 경과 분 | time-of-day filter |
| `book_thickness` | float ≥ 0 | `TOTAL_BID + TOTAL_ASK` 합산 잔량 | 유동성 regime |

## Whitelist (stateful, 이전 snapshot 필요)

| Primitive | 반환 | 설명 |
|---|---|---|
| `ofi_depth_5` | float | CKS OFI 를 top-5 level 까지 누적 (top-of-book 만 보는 ofi_cks_1 보다 robust) |
| `ofi_depth_10` | float | 동일, top-10 level |

## 파생 신호 예시 (helper 조합)

실시간 regime 지표를 원할 때:

```
# 현재 변동성이 최근 100 tick 대비 높은가?
rolling_realized_vol(mid_px, 100) > 40     # 40 KRW per 100 ticks → high-vol

# 상승 추세 확인
rolling_momentum(mid_px, 200) > 100        # 최근 20초간 mid 상승 ≥ 100 KRW

# 거래 활발도
rolling_mean(vol_flow, 100) > 5            # 평균 거래량 ≥ 5주/tick
```

## 주요 활용 패턴

### 1. Regime filter (AND 절 추가)
```
# 기본 신호 × 변동성 regime
obi_1 > 0.5 AND rolling_realized_vol(mid_px, 100) > 40

# 기본 신호 × 시간대 filter (closing zone)
ofi_cks_1 > 1000 AND minute_of_session > 350

# 기본 신호 × 유동성 filter
obi_total > 0.3 AND book_thickness > 800000
```

### 2. Extreme event trigger
```
# z-score 로 극단치 진입
zscore(ofi_cks_1, 300) > 2.5    # 상위 0.6% (극단 OFI)
```

### 3. Momentum + imbalance ensemble
```
# 추세 + 호가 불균형 둘 다 양수일 때만
obi_1 > 0.4 AND rolling_momentum(mid_px, 50) > 0
```

---

## 시간 기반 filter — KRX 세션 구조

| minute_of_session | 시간 (KST) | regime 설명 |
|---|---|---|
| 0 ~ 15 | 09:00 ~ 09:15 | 개장 직후 변동성 최대, 정보 유입 집중 |
| 30 ~ 330 | 09:30 ~ 14:30 | 안정적 continuous session |
| 350 ~ 380 | 14:50 ~ 15:20 | 마감 전 포지션 정리 |
| 380 ~ 390 | 15:20 ~ 15:30 | 동시호가, 거래 메커니즘 다름 (주의) |

**주의**: 09:00 전 (minute_of_session < 0) 은 음수로 반환되며 이는 pre-open
또는 데이터 오류. 필터에서 `minute_of_session > 0` 추가 권장.

---

## Reference

- Cont-Kukanov-Stoikov (2014) §3.2 — deep-level OFI 의 marginal 정보 가치
- Pereira & Zhang (2017) — "Intraday Seasonality in KOSPI200" — 개장·마감 regime 구분
