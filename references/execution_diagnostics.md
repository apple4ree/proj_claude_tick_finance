# Execution Diagnostics

> **Primary consumer**: execution-critic
> **Secondary consumers**: feedback-analyst
> **Trigger condition**: 모든 execution critique 작성 시 (항상)
> **Companion references**: `exit_design.md`, `fee_aware_sizing.md`, `market_making.md`, `signal_diagnostics.md`
> **Status**: stable

---

## 0. Core insight

**execution-critic은 "execution looks poor" 같은 정성 서술 대신 5-step 고정 순서로 진단한다.**

**해결할 failure mode**: ad-hoc judgment → critic verdict가 iter마다 drift → feedback loop의 신호가 흔들림. 동일 전략에 대해 iter 전환 시 "sufficient" → "suboptimal" verdict 역전이 발생하며 개선 방향이 수렴하지 않는다.

**실측 근거**: 2026-04-20 smoke에서 exit-tag 분포를 수동으로 재발견하는 데 분석 시간의 40% 이상 소모. 고정 순서 checklist가 있었다면 구조적으로 차단 가능했던 비용.

---

## 1. Diagnostic checklist (고정 순서)

execution-critic은 반드시 아래 순서로 진행. **순서 변경·생략 금지.**

```
Step 1. Exit tag distribution        → §2
Step 2. Fee burden (counterfactual)  → §3
Step 3. PT/SL calibration            → §4
Step 4. SL gap / overshoot           → §5
Step 5. Per-symbol exit spread       → §6
```

각 step 결과를 수치와 함께 기록 후 §8 Verdict로 종합.

---

## 2. Exit tag distribution (Step 1)

**수식**:
```
pct(tag)         = n(tag) / N_roundtrips × 100
avg_pnl_bps(tag) = mean({pnl_bps | rt.exit_tag == tag})
wr(tag)          = |{rt | tag match AND outcome == WIN}| / n(tag) × 100
```

**Python snippet**:
```python
from collections import Counter
from statistics import mean

def exit_mix(roundtrips: list[dict]) -> dict:
    """Group roundtrips by exit_tag; return pct/avg_pnl/wr per tag."""
    c = Counter((rt.get("exit_tag") or "unknown") for rt in roundtrips)
    n = max(len(roundtrips), 1)
    out = {}
    for tag, k in c.items():
        rts = [rt for rt in roundtrips
               if (rt.get("exit_tag") or "unknown") == tag]
        out[tag] = {
            "n":           k,
            "pct":         round(100 * k / n, 1),
            "avg_pnl_bps": round(mean([rt["pnl_bps"] for rt in rts]), 3),
            "wr":          round(100 * sum(
                               1 for rt in rts if rt.get("outcome") == "WIN"
                           ) / k, 1),
        }
    return out
```

**When to use**: 모든 critique 시작 시 (Step 1 필수)
**When NOT to use**: 없음

**판정 table**:

| 주된 exit_tag | 비율 | 해석 |
|---------------|------|------|
| `time_stop` | > 70% | time-stop이 edge harvester — PT/SL은 cap 역할에 불과 |
| `profit_target` | > 50% | PT가 실제 주 청산, SL/time은 보조 |
| `stop_loss` | > 30% | SL 과다 발동 — 너무 타이트하거나 signal noise 높음 |
| `trailing_stop` | > 40% | trailing activation 재보정 필요할 수 있음 |
| `exit_eod` | > 10% | 하루 내 hold 의도 실패, 포지션 과대 유지 |

---

## 3. Fee burden (Step 2)

**수식**:
```
fee_to_edge_ratio = fee_RT / (avg_pnl_gross + fee_RT) × 100   (%)
break_even_WR     = (SL + fee_RT) / (PT + SL) × 100            (%)
net_per_trade     = avg_pnl_gross_bps - fee_RT_bps
```

