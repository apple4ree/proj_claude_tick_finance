---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, paradigm, measurement-failure]
refs:
  code:
    - {path: "chain1/backtest_runner.py", symbol: "backtest_symbol_date_regime", confidence: inferred}
  papers: []
  concepts:
    - regime-state-paradigm
    - buy-and-hold-baseline
  experiments:
    - exp-2026-04-27-regime-state-paradigm-ablation
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
---

# Force-Close Artifact

Backtest 측정 결함의 한 종류 — **session 종료 시점의 강제 청산** 이 "거의 항상 ON 인 신호" 의 가짜 deployable metric 을 generate 하는 현상.

## Definition

```
session 동안 signal 이 거의 항상 True (duty > 0.95)
                ↓ force-close at session end
1 regime / session = entire-session buy-and-hold
                ↓
gross_bps = (mid_close − mid_open) ≈ 일중 |return|
                ↓
random sample 의 mean → 일중 변동성 측정 (alpha 아님)
```

→ "Signal 의 alpha" 가 아니라 "시장의 일중 random walk" 측정. directional 정확도 (WR) 는 0.5 부근, magnitude 만 큼 (KRX 005930 약 100 bps/일).

## v3 ablation 의 발견 사례 (2026-04-27)

Standalone regime-state ablation (3 sym × 2 dates = 6 sessions):
- 14 spec 이 모두 동일 패턴: n_regimes=6 (정확히 1/session), mean +102.57 bps, WR 0.5, mean_duration ≈ 4시간 30분
- 처음에 17/80 deployable 결과로 보였으나 정밀 분석에서 14가 force-close artifact

iter000_ask_wall_reversion 의 force-close 제거 후 실측:
- n_regimes=6375 (1000× 차이)
- duty=0.129
- mean -0.25 bps
- → 진짜 메트릭은 not deployable

## Why force-close generates this artifact

Signal 이 session 첫 tick 에 fire → 마지막 tick 까지 지속:
1. 매 session 마다 1 entry, 1 force-close exit
2. n_regimes = n_sessions (constant)
3. gross 가 random walk 의 일중 변화량
4. mean across sessions 이 시장 평균 |return| 에 수렴 (KRX large cap ≈ 100 bps)

## Mitigation

**2026-04-27 chain 1 design choice**: end-of-session force-close 제거.

```python
# Before:
if in_position at session_end:
    close at mid[-1]  # ← artifact 발생

# After (2026-04-27):
if in_position at session_end:
    discard incomplete regime  # ← clean detection
```

**효과**: 신호가 항상 ON 이면 n_regimes = 0 이 되어 sanity check (`n_regimes/sessions < 1.5`) 가 자동 trigger. 진짜 buy-and-hold 와 noisy signal 의 구별이 더 sharp.

## Detection criteria (post-fix)

```python
if signal_duty_cycle > 0.95:    # 거의 항상 ON
    return "swap_feature"        # buy-and-hold artifact
```

이 trigger 가 force-close 제거 후의 정상 detection.

## Related concepts

- `regime-state-paradigm` — measurement framework
- `capped-post-fee` — paradigm-orthogonal fee constraint
- (`buy-and-hold-baseline` — 향후 추가 가능)

## Paper relevance

- §Method 의 "measurement design choices" 에 명시
- §Discussion 에서 "measurement artifact taxonomy" 의 구체적 instance
- compositional-fragility 의 한 instance — backtest mechanism 의 design choice 가 outcome distribution 을 비대칭하게 왜곡

## Status

- 2026-04-27 식별 + remediation
- v5 paradigm 의 일부로 통합 (chain1/backtest_runner.py)
