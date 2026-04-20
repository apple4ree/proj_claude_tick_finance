# 3-Axis Trajectory System Design Spec

## 1. 개요

전략 생성 파이프라인을 **3개 독립 축(Alpha, Execution, Portfolio)**의 trajectory pool로 분리하고,
각 축에서 독립적으로 mutation/improvement를 수행한 뒤, 최적 trajectory를 crossover하여 전략을 합성하는 시스템.

### 핵심 원리
- **분리**: Alpha(언제/왜) × Execution(어떻게) × Portfolio(얼마나/어디에) — 각각 독립 평가
- **보존**: 성공한 trajectory는 보존하고 실패한 축만 교체
- **교배**: 서로 다른 iteration에서 나온 best trajectory를 조합하여 새 전략 합성

### 해결하는 문제
- 이전 iterate: 14회 반복 → 매번 scratch에서 전체 재생성 → 챗바퀴
- Trajectory: 성공 부분 보존 + 실패 부분만 교체 → 수렴

## 2. Trajectory 정의

### Alpha Trajectory (αᵢ)
```json
{
  "traj_id": "alpha_001",
  "symbol": "005930",
  "signal": "obi_1",
  "threshold": 0.3,
  "horizon": 1000,
  "signal_brief_rank": 1,
  "ic": 0.26,
  "q5_bps": 3.72,
  "entry_condition": "obi(5) > 0.3 AND spread < 8",
  "time_window": [36000, 46800],
  "score": 0.0  // clean_pnl 기반 점수 (backtest 후 업데이트)
}
```

### Execution Trajectory (εⱼ)
```json
{
  "traj_id": "exec_001",
  "entry_mode": "passive_maker",
  "entry_price": "bid",
  "ttl_ticks": 75,
  "profit_target_bps": 80,
  "stop_loss_bps": 50,
  "sl_reference": "bid_px",  // bid-anchored (invariant 준수)
  "trailing": {"activation": 60, "distance": 40},
  "time_stop_ticks": 3000,
  "max_entries_per_session": 3,
  "score": 0.0
}
```

### Portfolio Trajectory (πₖ)
```json
{
  "traj_id": "port_001",
  "allocation_method": "equal_weight",
  "symbols": ["005930", "000660"],
  "weights": {"005930": 0.5, "000660": 0.5},
  "lot_sizes": {"005930": 5, "000660": 3},
  "max_total_exposure_pct": 20,
  "max_correlated_symbols": 3,
  "score": 0.0
}
```

## 3. Trajectory Pool 관리

### 저장 위치
```
strategies/_trajectories/
  alpha_pool.json     ← 모든 alpha trajectory 목록
  exec_pool.json      ← 모든 execution trajectory 목록
  port_pool.json      ← 모든 portfolio trajectory 목록
  combinations.json   ← 이전 조합 기록 (α×ε×π → score)
```

### Pool 크기 제한
- 각 pool: 최대 20개 trajectory 유지
- Score 기준 하위 50%는 매 5 iteration마다 pruning
- 새 trajectory 추가 시 score 0으로 시작, backtest 후 업데이트

## 4. 파이프라인 변경

### 기존
```
seed → alpha-designer → execution-designer → spec-writer → coder → backtest → critic → feedback
```

### Trajectory 기반
```
Phase A:
  signal_brief (per symbol) → alpha pool에서 top-N 선택 OR 새 alpha 생성

Phase B (새 파이프라인):
  1. Alpha Selection/Mutation
     - Pool에서 score 상위 alpha 선택  OR
     - 기존 alpha를 mutation (threshold ±10%, signal 교체)  OR
     - 새 alpha 생성 (signal brief 기반)
  
  2. Portfolio Design (NEW)
     - 선택된 alpha들의 symbol 목록 수집
     - 종목 간 상관관계 체크 (일별 수익률 상관)
     - 자본 배분 결정 (IC 비례 or 균등)
     - lot_size per symbol 산출
  
  3. Execution Selection/Mutation
     - Pool에서 score 상위 execution 선택  OR
     - 기존 execution을 mutation (PT ±20%, SL ±20%)  OR
     - 새 execution 생성 (optimal_params 기반)
  
  4. Crossover: α_selected × ε_selected × π_designed → Strategy
     - spec.yaml 합성 (alpha 조건 + execution 파라미터 + portfolio 배분)
     - strategy.py 생성

  5. Backtest + Attribution
     - normal + strict 이중 실행
     - clean_pnl → 각 축의 score 업데이트

  6. Localization (실패 시)
     - clean_pnl < 0이면:
       * Alpha 문제? (signal IC 재확인)
       * Execution 문제? (invariant 위반? exit 분포 비정상?)
       * Portfolio 문제? (특정 종목이 전체를 dragging?)
     - 문제 축만 mutation, 나머지 유지
     - 다음 iteration은 실패 축만 교체
```

