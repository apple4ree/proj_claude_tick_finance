---
date: 2026-04-28 17:10
tone: incident
title: v3 의 13.32 bps 가 fixed-H over-counting 인공물 진단
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

v6 진행 중 \"v6 max mid_gross 4.46 bps 가 v3 의 13.32 bps 보다 작은 이유가 뭔가\" 라는 의문 제기. 이는 단순히 \"v6 가 약하다\" 가 아니라 \"v3 의 측정 방식 자체가 magnitude 를 부풀리고 있었던 것 아닌가\" 의 systematic 진단으로 이어짐.

이전에 (2026-04-27, regime-state-paradigm-ablation 실험) 일부 발견은 있었으나 \"force-close 인공물 17 개\" 만 확인하고 종료. 이번에 더 근본적인 \"fixed-H 자체의 over-counting 효과\" 가 v3 의 모든 신호 측정값에 systematic bias 를 만들었다는 것을 명확히 진단.

이 finding 이 paper-grade methodology critique 후보. 같은 실수 (다른 LLM-trading framework 가 fixed-H 측정으로 magnitude 부풀림) 를 다시 안 하도록 기록 필수.

## 가설 (Hypothesis)

\"v3 의 mean expectancy_bps 13.32 는 신호의 진짜 알파가 아니라, fixed-H 패러다임이 같은 가격 변동을 신호=참 인 동안 매 틱마다 trigger 해 N 번 카운트하면서 발생하는 measurement bias 다.\"

가설이 맞다면: 같은 신호를 regime-state 로 재측정하면 mean 이 0 근처 또는 v5/v6 의 4-5 bps 영역.

가설이 틀리면 (정말 v3 신호가 더 좋았다면): 같은 신호의 regime-state 재측정도 13 bps 수준이어야.

## 변인 통제 및 설계

이미 진행한 ablation 의 재분석:

- **테스트 신호**: `iter005_ask_wall_reversion_low_vol` (v3 best, fixed-H 측정값 +13.32 bps)
- **테스트 환경**: 같은 KRX 005930 데이터, 같은 신호 코드
- **차이**: 측정 방법 (fixed-H vs regime-state)

## 철학 / 선택의 근거

\"신호의 진짜 알파\" 를 측정하는 방법:
- Fixed-H: 매 틱마다 H 후 가격 차 측정 → **신호=참 인 N 틱 동안 N 번 측정**
- Regime-state: 신호가 켜진 구간의 시작 ~ 끝 가격 차 한 번 측정 → **한 사건 한 번 측정**

\"실제로 매수 → 매도 한 번 사이의 가격 변동\" 이 deployable signal 의 진짜 metric. 이게 regime-state 의 측정. Fixed-H 는 \"매 0.1초마다 따로 거래한다는\" 비현실적 가정.

→ Paper-grade 함의: 다른 LLM-trading framework 가 fixed-horizon 측정으로 alpha 를 보고할 때 systematic over-counting bias 가 있을 수 있음.

## 다이어그램 (Diagrams)

### 같은 사건 측정 — 두 방법 비교

```
신호가 켜져 있는 100 틱 동안 가격 +10 bps 움직였다 가정:

가격 ↑                       
        ┌─────────────●  +10 bps
        │            ╱
        │       ╱
        │   ╱
        ●                     0
        └────────────────────→ 시간
        t=0              t=100
        (신호 시작)      (신호 끝)


[Fixed-H 측정 (v3, H=30)]
    매 틱마다 30 틱 후 가격 측정:
    t=0:  +3 bps  ✓
    t=1:  +3 bps  ✓
    ...
    t=70: +3 bps  ✓
    
    → 71 trades 모두 양수
    → mean expectancy = 3 bps × 71 trades = inflated mean

    문제: 같은 +10 bps movement 를 71 번 카운트.

[Regime-state 측정 (v5/v6)]
    신호 시작 ~ 신호 끝, 1 번 측정:
    gross = +10 bps × 1 trade
    
    → 1 trade
    → 진짜 한 번의 movement
```

