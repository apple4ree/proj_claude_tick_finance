---
schema_version: 1
type: plan
created: 2026-04-27
updated: 2026-04-27
tags: [chain1, signal-generator, empirical-data, bias-mitigation, post-v5]
refs:
  code:
    - {path: ".claude/agents/chain1/_shared/references/cheat_sheets/", confidence: verified}
  papers: []
  concepts:
    - reward-target-mismatch
    - duty-cycle-target
  experiments: []
authored_by: hybrid
source_sessions:
  - 2026-04-27-s1
plan_id: PLAN-C-empirical-baselines
status: proposed
trigger: post-v5-completion
priority: medium
---

# Path C — Empirical Baselines (bias-mitigated systematic partition)

## 문제

LLM signal-generator 가 hypothesis 작성 시 expectancy 를 **추측** 함 — "이 OBI threshold 는 5~10 bps move 를 잡을 것" 같은 prior 가 unanchored. 실측 v3/v4/v5 결과를 보면 평균 0.5~3 bps 영역에 몰려있음. LLM 의 prior 가 **한 자릿수 off**.

해결: cheat sheet 에 **systematic empirical baseline table** 을 박아넣기. LLM 이 hypothesis 를 만들 때 "내 spec 은 cell (X, Y) 의 baseline 보다 ±N bps 다르다" 로 anchored prediction.

**Bias 위험**: 단순히 "Opening 30분 vs lunch 의 mean magnitude 차이" 만 보여주면 LLM 이 그 cell 만 trigger 하려 함. → 다양한 partition + distribution + negative space (no-edge cells) 를 함께 제시.

## 제안 design

**C.1 Partition 정의** (15 cells):

```
Time (5):           opening_30min | morning_60min | lunch_60min | afternoon_120min | closing_30min
Volatility (3):     low (RV < q33%) | mid (q33%~q67%) | high (q67%~q100%)
                                    intra-session realized vol 의 이동 분위수
```

**C.2 Per-cell metric (5):**
- `mean_|Δmid_per_tick|_bps` — 평균 1-tick magnitude
- `mean_|Δmid_per_50tick|_bps` — 50-tick (5초) magnitude
- `mean_|Δmid_per_500tick|_bps` — 500-tick (50초) magnitude
- `pct_obi_above_0.5` — OBI extreme 빈도
- `lag1_autocorr_mid` — sticky vs mean-reverting

→ 15 cells × 5 metrics = 75 data points 의 표.

**C.3 Distribution (not point)** — 각 cell 의 metric 을 single number 가 아닌 (mean, median, p90) triple 로:
- 한 cell 의 magnitude 가 mean=2 bps, median=0.5, p90=8 bps 이면 "rare extreme" cell. LLM 이 "p90 만 trigger" 같은 spec 도출 가능.

**C.4 Negative space 명시** — cell 별 "**no edge**" 표시:
- mean magnitude < 1 bps AND p90 < 5 bps → "fee 통과 어려움" 라벨
- LLM 이 이런 cell 을 trigger 하지 않도록 anti-pattern 으로 고지

**C.5 OOS partition** — 실측 데이터를 IS / OOS 로 분리:
- IS: 2026-03-16 ~ 2026-03-25 (8 dates, v5 와 동일)
- OOS: 2026-04-01 ~ 2026-04-15 (별도)
- 각 cell 의 metric 은 IS 만 사용. OOS 는 hypothesis verification 용 보존.

**C.6 Observation framing** — cheat sheet 에 표만 넣지 말고 frame:
> "이 표는 KRX cash 의 통계적 baseline 입니다. 어떤 cell 이 trade 가능한지를 의미하지 **않으며**, 단지 'cell X 의 mean magnitude 가 Y' 라는 사실 입니다. 본인의 spec 이 이 baseline 을 어떻게 깨는지 가설을 세우세요."

→ LLM 이 cell 을 "선택" 하는 게 아니라 baseline 대비 deviation 을 가설로 형성.

**C.7 Implementation** — `analysis/empirical_baselines.py` (NEW):
- 입력: KRX CSV (data_loader 통해)
- 출력: `chain1/_shared/references/cheat_sheets/empirical_baselines.md`
- 포맷: 15 cells × 5 metrics 표 + distribution + negative space 라벨
- bonus: `data/calibration/empirical_baselines.json` 으로도 저장 → LLM tool (Path E) 이 읽을 수 있게

## 구현 단계

```
C.1  partition 정의 (5×3 cells) 및 vol quantile 계산 코드  (1h)
C.2  per-cell metric aggregation (15 cells × 5 metrics)    (2h)
C.3  distribution triple (mean/median/p90) 추가           (1h)
C.4  negative space labeling                              (30 min)
C.5  IS/OOS split                                         (30 min)
C.6  cheat sheet markdown 생성 (template + observation 프레임)  (1h)
C.7  signal-generator AGENTS.md 에 reference 추가          (15 min)
C.8  smoke test: 1 iter × 1 sym, hypothesis 텍스트 분석    (30 min)
─────
total ~7h
```

## 성공 기준

1. **Anchoring 효과**: smoke test 의 hypothesis 텍스트에서 "baseline" / "cell" / "partition" 키워드 ≥ 2/4 등장.
2. **Bias 미발생**: 15 cells 중 같은 cell 만 trigger 하는 spec 비율 < 50% (즉 5+ cells 에서 spec 분포).
3. **Negative space respect**: "no edge" 라벨 cell 을 명시적으로 trigger 하는 spec = 0.
4. **OOS validity**: IS-fitted spec 의 OOS gross 가 IS gross 의 ±50% 범위 내.

## 의존성 / ordering

- **선행**: v5 종료 (KRX 데이터는 이미 있어서 v5 와 무관하게 시작 가능, 단 cheat sheet 변경은 v5 영향)
- **권장 순서**: A → C → D → B → E (LLM 가 baseline 부터 보고 → spec 도출 → execution 추가)
- **무관**: Path B/E 와 직교

## 위험 / blocker

1. **편향성**: 5×3 partition 자체가 우리의 prior. 다른 partition (가격대 / 종목별 등) 에서는 결과 다를 수 있음. — Mitigation: §C.6 의 framing 으로 "이건 단지 our partition" 라고 명시.
2. **선택 bias**: LLM 이 "high vol × opening" cell 만 trigger → 결국 closing auction artifact 와 유사 problem. — Mitigation: §C.4 negative space + AGENTS.md anti-pattern.
3. **OOS depletion**: IS=8 dates, OOS=별도 → 데이터 부족. KRX 데이터 누적 (현재 ~20 dates) 의 한계.
4. **계산 비용**: 15 cells × 5 metrics × 8 dates × 3 sym = 1800 cell-aggregates. polars 로 빠름 (< 5 min) 추정.

## 예상 영향

- LLM 의 prior 가 numerical anchoring 됨 → unanchored magnitude 추측 감소
- v6+ run 의 hypothesis-result divergence (현재 가설은 +5 bps 인데 실제 +0.5 bps) 가 개선
- Path D (T-scaling) 와 함께 쓰면 magnitude axes (horizon × cell × tail) 의 3D 그리드 완성

## 미정 사항

- Vol partition 의 quantile 기준 — intra-day rolling vs day-level static (전자 권장, 더 fine)
- Symbol 별로 cell-table 분리할지 통합할지 — 통합 권장 (데이터 부족)
- Negative space 라벨의 임계 — `mean < 1 AND p90 < 5` 가 적절한지 (실측 후 조정)
