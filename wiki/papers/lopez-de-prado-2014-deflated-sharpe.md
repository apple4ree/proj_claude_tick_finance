---
schema_version: 1
type: paper
created: 2026-04-27
updated: 2026-04-27
tags: [statistics, multiple-testing, deflated-sharpe]
refs:
  code:
    - {path: "chain1/statistics.py", symbol: null, confidence: inferred}
  papers: []
  concepts:
    - cite-but-fail
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
authors: [Marcos López de Prado]
venue: Journal of Portfolio Management
year: 2014
---

# López de Prado (2014) — The Deflated Sharpe Ratio

**Citation**: López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality". *Journal of Portfolio Management* 40(5).

## TL;DR

다수의 backtest 후 max Sharpe 를 보고하는 standard practice 가 **selection bias + non-normal returns + autocorrelation 으로 systematically Sharpe overstate**. DSR (Deflated Sharpe Ratio) 가 이를 numerically correct.

## 핵심 problem

```
True Sharpe = 0 인 spec 100 개 backtest
   → max(observed Sharpe) ≈ 2.42  (E by formula)
   → "winning spec 발견했다!" 라고 잘못 결론
```

세 가지 distortion source:
1. **Selection bias** — max of M random variables is positively biased
2. **Non-normal returns** — fat-tail, skew (microstructure 특히 심함)
3. **Autocorrelation** — overlapping holding period 시 SE underestimate

## DSR formula (간략)

```
DSR(SR) = Φ(SR_adjusted)

SR_adjusted = (SR - E[max SR | null]) / SE(SR)

with corrections for skewness, kurtosis, and effective sample size.
```

선정된 spec 의 DSR > 0.95 이면 statistical significance 보장.

## 우리 framework 와의 관계

### v3 / v4 / v5 의 multiple-testing context

- v3: 100 spec 제안, 80 backtested → top spec 의 measured Sharpe 는 selection bias 영향
- 우리는 Sharpe 보다 expectancy_bps 사용 — 같은 distortion 적용
- **fee 통과 spec 0/80 이라 selection bias 의 direction 무관 (전부 fail)**

→ 만약 v5 에서 일부 spec 이 fee 통과하면 DSR check 필수.

## 우리가 해결해야 할 multi-testing 문제

`chain1/statistics.py` 에 BH-FDR / DSR / PBO 함수 일부 구현됨.

| Method | 사용 시점 |
|---|---|
| **DSR** (Lopez de Prado 2014) | top spec 의 Sharpe 의 selection-bias 보정 |
| **BH-FDR** (Benjamini-Hochberg 1995) | multiple spec 동시 평가 시 false discovery rate 통제 |
| **PBO** (Bailey & Lopez de Prado 2014) | backtest overfitting probability 측정 |

## 인용 우선순위

⭐⭐ **§Method (statistical robustness)**:
- "Following López de Prado (2014), we apply DSR adjustment to the top spec's Sharpe to correct for selection bias..."

⭐ **§Discussion (limitations)**:
- "Our raw expectancy_bps numbers are not selection-bias-corrected..."

## v5 결과 분석 시 적용 권장

만약 v5 가 fee-passing spec 발견하면:
1. 그 spec 의 raw Sharpe 계산
2. DSR adjustment (n_trials = 100)
3. BH-FDR 로 multiple comparison correction
4. 최종 conclusion 의 statistical significance 보고

## Connection

- `chain1/_shared/references/papers/lopez_de_prado_2014_deflated_sharpe.md` — full summary (existing)
- BH-FDR / PBO 와 자매 paper

## Status

- Existing reference
- v5 결과 분석 시 적용 (currently pre-result)
