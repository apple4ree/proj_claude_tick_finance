---
date: 2026-04-28 12:30
tone: milestone
title: v6 fresh run 시작 — 4 lever 통합 첫 정식 실험
session_id: 2026-04-27-s1
---

## 계기 (Motivation)

직전 progress (12:00) 에서 4가지 개선 lever (A: LLM 캘리브레이션 / B: Maker 호가 회수 / C: 시장 통계 표 / D: 보유 시간 표) 모두 구현 완료 + 사전 smoke 검증 통과. 이제 정식 fresh run 으로 4 lever 의 결합 효과를 v3/v4/v5 와 직접 비교 가능한 조건에서 측정해야 함.

\"왜 동시 적용 fresh run 이 의미 있는가\":
- v5 와 동일한 setup (8 거래일 × 3 종목 × 25 iter × 4 candidates) 으로 돌리면 \"v5 → v6\" 가 clean ablation.
- 같은 pipeline / 같은 데이터에서 references + execution_mode 만 다름 → 차이의 원인이 4 lever 라고 attribution 가능.
- Path D 의 boost 가 큰 horizon (T=500~5000) 신호를 LLM 에게 노출하므로, 새 종류 신호가 등장하는지 관찰.

## 가설 (Hypothesis)

\"4 lever 동시 적용한 v6 가 v5 의 4.74 bps mid_gross 천장을 뚫고, 어느 한 신호의 maker_gross 가 23 bps 이상 (= net deployable) 도달한다\".

가설이 맞다면:
- 어느 한 신호의 aggregate_expectancy_bps (maker mode) > 23 → 프로젝트 first deployable
- 평균 mean_dur 가 v5 대비 ≥ 2x (Path D 효과)
- top 10 의 primitive family 가 ≥ 3 (Path A/C 의 saturation 완화 효과)

가설이 틀리면 (모두 net < 0):
- Path B 단독 효과 (mid + 9 bps spread) 만 작용했고 magnitude 자체는 못 키웠다는 뜻
- → chain 1 의 spec language (binary trigger + regime-state) 의 fundamental 한계 신호
- 다음 검토: Path E (agentic tool-use) 또는 chain 2 통합

## 변인 통제 및 설계 (Experimental Design)

- **독립 변수**:
  - LLM references: 17 files (v5) → 19 files (v6, +quick_ref + empirical_baselines + t_scaling)
  - Execution mode: mid-to-mid (v5) → maker_optimistic (v6, --execution-mode flag)
- **종속 변수**:
  - aggregate_expectancy_bps (maker mode) per spec
  - aggregate_expectancy_maker_bps (maker mode 의 primary)
  - aggregate_avg_spread_bps (Path B 의 측정 부산물)
  - mean_duration_ticks, signal_duty_cycle, n_regimes
- **통제 변수**:
  - 종목: 005930, 000660, 005380 (동일)
  - 날짜: 20260316~25 (8 KRX 거래일, 동일)
  - Iteration: 25 (동일)
  - Candidates / iter: 4 (동일)
  - 패러다임: regime-state (동일, v5 부터)
  - Reward: net = gross − 23 bps (동일, v4 부터)
  - Calibration table: krx_v2_2026_03_3sym.json (동일)
  - LLM model: Claude Sonnet (동일)
- **비교 baseline**: v5 (iterations_v5_archive_20260428). 차이는 references 와 execution_mode 만.

## 철학 / 선택의 근거 (Why this approach)

\"같은 setup\" 을 고정한 이유:
- 모든 차이가 4 lever 의 효과로 attribution 되려면 통제 변수가 흔들리면 안 됨.
- 만약 종목·날짜·iter 수도 바꾸면 \"v5 vs v6\" 에 confounding factor 가 늘어 paper-grade ablation 안 됨.
- 시간 자원도 동일 (~5h) — 더 큰 setup 은 매 lever 변경 마다 추가 비용.