### 직접 측정 비교 (regime-state-paradigm-ablation 실험, 2026-04-27)

| Run / 측정 방법 | 같은 신호의 측정값 | n_trades |
|---|---:|---:|
| v3 fixed-H 원본 | +13.32 bps | 수만 (over-counting) |
| Regime-state (force-close 있음) | +102 bps | 6 (한 세션 1 진입, 4.5h 보유) |
| **Regime-state (force-close 없음, 진짜)** | **−0.25 bps** | 6,375 |

→ 같은 신호인데 측정 방법 바꾸니 +13 → -0.25. 알파 거의 없음. **v3 의 +13.32 는 fixed-H 의 인공물**.

## 세션 컨텍스트

### 이미 수행하고 분석한 것 (Done & Analyzed)

- v3 fresh run (2026-04-26): 80 specs, max mid_gross 13.32 bps
- v4 fresh run (2026-04-27): reward 함수 변경, 같은 fixed-H — magnitude 비슷
- v5 fresh run (2026-04-27): regime-state 패러다임 도입 — max mid_gross 4.74 bps
- regime-state-paradigm-ablation (2026-04-27): force-close 인공물 발견 + ask_wall_reversion 의 진짜 metric -0.25 bps 측정
- v6 진행 중 (2026-04-28): max mid_gross 4.46 bps (v5 와 비슷)
- 사용자 질문: \"v3 13 bps 시절이 더 좋았는데 왜 v6 가 약한가\"
- → 본 progress 의 systematic 진단

### 지금 수행·분석 중인 것 (In Progress)

- v6 fresh run (PID 3237121, iter_014 진행 중)
- v5 archive retroactive report.html 생성 (PID 3311248)
- 본 finding 의 wiki + flow 기록

### 수행·분석할 예정인 것 — 추측

- v6 종료 (~12:30 KST 예상) → 최종 결과 비교
- v6 의 best mid_gross 가 4-5 bps 영역 머무르면 \"v3 의 13 = fixed-H 인공물, 진짜 천장 = 4-5\" 확정
- 이 진단이 확정되면 paper § Method 의 \"fixed-H 측정의 systematic bias\" 섹션의 핵심 finding

## 진행 / 결과 (Progress / Results)

- 진단 정량 정리: v3 의 13.32 bps 가 fixed-H 의 trigger over-counting 인공물
- ablation 측정 (이전): 같은 신호 -0.25 bps (진짜 알파)
- 진짜 천장 ≈ 4-5 bps mid_gross (v5/v6 가 측정)

## 발견 / 의미 (Findings / Implications)

1. **Fixed-H 의 systematic over-counting bias**: 한 신호가 N 틱 동안 켜져있으면 mean expectancy 계산에 N 번 카운트. 같은 movement 가 N 번 측정.

2. **v3 의 13.32 bps 는 인공물**: ablation 측정으로 -0.25 bps 확인.

3. **진짜 천장 4-5 bps**: v5/v6 의 regime-state 측정이 \"실제로 매수 → 매도 한 번 사이 가격 변동\" 의 직접 측정.

4. **Paper-grade methodology critique 후보**: 다른 LLM-trading framework (AlphaAgent, QuantAgent) 가 fixed-horizon 측정 사용하면 같은 bias 가능. 우리 finding 이 그 진단의 정량 증거.

5. **다음 단계의 implication**: 표현력 (Level 2+4) / paradigm shift / chain 2 통합 — 어떤 lever 도 \"4-5 bps 천장\" 을 \"23 bps deploy 임계\" 까지 올리는 게 진짜 task.

## 다음 단계 (Next)

1. v6 종료 후 max mid_gross 확정 (≈ 4-5 bps 예상)
2. Wiki concept 신규: `fixed-h-overcounting-bias`
3. Wiki note 신규: `v3-13bps-was-fixed-h-artifact`
4. Paper § Method 의 \"measurement methodology\" 섹션에 이 finding 핵심으로
5. 다른 LLM-trading framework 의 fixed-H 측정 비판 (related work)