**Python snippet**:
```python
def fee_burden(avg_pnl_gross_bps: float, fee_rt_bps: float,
               pt_bps: float, sl_bps: float) -> dict:
    denom = avg_pnl_gross_bps + fee_rt_bps
    ratio = (fee_rt_bps / denom * 100) if denom > 0 else float("inf")
    be_wr = (sl_bps + fee_rt_bps) / (pt_bps + sl_bps) * 100
    return {
        "fee_to_edge_ratio_pct": round(ratio, 1),
        "break_even_wr_pct":     round(be_wr, 1),
        "net_per_trade_bps":     round(avg_pnl_gross_bps - fee_rt_bps, 3),
    }
```

**When to use**: Step 2 (항상)
**When NOT to use**: 없음
**Calibration**: `fee_to_edge_ratio > 50%` → fee-dominated → abandon 또는 maker 전환 (`fee_aware_sizing.md §6`)

**counterfactual 2-scenario 의무 보고** (critique에 반드시 두 줄):
```
At fee = 0 bps  (current):     net_per_trade = +X bps,  ratio = Y%
At fee = 4 bps  (Binance taker): net_per_trade = −X' bps, ratio = Z%
                                  (fee-dominated if ratio > 50%)
```

---

## 4. PT/SL calibration (Step 3)

**수식**:
```
pt_hit_rate  = n(exit_tag=profit_target) / N_roundtrips × 100
sl_hit_rate  = n(exit_tag=stop_loss)     / N_roundtrips × 100
required_WR  = SL / (PT + SL) × 100

phantom_pt = (pt_hit_rate < 5) AND (required_WR > observed_WR)
```

**Python snippet**:
```python
def pt_sl_diagnose(roundtrips: list[dict],
                   pt_bps: float, sl_bps: float) -> dict:
    n = len(roundtrips)
    pt_rate = sum(1 for r in roundtrips
                  if r.get("exit_tag") == "profit_target") / n * 100
    sl_rate = sum(1 for r in roundtrips
                  if r.get("exit_tag") == "stop_loss") / n * 100
    req_wr  = sl_bps / (pt_bps + sl_bps) * 100
    obs_wr  = sum(1 for r in roundtrips
                  if r.get("outcome") == "WIN") / n * 100
    phantom = (pt_rate < 5) and (req_wr > obs_wr)
    return {
        "pt_hit_rate_pct":    round(pt_rate, 1),
        "sl_hit_rate_pct":    round(sl_rate, 1),
        "required_wr_pct":    round(req_wr, 1),
        "observed_wr_pct":    round(obs_wr, 1),
        "phantom_pt":         phantom,
    }
```

**When to use**: Step 3 (항상)
**When NOT to use**: n < 20 — 결론 유보, "샘플 부족" 명시

**임계 table**:

| 패턴 | 의미 | 권장 조치 |
|------|------|-----------|
| `phantom_pt = True` | PT 도달 불가 — ephemeral | `exit_design.md §6` — PT를 p50으로 하향, time_stop 확인 |
| `sl_hit_rate > 40%` | SL 과다 발동 | SL widening 또는 signal 재조준 |
| `required_WR > 80%` | 구조적 비가능 | PT/SL ratio 뒤집기 또는 다른 paradigm |

---

## 5. SL gap / overshoot (Step 4)

**수식**:
```
overshoot_ratio_i = |realized_SL_bps_i| / spec_SL_bps     (per SL trade)
gap_severity      = mean(overshoot_ratio where exit_tag == stop_loss)
```

spec invariant checker의 `sl_overshoot` type은 ±10 bps tolerance를 가지므로 gap이 허용오차 내면 technically violation 아님.
**그러나 `gap_severity > 1.5` (실현 SL이 spec의 1.5배 초과)는 critic이 반드시 플래그해야 함.**

