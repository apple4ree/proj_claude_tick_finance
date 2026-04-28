---
schema_version: 1
type: plan
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, backtest, maker, spread-capture, post-v5]
refs:
  code:
    - {path: "chain1/backtest_runner.py", symbol: "backtest_symbol_date_regime", confidence: verified}
    - {path: "chain1/_shared/schemas.py", symbol: "BacktestResult", confidence: verified}
  papers:
    - stoikov-2018-microprice
    - cont-kukanov-stoikov-2014
  concepts:
    - fee-binding-constraint
    - capped-post-fee
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-B-maker-spread-capture
status: proposed
trigger: post-v5-completion
priority: high
---

# Path B — Maker Spread Capture (chain 1 backtest 확장)

## 문제

Chain 1 의 현재 backtest (`backtest_symbol_date_regime`) 는 **mid-to-mid execution** — entry/exit 모두 mid 에서 체결. 즉:
- gross_bps = (mid[exit] - mid[entry]) / mid[entry] × 1e4
- spread / fee / queue 효과 0

KRX 현물의 23 bps RT fee 벽 하에서 우리는 mid-to-mid 기준 13 bps (v3 best) 의 신호 천장을 봤음. **그러나 maker 측 (LIMIT_AT_BID 매수 / LIMIT_AT_ASK 매도) 은 spread 절반 만큼의 추가 edge** 가 있음:
- KRX 005930 평균 spread ≈ 5~7 bps
- maker 양쪽 (entry + exit) = +5~7 bps gross 추가 가능
- 단, queue position / cancel risk / adverse fill 고려 필요

이걸 chain 2 로 미루지 말고 **chain 1 backtest 옵션** 으로 추가하면 — LLM 이 "maker-friendly spec" 을 직접 generate 가능.

## 제안 design

**B.1 BacktestMode 확장** — `backtest_runner.py`:
```python
def run_backtest(spec, ..., mode="regime_state", execution_mode="mid_to_mid"):
    # execution_mode ∈ {"mid_to_mid", "maker_optimistic", "maker_realistic"}
```

- `mid_to_mid` (default, 현재): entry/exit at mid
- `maker_optimistic`: entry at touch (BID for long entry, ASK for short entry), exit at touch (ASK for long exit, BID for short exit). Queue position = front. **Always fills**. — 이론적 상한.
- `maker_realistic`: entry at touch, but only fills if **price stays at level for ≥ 1 tick AND opposite side trades through within TTL**. Adverse selection: if mid moves opposite within fill window, fill at unfavorable side.

**B.2 Spread proxy 측정** — backtest 시 매 regime entry/exit 시점의 (BIDP1, ASKP1) 기록:
- spread_at_entry_bps
- spread_at_exit_bps
- maker_gain_entry_bps = spread_at_entry / 2
- maker_gain_exit_bps = spread_at_exit / 2
- 이 값들을 BacktestResult 에 새 필드로 추가

**B.3 BacktestResult schema 확장** — `_shared/schemas.py`:
```python
class PerSymbolResult:
    # 기존 필드 +
    execution_mode: str = "mid_to_mid"
    expectancy_maker_bps: Optional[float] = None  # maker_optimistic 경우 max edge
    expectancy_maker_realistic_bps: Optional[float] = None
    avg_spread_at_entry_bps: Optional[float] = None
    avg_spread_at_exit_bps: Optional[float] = None
    fill_rate: Optional[float] = None  # maker_realistic 경우
```

**B.4 Fee model 확장** — execution_mode 별:
- mid_to_mid: fee = 23 bps (taker 가정)
- maker_optimistic: fee = 3 bps (maker only, 0.015% × 2) + sell tax 20 bps = 23 bps (KRX 매도세는 maker/taker 구분 없음)
- → KRX 의 사실: **sell tax 가 maker 효과를 거의 상쇄**. 그러나 net = gross + spread_capture - fee = (gross + 5 bps) - 23 bps 라면 net 임계 8 bps 로 낮춰짐.

**B.5 Smoke test** — v5 best 5 spec 을 maker_optimistic 모드로 재backtest. Net > 0 spec 출현 가능성 측정.

## 구현 단계

```
B.1  execution_mode 인자 추가 + dispatch 분기            (1h)
B.2  spread 측정 코드 (entry/exit 시점 ASKP1-BIDP1)      (1h)
B.3  BacktestResult schema 확장                          (30 min)
B.4  fee model 확장 (FEE_BPS_RT_MAKER 상수 추가)         (30 min)
B.5  maker_optimistic 모드 코드                          (2h)
B.6  maker_realistic 모드 코드 (queue + adverse)         (4h, 복잡)
B.7  smoke test on v5 best 5 spec                        (30 min)
B.8  signal-generator AGENTS.md 에 maker-mode 안내 추가  (30 min)
─────
total ~10h, B.6 가 가장 무거움
```

## 성공 기준

1. **Smoke test (B.7)**: v5 best 5 spec 중 **≥ 1 spec** 이 maker_optimistic 모드에서 net > 0 (gross + spread_capture - fee_maker_with_tax > 0).
2. **schema 호환**: 기존 fixed-H run / regime-state run 결과가 변경 없이 재현 (mid_to_mid default).
3. **regression 0**: v5 best spec 의 mid_to_mid 결과 numeric 동일.

## 의존성 / ordering

- **선행**: v5 종료
- **무관**: Path A 와 병렬 가능 (서로 다른 layer)
- **권장 순서**: A → B → C/D → E (calibration → execution → empirical → agent)
- **충돌 가능**: Path E 의 query_spread_capture tool 이 B 의 spread proxy 출력을 사용 — B 가 먼저 끝나면 E 의 1 tool 자동 활성화

## 위험 / blocker

1. **Sell tax 의 mechanical 한계**: KRX 매도 0.20% 가 maker/taker 무관 → maker capture 의 절반 (long position 의 sell side) 이 무력화. 실제 net 개선폭은 spread/2 ≈ 2.5~3.5 bps 만 — fee floor 아직 멀음.
2. **maker_realistic 의 queue model 구현 난이도**: hftbacktest 의 RiskAdverseQueueModel 은 chain 2 용. Chain 1 에서는 단순 heuristic (front-of-queue + 50% fill rate) 으로 시작 권장.
3. **Adverse selection bias**: maker fill 은 내 신호 반대로 갈 때 더 잘 체결됨. naive maker_optimistic 은 이 효과 무시 → over-optimistic. 그래서 B.6 (maker_realistic) 이 진짜 critical.
4. **LLM 이 maker-spec 으로 over-fit 위험**: gross 0 이지만 spread capture 만으로 net > 0 인 spec 을 추구할 수 있음 — 신호 자체에는 alpha 없음. AGENTS.md 에 명시 필요.

## 예상 영향

- B.5 (maker_optimistic) 만으로도 net 임계 8 bps → v5 best 3.44 bps 와의 gap 5 bps 로 줄어듦
- 만약 maker_realistic 까지 + 신호 개선 (Path A/E) 결합으로 net > 0 spec 발견 = **프로젝트의 첫 deployable 신호**
- Chain 2 의 spread_capture paradigm 을 chain 1 단계에서 부분 미리보기 가능

## 미정 사항

- maker_realistic 의 fill rate 모델: 단순 (always fill) vs queue position vs hftbacktest borrow
- KRX 매수측 (BIDP1 post 후 ASKP1 트레이드 까지 대기) 의 1-tick TTL 적정 — too short = 0%, too long = adverse selection
- BacktestResult 의 execution_mode 별 결과를 1개 spec 안에 multi-row 로 담을지, 별도 spec ID 로 분리할지 (전자 권장)
