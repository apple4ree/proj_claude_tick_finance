# Signal Diagnostics

> **Primary consumer**: alpha-critic
> **Secondary consumers**: feedback-analyst
> **Trigger condition**: WIN/LOSS bucketing 분석 시 (항상)
> **Companion references**: `mean_reversion_entry.md` §2 (iter1 진단 예시)
> **Status**: stable

---

## 0. Core insight

**alpha-critic은 "signal looks weak" 같은 정성 서술 대신 정량 지표 5개를 고정 순서로 진단한다.**

**해결할 failure mode**: ad-hoc judgement → feedback의 재현성 0. 같은 결과에 대해 iter마다 다른 결론 → 전략 개선 방향 수렴 불가.

**실측 근거**: iter1–3 alpha_critique.md 검토 결과, 3개 중 2개가 "신호가 약해 보입니다" 단독 서술. selectivity / capture_pct 미계산으로 execution lever와 alpha lever 혼동.

---

## 1. Diagnostic checklist (고정 순서)

alpha-critic은 반드시 아래 순서로 진행. **순서 변경 및 생략 금지.**

```
Step 1. Selectivity          → §2
Step 2. Hit-rate vs Edge     → §3
Step 3. Regime-dependency    → §4
Step 4. MFE/MAE gap          → §5
Step 5. Cross-symbol consistency → §6
```

각 step 결과를 수치와 함께 기록 후 §8 Verdict로 종합.

---

## 2. Selectivity

**수식**:
```
entry_pct = n_entry / n_bars × 100   (%)
```

**Python snippet**:
```python
def selectivity(n_entry: int, n_bars: int) -> float:
    return n_entry / n_bars * 100 if n_bars > 0 else 0.0

# 판정
pct = selectivity(len(roundtrips), total_bars)
if pct > 5.0:
    verdict = "too_frequent — signal random-like"
elif pct < 0.1:
    verdict = "too_sparse — statistically thin"
elif 0.5 <= pct <= 3.0:
    verdict = "recommended range"
else:
    verdict = "acceptable"
```

**When to use**: 모든 분석 시작 전 (Step 1 항상)
**When NOT to use**: 없음
**Calibration**: 권장 0.5–3.0%. bar 전략 기준. tick 전략은 별도 기준 필요

| entry_pct | 판정 | 조치 |
|-----------|------|------|
| > 5% | noise 의심 | threshold 강화, confirmation 추가 |
| 0.5–5% | 권장 구간 | 유지 |
| 0.1–0.5% | 희박 — 주의 | n 확인 후 통계 해석 |
| < 0.1% | thin | 결론 유보 |

---

## 3. Hit-rate vs Edge decomposition

**수식**:
```
total_edge_bps = WR × avg_win_bps - (1 - WR) × avg_loss_bps
payoff_ratio   = avg_win_bps / avg_loss_bps
```

**Python snippet**:
```python
import numpy as np

def edge_decompose(pnl_bps: list) -> dict:
    arr = np.array(pnl_bps)
    wins   = arr[arr > 0]
    losses = arr[arr <= 0]
    wr         = len(wins) / len(arr) if len(arr) > 0 else 0.0
    avg_win    = float(wins.mean())  if len(wins)   > 0 else 0.0
    avg_loss   = float(abs(losses.mean())) if len(losses) > 0 else 0.0
    total_edge = wr * avg_win - (1 - wr) * avg_loss
    payoff     = avg_win / avg_loss if avg_loss > 0 else float("inf")
    return {"wr": wr, "avg_win": avg_win, "avg_loss": avg_loss,
            "total_edge": total_edge, "payoff_ratio": payoff}
```

**When to use**: Step 2 (항상)
**When NOT to use**: n < 20 — 추정치 신뢰 불가. "샘플 부족" 명시 후 유보

| WR | payoff | 결론 | 조치 |
|----|--------|------|------|
| > 55% | < 1.0 | payoff 비대칭 | execution lever (exit 조정) |
| < 40% | > 2.0 | right-tail 의존 | 정상 |
| 고 + 고 | — | 데이터 누수 의심 | look-ahead 체크 |
| 저 + 저 | — | signal edge 없음 | alpha lever (abandon 검토) |

---

## 4. Regime-dependency

**수식**:
```
regime_labels = pd.qcut(symbol_returns, 3, labels=["bear","neutral","bull"])
per_regime_wr = trades.groupby(regime_label)["win"].mean()
```

**Python snippet**:
```python
import pandas as pd

def regime_dependency(symbol_returns: pd.Series,
                      trade_df: pd.DataFrame) -> pd.DataFrame:
    """
    trade_df: columns = [entry_date, win(bool)]
    symbol_returns: index = date
    """
    regime = pd.qcut(symbol_returns, 3, labels=["bear", "neutral", "bull"])
    trade_df = trade_df.copy()
    trade_df["regime"] = trade_df["entry_date"].map(regime)
    result = trade_df.groupby("regime")["win"].agg(["mean", "count"])
    result.columns = ["wr", "n"]
    return result
```

**When to use**: Step 3 (항상)
**When NOT to use**: per-regime n < 5 — 결론 유보
**Calibration**: 특정 regime WR > 60% but others < 40% → regime gate 권장 (`trend_momentum_entry.md §2`)

---

## 5. MFE/MAE gap (capture_pct)

**수식**:
```
capture_pct = realized_bps / MFE_bps × 100   (%)
```