**Python snippet**:
```python
from statistics import mean

def sl_gap_stats(roundtrips: list[dict], spec_sl_bps: float) -> dict:
    sl_trades = [r for r in roundtrips
                 if r.get("exit_tag") == "stop_loss"]
    if not sl_trades:
        return {"n_sl": 0, "status": "no_sl_triggers"}
    realized   = [float(r["pnl_bps"]) for r in sl_trades]
    overshoots = [abs(r) / spec_sl_bps for r in realized if r < 0]
    return {
        "n_sl":                    len(sl_trades),
        "avg_realized_bps":        round(mean(realized), 3),
        "worst_bps":               round(min(realized), 3),
        "gap_severity":            round(mean(overshoots), 3) if overshoots else 0.0,
        "n_overshoot_gt_1p5x":     sum(1 for o in overshoots if o > 1.5),
    }
```

**When to use**: Step 4 (항상, LOB 환경에서 특히 중요)
**When NOT to use**: `n_sl == 0` → "no_sl_triggers" 반환, 다음 step으로 진행

**판정**:
- `gap_severity > 1.5` + LOB market → cadence gap risk; critic은 "accept as known structural feature" 또는 "widen spec SL" 권고
- `exit_design.md §1` iter1 case study의 SL-overshoot 패턴 재현 시 인용 필수

---

## 6. Per-symbol exit spread (Step 5)

**수식**:
```
per-symbol: {wr_i, avg_pnl_bps_i, exit_mix_i, n_i}
wr_std_pp  = std(wr_i across symbols)              (percentage points)
pnl_std    = std(avg_pnl_bps_i)

gross_pnl_i = avg_pnl_bps_i × n_i                  (per symbol total PnL, signed)
dominance   = max(|gross_pnl_i|) / Σ|gross_pnl_i|  (절대합 분모; 0≤dominance≤1)
              — 한 심볼이 전체 |PnL| 움직임에서 차지하는 최대 비중
```

**Python snippet**:
```python
from collections import Counter, defaultdict
from statistics import mean, stdev

def per_symbol_exit(roundtrips: list[dict]) -> dict:
    by_sym: dict = defaultdict(list)
    for r in roundtrips:
        by_sym[r["symbol"]].append(r)

    out = {}
    for sym, rts in by_sym.items():
        out[sym] = {
            "n":           len(rts),
            "avg_pnl_bps": round(mean([r["pnl_bps"] for r in rts]), 3),
            "wr":          round(100 * sum(
                               1 for r in rts if r.get("outcome") == "WIN"
                           ) / len(rts), 1),
            "exit_mix":    dict(Counter(r.get("exit_tag") for r in rts)),
        }

    wrs = [d["wr"] for d in out.values()]
    # dominance uses absolute-sum denominator so a +500 / -500 split between
    # symbols does not explode the ratio. Intent: "which symbol contributed
    # the largest share of gross PnL motion, long or short."
    abs_sum = sum(abs(d["avg_pnl_bps"] * d["n"]) for d in out.values())
    max_sym_pnl = max((abs(d["avg_pnl_bps"] * d["n"]) for d in out.values()),
                      default=0)
    out["_summary"] = {
        "wr_std_pp":  round(stdev(wrs), 2) if len(wrs) > 1 else 0.0,
        "dominance":  round(max_sym_pnl / abs_sum, 3) if abs_sum > 0 else None,
    }
    return out
```

**When to use**: Step 5 (항상)
**When NOT to use**: 단일 심볼 전략

**판정 임계**:
- `wr_std_pp > 15` → 심볼 간 불일관 — per-symbol 파라미터 분리 또는 해당 심볼 제외
- `dominance > 0.80` → concentration warning — `portfolio_allocation.md §5` 참조

---

## 7. Counterfactual scenarios (의무)

모든 critique에 아래 4-scenario를 최소 제시. **숫자로 기재, 추정만 가능한 경우 "(추정)" 명시.**

