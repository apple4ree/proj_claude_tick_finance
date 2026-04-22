# Fee Scenarios — Chain 2 후보 평가 시 cost 가정

CLAUDE.md §Chain 2 Backtest Engine (4) Fee 테이블 과 일치. 선물 / ETF 는 제외 (2026-04-20 결정). **Cross-market 시나리오(예: crypto) 는 해당 시장 데이터로 재측정하지 않은 한 사용 금지** (category error 방지, 2026-04-21).

---

## 지원 시나리오 — KRX 데이터 run 전용

| ID | RT fee (bps) | 구성 | 비고 |
|---|---|---|---|
| `krx_cash_23bps`              | 23.0 | maker 1.5 + taker 1.5 + sell_tax 20.0 (SELL side) | KRX 현물 소매. 실제 배포 목표. |
| `hypothetical_low_fee_5bps`   | 5.0 | maker 2.5 + taker 2.5 | 가상 시나리오. maker 리베이트 도입 or 저수수료 venue 가정. 연구용 참조 지표. |

---

## 시장-시나리오 쌍 규칙 (엄격)

Signal 은 **측정된 시장에서만** 배포 가능. 따라서:
- Chain 1 을 **KRX 데이터** 로 돌렸다면: `krx_*` scenario 만 평가 가능
- Chain 1 을 **crypto LOB 데이터** 로 돌렸다면 (별도 adapter + backtest_runner 확장 필요): `crypto_*` scenario 만 평가 가능

signal-generator + backtest_runner 가 현재 KRX 전용이라, Chain 2 gate 도 기본으로 KRX 시나리오만 사용한다.

---

## 계산 규약

- `fee_rt_bps` = round-trip (entry + exit) 총 수수료
- `half_rt_bps = fee_rt_bps / 2` — 단방향 추정치 (fee_absorption_ratio 산출 시)
- `expectancy_post_fee_bps = expectancy_bps_raw − fee_rt_bps`
- 음수 면 해당 scenario 에서 거래할수록 손실 → G3 hard-fail

---

## 확장 규약

새 scenario 추가 시:
1. 이 파일에 entry 추가
2. `chain1/agents/chain2_gate.py` 의 `FEE_SCENARIOS` dict 에 동일 entry 추가
3. `.env.example` 에 예시 값 포함
4. CLAUDE.md Chain 2 Backtest Engine (4) 테이블 동기