## 5. Agent 변경

### 새 agent: portfolio-designer
```
역할: alpha trajectory들의 종목 구성을 받아 자본 배분 결정
입력: alpha_trajectories[] (종목별 IC, Q5, signal brief 정보)
출력: portfolio trajectory (배분 비율, lot_sizes, 위험 제한)
```

### 기존 agent 변경
- **alpha-designer**: trajectory pool에서 선택/mutation 모드 추가
- **execution-designer**: trajectory pool에서 선택/mutation 모드 추가
- **feedback-analyst**: localization 로직 추가 (어느 축이 실패했는지 진단)
- **iterate.md**: trajectory pool 관리 + crossover + localization 루프

### 변경 없는 agent
- spec-writer: 입력 형식만 변경 (3-axis → single spec)
- strategy-coder: 동일 (spec → code)
- backtest-runner: 동일
- alpha-critic / execution-critic: 동일 (각 축 평가는 이미 하고 있음)

## 6. Score 계산

### 개별 축 score
```
α_score = clean_pnl의 alpha 기여분 (signal이 예측한 방향성)
ε_score = clean_pnl의 execution 기여분 (exit 효율성)
π_score = portfolio-level Sharpe ratio × (1 - max_drawdown_pct/100)
```

### 조합 score
```
strategy_score = clean_pnl (total)

# 개별 축 score 분해:
# alpha가 좋고 execution이 나쁜 경우를 구분하기 위해
# critic의 진단 결과를 score에 반영:
#   alpha-critic: signal_edge_assessment → α_score 조정
#   execution-critic: execution_assessment → ε_score 조정
#   portfolio-level: symbol별 return 분산 → π_score 조정
```

## 7. Mutation 연산

### Alpha mutation
- `threshold ± 10%` (signal brief 범위 내)
- `signal 교체` (brief rank 2→3으로 시도)
- `symbol 교체` (같은 signal, 다른 종목)
- `horizon 변경` (100→200→500)

### Execution mutation
- `PT ± 20%`
- `SL ± 20%`
- `entry_mode 교체` (passive→taker, taker→passive)
- `trailing 파라미터 조정`

### Portfolio mutation
- `종목 추가/제거` (viable symbols 중)
- `배분 비율 조정` (IC 비례 → 균등, 또는 반대)
- `lot_size 스케일링`

## 8. Crossover 연산

```
부모 A: (α₃, ε₁, π₂) → score 0.45
부모 B: (α₁, ε₅, π₃) → score 0.38

자식 1: (α₃, ε₅, π₂) → α₃ from A + ε₅ from B + π₂ from A
자식 2: (α₁, ε₁, π₃) → α₁ from B + ε₁ from A + π₃ from B
```

축 간 독립성이 보장되므로 자유롭게 교배 가능.

## 9. 구현 우선순위

1. **trajectory 데이터 구조 + pool 저장** (scripts/trajectory_pool.py)
2. **portfolio-designer agent** (.claude/agents/portfolio-designer.md)
3. **iterate.md 업데이트** (trajectory 기반 루프)
4. **alpha/execution-designer mutation 모드**
5. **feedback-analyst localization 로직**
6. **crossover 연산자**

## 10. 논문 기여

- QuantaAlpha의 trajectory 개념을 **3축(Alpha/Execution/Portfolio)으로 확장**
- Localization이 단순 "어느 단계가 나빴는가"가 아니라 **"어느 축이 나빴는가"** — domain-specific decomposition
- Invariant checker + counterfactual attribution이 score의 noise를 제거 (QuantaAlpha에 없는 기능)
- Cross-axis crossover의 효과 정량화 (ablation: crossover 있/없 비교)