| Scenario | 입력 | 관찰 대상 | 실행 방법 |
|----------|------|-----------|-----------|
| baseline | spec 그대로 | 현재 metric | 기존 `report.json` |
| fee=0 vs taker 4 bps | `fee_burden` 재계산 | `net_per_trade`, `ratio` | §3 공식 재적용 (재실행 불필요) |
| SL 삭제 | exit_tag ⊂ `{time_stop, profit_target}` 에 집중 | EV 추정 | roundtrips에서 `exit_tag == "stop_loss"` 제외 후 avg 재계산 (분석적) |
| time_stop 2배 | `time_stop_ticks` × 2 (예: 10 → 20) | hold 가치 (`exit_design.md §2.4`) | **선호**: `_spec_ts2x.yaml` 임시 생성 → `engine.runner`로 재실행 → 새 report와 비교. **여의치 않으면**: 기존 roundtrips의 `entry_ts_ns` 기준 `20 ticks` 시점 mid를 trace.json의 mid_series에서 재샘플해 분석적 PnL 재계산 (추정) |

---

## 8. Verdict grammar (고정 어휘)

execution-critic이 `execution_critique.md` 말미에 반드시 기록:

```markdown
## Verdict
- **Execution quality**: {strong | adequate | suboptimal | broken}
- **Primary defect**: {fill_mechanics | pt_phantom | sl_gap | fee_dominated | per_symbol_drag | none}
- **Recommend**: {keep | tune_pt_sl | add_spread_gate | switch_to_maker | abandon}
- **Confidence**: {high | medium | low} (n=<N>, exit_tag_diversity=<k>)
```

**금지 어휘**: "looks fine", "seems off", "could be better", "일반적으로", "실행이 괜찮아 보입니다"

**예시 (올바른 서술)**:
```
## Verdict
- Execution quality: suboptimal
- Primary defect: per_symbol_drag (SOL spread 1.17 > PT 1.09)
- Recommend: add_spread_gate
- Confidence: high (n=1500, exit_tag_diversity=3)

근거: time_stop 91.3%, SOL wr=3% vs BTC/ETH wr=37%,
fee=4 bps scenario ratio=94.7% (fee_aware_sizing §6, §3).
```

---

## 9. Anti-patterns

1. **Pooled metric만 보고 단일 심볼 drag 놓침** — 항상 §6 per-symbol 분해 수행. SOL이 BTC/ETH 평균을 끌어내리는 패턴은 pooled 지표에서 불가시.
2. **time_stop 91%인데 PT 미세튜닝에 집중** — time_stop이 primary exit이면 PT/SL은 보조. `exit_design.md §2.3` 참조.
3. **fee=0 단일 시나리오만 보고 "deployable" 판정** — §7 counterfactual 4-scenario 의무. taker 4 bps 시나리오 누락 시 reject.
4. **SL overshoot을 invariant pass로 해석** — ±10 bps tolerance가 gap_severity를 마스킹. `sl_gap_stats` 별도 계산 필수 (§5).
5. **"trailing을 켜보자" 근거 없이 처방** — 현재 `n_trailing_triggered == 0`일 수 있음. exit_mix 먼저 확인 후 제안.
6. **Outlier 1-2 trade가 avg_pnl 지배** — median 및 trimmed mean(10%) 병행. `signal_diagnostics.md §9` 교차참조.
7. **Same-family 이전 iter critique 무시** — verdict drift 위험. `strategies/<family>_*_execution_critique.md` 확인 후 비교 서술.
8. **canonical paradigm fee 잘못 가정** — market_making은 maker fee(0 bps) 기준. taker fee로 계산 시 EV 왜곡.

---

## 10. References

- `references/exit_design.md §1, §4` — give-back 패턴, counterfactual 분석
- `references/fee_aware_sizing.md §6` — fee-to-edge ratio 임계
- `references/market_making.md §3, §4` — MM 패러다임 특수 exit
- `references/signal_diagnostics.md` — alpha-critic 대칭판 (구조 모방)
- `knowledge/lessons/` — 키워드: `exit_tag`, `gap_risk`, `fee_dominated`
