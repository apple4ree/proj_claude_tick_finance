# Regime-State Paradigm — Chain 1 v5 (2026-04-27)

**Master document for the new chain 1 backtest semantics.** All agent prompts (signal-generator, signal-evaluator, feedback-analyst, signal-improver, chain2-gate) reference this. Read this first before designing or evaluating specs.

---

## 1. The Core Change

**Before (fixed-H, pre-2026-04-27)**: Every tick where `|formula| > threshold` opens a new trade; close fixed `H` ticks later. Multiple overlapping trades. Fee charged per trade.

**After (regime-state, current)**: `formula > threshold` is a **state indicator** — IN-position while True, FLAT while False. Holding period is variable (signal-driven). Fee charged once per regime (round-trip).

```
            tick i           tick j (signal becomes False)
            │                │
   FLAT ────┤████████████████├──── FLAT
            ↑                ↑
          ENTER             EXIT
        at mid[i]         at mid[j]

   gross_bps_per_regime = (mid[j] − mid[i]) / mid[i] × 1e4 × direction_sign
   fee_per_regime = 23 bps (KRX cash, RT)
   net_bps_per_regime = gross − 23
```

No end-of-session force-close. If signal still True at session close, the regime is **incomplete** and not counted.

---

## 2. Implications for Spec Design

### 2.1 What you optimize
**Maximize: `net = gross_bps_per_regime − 23` (KRX cash)**

`gross_bps_per_regime ≈ (2·directional_correctness − 1) × E[|Δmid| during regime]`

Three levers (orthogonal):
| Lever | What | How |
|---|---|---|
| **A — direction** | regime 동안 가격이 예측 방향으로 움직이는 비율 | primitive 선택 + direction (long_if_pos / long_if_neg) |
| **B — magnitude** | regime 동안 \|Δmid\| 의 기대 크기 | longer holding × higher-vol regime gating × tail selection |
| **C — selectivity** | n_regimes / 365 sessions 의 quality | duty cycle 통제 (5-80% 범위) |

### 2.2 Target ranges (실측 기반 권장)

| Metric | 권장 범위 | 의미 |
|---|---|---|
| **signal_duty_cycle** | **0.05 – 0.80** | 5–80% 시간 ON. Below 5% = 너무 rare; above 80% = buy-and-hold artifact |
| **n_regimes / session** | **5 – 50** | 평균 1 session 당 regime 수. Below 5 = sample 부족; above 50 = flickering 위험 |
| **mean_duration_ticks** | **20 – 5000** | 평균 보유 길이 (2 sec ~ 8 min). Below 20 = flickering; above 5000 = approaching always-on |
| **WR** | **≥ 0.55** | regime 의 directional 정확도 (gross > 0 비율). 0.5 = noise |
| **gross expectancy** | **target ≥ 28 bps** | KRX 23 fee + 5 spread cost = deployable threshold |

### 2.3 Anti-patterns (auto-rejected by feedback-analyst)

```
duty_cycle > 0.95  →  swap_feature  (buy-and-hold artifact — 신호가 거의 항상 ON)
n_regimes / sessions < 1.5  →  loosen_threshold  (signal too rare to validate)
mean_duration_ticks < 5  AND  n_regimes > 100  →  add_filter  (flickering)
```

---

## 3. Hypothesis Template (REQUIRED for v5+ specs)

Every SignalSpec hypothesis MUST include this 3-axis description:

> **"This signal enters position when `<state condition>` and exits when `<inverse condition>` — i.e., the signal indicates `<regime characterization>`. **
> **Expected behavior: duty cycle `~D%`, mean regime duration `~M ticks (~T sec)`, target gross expectancy `~G bps per regime` (vs 23 bps fee floor). **
> **Direction = `<long_if_pos|long_if_neg>` per Category `<A|B1|B2|B3|C>` (cite reference). **
> **Magnitude mechanism: axis A (longer hold), axis B (regime gate `<...>`), axis C (tail selection `<zscore...>`)."**

### Example (good)
> *"Enter long when (obi_1 > 0.5) AND (rolling_realized_vol(mid_px, 100) > 30); exit when either condition fails. Signal indicates 'persistent BBO buy pressure during high-vol regime'. Expected: duty 8–15%, mean duration 60-150 ticks (6-15 sec), target gross +35 bps per regime via axis A (extended hold) + axis B (high-vol concentration). Direction long_if_pos per Category A (BBO pressure, Cont-Kukanov-Stoikov 2014)."*

### Example (bad — auto-rejected)
> *"This will give high WR by combining two indicators."*  
> ❌ No regime characterization, no duty cycle estimate, no fee comparison.

---

## 4. Common Patterns Translated to Regime-State

### Pattern A — Pressure persistence
```
formula: obi_1 > 0.5 AND rolling_realized_vol(mid_px, 100) > 30
direction: long_if_pos
expected: short-medium hold (50–200 ticks), large magnitude in vol regime
```

### Pattern B — Wall reversion
```
formula: zscore(ask_depth_concentration, 300) > 2.5 
direction: long_if_neg  (Cat B1)
expected: hold while wall persists, exit when wall absorbed/removed
```

### Pattern C — Time-of-day regime gating
```
formula: (zscore(obi_ex_bbo, 300) > 2.0) AND is_opening_burst
direction: long_if_pos
expected: opening burst window only — concentrated magnitude
```

### Pattern D — Multi-condition consensus
```
formula: (obi_1 > 0.4) AND (obi_ex_bbo > 0.2) AND (trade_imbalance_signed > 0)
direction: long_if_pos
expected: rare but high-conviction; expect duty 1-3% but high WR
```

---

## 5. What's DEPRECATED

- **`prediction_horizon_ticks`** — schema 필드는 남아있으나 backtest 무시. 옵션으로 ablation 시 미래 사용 가능.
- **Fixed-H mutation directions** — `change_horizon` 더 이상 적용 안 됨. signal_improver 가 알아서 처리.
- **WR-only optimization** — net-PnL (Fix #1) 이 primary, WR 은 보조.
- **Force-close at session end** — regime 이 session 넘으면 그냥 미완료로 drop.

---

## 6. Connection to Other References

- `direction_semantics.md` — direction 결정 framework (long_if_pos vs long_if_neg). 그대로 유효.
- `magnitude_primitives.md` — magnitude axis A/B/C framework. 그대로 유효.
- `time_of_day_regimes.md` — KRX intraday burst regime. axis B 의 lever.
- `formula_validity_rules.md` — primitive whitelist. 그대로 유효.
- `prior_iterations_index.md` — v3/v4 specs (fixed-H interpretation, legacy).

---

## 7. Why This Paradigm

**v3 결과 (fixed-H, 2026-04-26)**: 0/80 spec 이 KRX 23 bps fee 통과 못 함.  
**원인 분석**: 매 tick fire = N trades = N × fee × n_ticks. 같은 mid 움직임을 여러 번 카운트하면서 fee 도 N 번 부과 — statistical artifact.  
**Regime-state 의 효과**: 1 trade per regime, fee per regime, holding period 가변 = real-world trading 의 자연스러운 paradigm.

**현 시점에서의 약속**: v5 가 이 paradigm 하에서 net > 0 인 spec 을 발견할 수 있는가? 측정 중.