\"Maker_optimistic\" 의 선택 이유:
- maker_realistic (queue + adverse selection) 은 chain 2 영역 — 너무 큰 작업.
- maker_optimistic 은 \"항상 체결\" 가정의 upper bound. 만약 이걸로도 fee 통과 안 되면 maker_realistic 으로도 안 됨 → fundamental 한계 진단.

\"Path E 미포함\" 의 이유:
- 동시 5 lever 적용 시 어느 lever 가 효과의 어느 비율인지 더 안 보임.
- Path E 는 cost 5x + 1주 작업. v6 의 결과가 margin 이면 Path E, 결과 좋으면 미포함.

## 세션 컨텍스트 (Session Context)

### 이미 수행하고 분석한 것 (Done & Analyzed)

본 progress 직전까지의 작업 (2026-04-28 12:00 ~ 12:30):

- 직전 progress (paths_a_b_c_d_implemented) 작성
- LabHub Flow / Wiki 정리 (post-v5 paths 관련 문서 추가)
- iterations/ → iterations_v5_archive_20260428 (v5 결과 보존)
- 새 iterations/ 디렉토리 생성

직전 세션 (2026-04-27) 에 한 작업의 요점:
- v5 fresh run (PID 2845354) 종료, 78 specs 중 0/78 fee 통과, best 4.74 bps
- v5 의 4가지 원인 진단
- Path A/C/D smoke 검증 (hypothesis 4/4)
- Path B smoke 검증 (top 5 v5 specs maker re-measure, +9.22 bps gain)

### 지금 수행·분석 중인 것 (In Progress)

- v6 fresh launch (PID 3166341, 12:30 KST 시작)
  - log: /tmp/chain1_logs/fresh_run_v6.log
  - 첫 줄 확인: \"objective = net_expectancy (fee_bps_rt=23.0)\", \"execution_mode = maker_optimistic\"
- 백그라운드 watcher (PID 종료 감지) 가동
- LabHub Wiki/Flow 정리 마무리 작업 (Phase 5)

### 수행·분석할 예정인 것 — 추측 / 가능성 (Planned, speculative)

v6 ~5h 후 종료 (예상 17:30 KST). 결과별 분기:

- **시나리오 A — net > 0 신호 ≥ 1 발견 (확률 30%)**:
  - 프로젝트 first deployable signal — paper §Results 핵심.
  - 그 신호의 OOS 검증 (별도 dates, 4월 일부) 즉시 수행.
  - DSR (Deflated Sharpe Ratio) / BH-FDR 적용해 statistical significance 보고.
  - Wiki + LabHub 에 \"first deployable\" milestone progress 작성.

- **시나리오 B — net ∈ (-5, 0] (margin, 확률 30%)**:
  - 결정적 첫 milestone 은 아니나 매우 가까움.
  - Path E (agentic data tools) 작업 시작. ~1주.
  - 종료 후 v7 fresh run 으로 margin 돌파 시도.

- **시나리오 C — net ≤ -10 (확률 30%)**:
  - chain 1 spec language 의 fundamental 한계.
  - chain 2 통합 검토 (maker_realistic + queue model).
  - 또는 multi-day paradigm 으로 chain 1 자체 redesign.

- **시나리오 D — 진행 중 crash / error (확률 10%)**:
  - 진단 후 재시작 (start-iter 옵션).

추측 — 확정 아님. 결과 보고 결정.

## 다이어그램 (Diagrams)

### v3 → v6 의 변경 trajectory

```
              백테스트            보상            백테스트          백테스트
              패러다임            함수            회계              회계
              ─────             ─────         ─────────         ─────────
v3 (4-26)  │  fixed-H     │   WR (승률)    │   mid-to-mid   │   mid-to-mid
              ↓                  ↓              (변경 없음)         (변경 없음)
v4 (4-27)  │  fixed-H     │   net = gross  │   mid-to-mid   │   mid-to-mid
              ↓                 − fee            ↓                  ↓
v5 (4-27)  │  regime-state│   net          │   mid-to-mid   │   mid-to-mid
              ↓ (변경 없음)      ↓ (변경 없음)     ↓ (변경 없음)        ↓
v6 (4-28)  │  regime-state│   net          │   maker_       │   + LLM 새 cheat
                                              optimistic       sheet (3개)
                                              (Path B)         (A/C/D)
              =======================================================
              Best mid_gross 측정값:
              v3: 13.32   v4: ~12   v5: 4.74   v6: TBD
              Best maker_gross (re-measure for v5):  14.01
```

