---
date: 2026-04-28 20:10
tone: design
title: Chain 1 의 binary signal premature exit 한계 발견
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

regime-state 패러다임의 작동 방식 (state ∈ {True, False} 에 따라 진입·청산) 을 정리하던 중 사용자 질문: \"근데 신호가 사실 F 가 떴지만 길게 봤을 때는 수익을 낼 수 있는 경우가 있는 거 잖아\".

→ 즉 chain 1 의 binary signal 이 \"잠깐 noise 로 F 가 됐을 뿐\" 인데 즉시 청산해버려 **premature exit** (조기 청산) 이 발생하는 fundamental 한계 식별.

이 한계는 v5/v6 의 \"4-5 bps mid_gross 천장\" 의 한 원인일 수 있음. LLM 이 noise sensitivity 를 줄이려고 rolling_mean smoothing 을 시도하나 — 본질적 해결 X.

## 가설 (Hypothesis)

\"Chain 1 의 binary signal-driven 진입·청산 구조가 noise sensitivity 로 premature exit 을 만들고, 이게 mid_gross 천장의 한 원인. LLM 의 rolling_mean smoothing 시도는 부분 mitigation. 진정한 해결은 hysteresis / min hold time / trailing exit / continuous strength 같은 chain 2 의 execution 영역.\"

검증 (가능한 실험):
- v6 의 best spec (`iter004_durable_book_consensus`, mean_dur 519) 의 청산 시점에서 추가 보유 했을 경우 mid_gross 변화 측정
- 만약 \"청산 후 1-3분 더 보유 시 평균 +3 bps 추가\" 같은 결과면 premature exit 증명

가설 틀리면: smoothing 만으로 해결되는 noise 문제. 즉 fundamental 한계 아님.

## 변인 통제 및 설계 — 분석 차원

이건 \"실험\" 보다는 \"진단\". 그러나 측정 가능한 metric:

- **독립 변수**: 청산 후 추가 보유 시간 (T = 0, 50, 100, 500, 1000 ticks)
- **종속 변수**: \"청산 시점 mid → T 후 mid\" 의 분포
- **통제**: regime-state 의 같은 진입 점, 같은 신호
- **비교 baseline**: T = 0 (현재 즉시 청산)

만약 \"청산 시점 mid 보다 T 후 mid 가 systematically 더 좋다\" 면 premature exit 의 정량 증거.

## 철학 / 선택의 근거

### Chain 1 의 spec language 한계

```python
def signal(snap) -> bool:
    return formula(snap) > threshold

# 단일 formula + 단일 threshold = binary on/off
# 진입 / 청산이 같은 조건의 transition 으로 결정됨
```

이 design 의 장점:
- 검증 가능 (fidelity_checker 가 spec ↔ code 일대일 검증)
- 단순 / 학술적 reproducibility
- Lookahead 방지 쉬움

단점 (이 발견):
- 진입과 청산을 **다른 조건** 으로 분리 못 함
- 진입 후 \"최소 보유 시간\" 강제 못 함
- Continuous strength 표현 못 함

→ **\"단순함 vs 표현력\"** trade-off 의 한 instance.

### Chain 1 vs Chain 2 의 분리 원칙 재확인

CLAUDE.md 의 design 원칙:
- Chain 1: 신호의 알파 자체 (execution = 1 상수)
- Chain 2: 실제 실행 (maker/taker, hold time, stop, trailing, sizing, ...)

→ Premature exit 의 \"진짜 해결\" 은 chain 2 의 영역. Chain 1 안에서는 부분 mitigation (smoothing) 만.

## 다이어그램

### Premature exit 의 상황