**Python snippet**:
```python
def capture_analysis(realized: list, mfe: list) -> dict:
    import numpy as np
    r, m = np.array(realized), np.array(mfe)
    valid = m > 0
    cap = np.where(valid, r[valid] / m[valid] * 100, np.nan)
    return {
        "avg_capture_pct": float(np.nanmean(cap)),
        "median_capture_pct": float(np.nanmedian(cap)),
        "avg_mfe_bps":  float(m.mean()),
        "avg_realized": float(r.mean()),
    }

# analysis_trace.md의 per-RT MFE 필드 파싱 후 입력
```

**When to use**: Step 4 (항상)
**When NOT to use**: MFE 데이터 없는 경우 — 엔진 설정에서 `track_mfe=true` 확인
**Calibration**: avg_capture_pct < 50% → exit 문제. `exit_design.md` 참조

| capture_pct | 진단 | primary lever |
|-------------|------|---------------|
| < 50% | exit 너무 이름 or SL 너무 타이트 | execution |
| 50–80% | 양호 | — |
| > 80% | exit OK, 신호 재검토 | alpha |

---

## 6. Cross-symbol consistency

**수식**:
```
wr_std      = std(per_symbol_wr)
rank_corr   = Spearman(symbol_rank_by_wr, symbol_rank_by_ev)
```

**Python snippet**:
```python
import numpy as np
from scipy.stats import spearmanr

def cross_symbol(symbol_wr: dict, symbol_ev: dict) -> dict:
    syms = list(symbol_wr.keys())
    wrs  = [symbol_wr[s] for s in syms]
    evs  = [symbol_ev[s] for s in syms]
    wr_std = float(np.std(wrs))
    rho, pval = spearmanr(wrs, evs) if len(syms) >= 3 else (None, None)
    return {"wr_std": wr_std, "ev_rank_corr": rho, "p_value": pval}
```

**When to use**: Step 5, 2개 이상 심볼 운용 시
**When NOT to use**: 단일 심볼 전략
**Calibration**: wr_std > 0.15 → cross-sectional 비일관. rank_corr < 0.3 → 범용성 없음

---

## 7. WIN/LOSS bucketing template

**수식**:
```
KS-statistic = ks_2samp(win_feature_vals, loss_feature_vals)
p-value < 0.05 → WIN/LOSS가 해당 feature에서 통계적으로 분리
```

**Python snippet**:
```python
from scipy.stats import ks_2samp

def bucket_separation(trades: list, feature: str) -> dict:
    """
    trades: [{"win": bool, "features": {feature: value}}]
    """
    wins   = [t["features"][feature] for t in trades if t["win"]]
    losses = [t["features"][feature] for t in trades if not t["win"]]
    if len(wins) < 5 or len(losses) < 5:
        return {"separable": None, "note": "n too small"}
    stat, pval = ks_2samp(wins, losses)
    return {"ks_stat": stat, "p_value": pval,
            "separable": pval < 0.05,
            "win_mean": sum(wins)/len(wins),
            "loss_mean": sum(losses)/len(losses)}

# 체크할 feature: BVI, OFI, spread_bps, regime, time_of_day
# separable=False → 해당 feature는 predictive power 없음
```

**When to use**: Step 2 추가 진단 — payoff 비대칭 원인 파악 시
**When NOT to use**: n < 10 per bucket

---

## 8. Verdict grammar (고정 어휘)

alpha-critic이 `alpha_critique.md` 말미에 기록하는 고정 종결부:

```markdown
## Verdict
- **Signal edge**: {strong | moderate | none}
- **Primary lever**: {alpha | execution | both | neither}
- **Recommend**: {same family | adjust threshold | adjust exit | abandon | regime gate}
- **Confidence**: {high | medium | low} (sample n=<N>)
```

**예시 (올바른 서술)**:
```
## Verdict
- Signal edge: moderate
- Primary lever: execution
- Recommend: adjust exit (trailing activation 낮추기, exit_design.md §3 참조)
- Confidence: medium (n=47)

근거: total_edge=+3.1 bps, WR=58%, avg_win=42 bps, avg_loss=31 bps.
avg_capture_pct=39% → MFE 절반 이상 반납. exit 문제.
```

**금지 어휘**: "looks good", "seems weak", "generally works", "신호가 약해 보임"

---

## 9. Anti-patterns

1. **WR만 보고 판단** — WR=65%라도 avg_loss > avg_win × 1.5이면 total_edge 음수 가능. §3 expectancy 필수 계산.
2. **Outlier 1개가 mean 지배** — avg_win이 비정상적으로 높을 때 median과 trimmed mean(10%) 병행 계산.
3. **n < 20에서 통계 단정** — 신뢰구간 너무 넓음. "샘플 부족 — Confidence: low" 명시 후 결론 유보.
4. **confirmation bias** — 자기 가설을 지지하는 trade만 인용. WIN/LOSS 전체 분포 기반 판단.
5. **pooled metric만 인용** — 단일 심볼이 평균 왜곡 가능. §6 per-symbol 분해 항상 수행.
6. **capture_pct 생략** — exit 문제를 alpha 문제로 오진 → 잘못된 방향으로 전략 수정.
7. **Regime 분석 생략** — 전체 WR은 좋지만 특정 regime에서만 작동 시 regime gate 없이 배포 → OOS 실패.

---

## 10. References

- `knowledge/lessons/` — `selectivity`, `regime_gate`, `capture_pct` 키워드 검색
- `exit_design.md` — capture_pct < 50% 시 참조
- `mean_reversion_entry.md §2` — iter1 진단 예시 (regime-dependent signal 케이스)