### v5 vs v6 ablation 의 통제·변경 변수

```
┌────────────────────────────────────────────────────────────┐
│ 통제 변수 (v5/v6 동일)                                     │
├────────────────────────────────────────────────────────────┤
│  • 종목: 005930, 000660, 005380                            │
│  • 날짜: 20260316 ~ 20260325 (8 KRX 거래일)                │
│  • Iteration: 25                                           │
│  • Candidates / iter: 4                                    │
│  • 패러다임: regime-state                                  │
│  • Reward: net = gross − 23 bps                            │
│  • Calibration table: krx_v2_2026_03_3sym.json             │
│  • LLM model: Claude Sonnet                                │
└────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│ 독립 변수 (v6 가 변경)                                     │
├────────────────────────────────────────────────────────────┤
│  • LLM references: 17 files → 19 files                     │
│       └ Path A: quick_ref.md  (신규)                       │
│       └ Path C: empirical_baselines.md  (신규)             │
│       └ Path D: t_scaling.md  (신규)                       │
│  • Execution mode: mid-to-mid → maker_optimistic           │
└────────────────────────────────────────────────────────────┘
                           ↓
                    측정할 종속 변수:
                    aggregate_expectancy_bps (maker mode)
                    aggregate_avg_spread_bps
                    mean_duration_ticks
                    primitive family 다양성
```

### 결과별 분기 (시나리오 트리)

```
v6 종료 (~5h)
  │
  ├──[A] net > 0 spec ≥ 1 (확률 30%)
  │       └─→ 프로젝트 first deployable
  │           ├─ OOS 검증 (별도 4월 dates)
  │           ├─ DSR / BH-FDR statistical correction
  │           └─ Paper §Results 시작
  │
  ├──[B] net ∈ (-5, 0]  margin (확률 30%)
  │       └─→ Path E (agentic tool-use) 작업 ~1주
  │           └─→ v7 fresh run 으로 margin 돌파
  │
  ├──[C] net ≤ -10  fundamental (확률 30%)
  │       └─→ chain 1 spec language 한계
  │           ├─ chain 2 통합 (queue model + adverse selection)
  │           └─ multi-day paradigm redesign
  │
  └──[D] crash / error (확률 10%)
          └─→ 진단 후 resume (start-iter)
```

## 진행 / 결과 (Progress / Results)

- v5 archive (iterations_v5_archive_20260428)
- v6 fresh launch — PID 3166341
- CLI 인자: --max-iter 25 --n-candidates 4 --symbols 005930 000660 005380 --dates 20260316~25 --calibration-table krx_v2_2026_03_3sym.json --fee-bps-rt 23.0 --execution-mode maker_optimistic
- Loop 첫 출력 정상: \"objective = net_expectancy\", \"execution_mode = maker_optimistic\"
- iter_000 진입 확인

## 발견 / 의미 (Findings / Implications)

- v5 / v6 가 clean ablation 으로 비교 가능 (모든 통제 변수 동일)
- LLM 가 새 cheat sheet (quick_ref / empirical_baselines / t_scaling) 자동 로드 확인 — 19 files / ~99K chars
- maker_optimistic 모드가 backtest_runner 에 정상 통합

## 다음 단계 (Next)

1. v6 진행 모니터링 (시간당 1회 체크, iter 진행 상황)
2. v6 종료 시 자동 분석 (analysis/v6_results.py 실행)
3. 결과별 분기 (시나리오 A/B/C/D 따라)
4. v6 결과 progress.md 작성 (이 template 으로)