```
신호:    F F T T T T T F F F F T T T T F F
                     ↑       ↑              ↑
                     t=2     t=7 (signal F)
                     진입     ↑ 청산 (현재 design)
                              
가격 mid:                     ↘   ↘   ↗   ↗   ↗ ...
                              ↑
                     실제로 잠깐 조정 → 다시 상승

[현재 chain 1 결과]
  진입 t=2 → 청산 t=7
  realized gain: +5 bps (예시)

[만약 추가 보유 했을 때]
  진입 t=2 → 청산 t=14
  realized gain: +15 bps (premature exit 으로 +10 놓침)

→ Binary signal 의 noise sensitivity 가 premature exit 을 만듦
```

### 부분 vs 완전 mitigation

```
[부분 mitigation — chain 1 안에서]
  rolling_mean smoothing
       │
       └─→ formula = rolling_mean(obi_1, 500) > 0.4
           short noise 흡수, 그러나 lag ↑

[완전 mitigation — chain 2 영역]
  Hysteresis     : 진입 임계 ≠ 청산 임계
  Min hold time  : 진입 후 최소 N tick 보유
  Trailing exit  : 진입가 대비 가격 변화 추적
  Continuous strength : binary 가 아닌 sliding scale
```

## 세션 컨텍스트

### 이미 수행하고 분석한 것

- v6 의 \"4-5 bps mid_gross 천장\" saturation 신호
- v3 의 13.32 가 fixed-H over-counting 인공물 진단
- Plan F 의 두 lever (Level 4 + Level 2) 동시 적용 디자인
- regime-state 패러다임의 동작 방식 명확화

### 지금 수행·분석 중

- v6 fresh run (iter_019+ 진행 중)
- 본 progress 의 wiki/flow 기록

### 수행·분석할 예정 — 추측

- v6 종료 → 결과 분석
- net ≤ 0 이면 F (Part A + B 동시) 시작 — Path F 의 표현력 ↑ 가 premature exit 의 부분 mitigation 가능
- Premature exit 의 정량 측정 — v6 의 best spec 의 trace 데이터로 \"청산 시점 + N tick 의 mid 분포\" 분석 가능 (간단한 후속 작업)
- Chain 2 활성화 시 hysteresis / min hold time / trailing exit 우선 구현

## 진행 / 결과

- 진단: chain 1 의 binary signal 이 premature exit 의 구조적 원인
- 부분 mitigation: rolling_mean smoothing (LLM 이 이미 시도, mean_dur 117 → 978 까지 확장)
- 완전 mitigation: chain 2 의 영역 (hysteresis, min hold, trailing exit, continuous strength)
- Wiki concept 신설 후보: `binary-signal-premature-exit-limitation`

## 발견 / 의미

1. **Mid_gross 천장 4-5 bps 의 한 원인** 가능성: noise sensitivity 가 premature exit 을 만들어 알파의 일부 (\"신호가 원래 잡으려던 movement 의 후반부\") 를 놓침.

2. **Path F 의 부분 보완**: Phase 2 의 raw column read 가 \"smoothing + 책 두께 + spread 정상\" 같은 multi-condition AND 로 noise 영향을 줄일 수 있음. 그러나 hysteresis (진입 ≠ 청산 임계) 는 여전히 chain 1 안에서 표현 어려움.

3. **Chain 2 의 우선 항목**: 
   - hysteresis (진입 임계 vs 청산 임계 분리)
   - min hold time (진입 후 N tick)
   - trailing exit (가격 추적)
   - 위 셋이 \"premature exit\" 의 진짜 mitigation lever

4. **Paper-grade finding 가치**: \"binary signal 의 premature exit 한계\" — 다른 LLM-trading framework (AlphaAgent, QuantAgent) 도 비슷한 한계 보일 가능성 있음. Methodology critique 후보.

## 다음 단계

1. v6 종료 후 best spec 의 trace 분석 → premature exit 의 정량 측정 (간단)
2. Wiki concept 등록 + Flow event
3. Path F 의 부분 보완 가능성 명시 (Phase 2 의 raw column 으로 multi-condition AND)
4. Chain 2 의 hysteresis / min hold time 우선 항목으로 향후 task
