# Related Work Survey — Tick-Level / HFT Trading Agents (Non-RL)

생성일: 2026-04-27
검색 범위: arXiv last 5 years, 7 buckets × 12 queries = 144 raw → 124 unique
주요 출처: arXiv (Google Scholar 미실행, OpenReview 미실행)

---

## ⭐⭐ 직접 비교 — 우리 framework 의 가장 가까운 analog (반드시 인용)

### B1-1. AlphaAgent (Tang, Chen, Yang 2025) — [2502.16789]
**"LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay"**

- **핵심**: LLM 이 alpha factor 를 generate, **alpha decay** (기존 factor 의 predictive power 가 시간 따라 감소) 에 대응하기 위해 *regularized exploration* 적용. 기존 LLM-driven 방식이 "exploration 부족 → homogeneous factor → crowding 악화" 한다고 비판.
- **우리와의 관계**: **OVERLAP** — 같은 paradigm (LLM → factor formula → backtest → improve). 우리도 mutation random walk 와 family clustering 측정. 우리의 차별점: chain 1/2 분리 (signal vs execution), KRX cash equity 의 sell tax constraint, capped-post-fee framing, regime-state paradigm 검증.
- **인용 우선순위**: ⭐⭐⭐ Top citation. 우리 §Related Work + §Method 비교 섹션 핵심.

### B1-2. Alpha Jungle MCTS (Shi, Duan, Li 2025) — [2505.11122]
**"Navigating the Alpha Jungle: An LLM-Powered MCTS Framework for Formulaic Factor Mining"**

- **핵심**: LLM + Monte Carlo Tree Search 결합. 기존 GP / RL 방식의 search inefficiency 와 interpretability 문제 해결. LLM 이 instruction-following + reasoning 으로 MCTS 의 노드 expansion 을 지도.
- **우리와의 관계**: **COMPLEMENTARY** — 우리 chain 1 의 signal-improver 가 사실 deterministic mutation + LLM augmentation 인데, MCTS 로 search 를 더 systematic 하게 할 수 있음. 우리는 reward function design (Fix #1) 에 집중, 이들은 search algorithm 에 집중.
- **인용 우선순위**: ⭐⭐ §Related Work + §Future Work.

---

## ⭐⭐ 우리 regime-state ablation 과 직접 연결

### B2/B6. Latent Microstructure Regimes (Hiremath × 2, 2026) — [2604.20949]
**"Early Detection of Latent Microstructure Regimes in Limit Order Books"**

- **핵심**: LOB 가 stable → latent build-up → stress 의 3-regime causal data-generating process 를 가정. **표준 OFI / vol 같은 reactive signal 의 한계** 명시. Latent build-up regime 의 identifiability 와 lead-time 보장 도출.
- **우리와의 관계**: ⭐⭐⭐ **OVERLAP + COMPLEMENTARY** — 우리 regime-state ablation 의 직접 motivating paper. 그들의 이론적 framework (3-regime causal DGP) 이 우리의 실증 (regime-state interpretation 의 효과 측정) 의 근거. 우리는 LLM 이 발견한 spec 들을 그들의 framework 으로 재해석할 수 있음.
- **인용 우선순위**: ⭐⭐⭐ §Method (regime-state paradigm) + §Discussion 핵심.

---

## ⭐ Tick-level supervised learning baseline (RL 제외)

### B2-3. Deep LOB Forecasting (Briola, Bartolucci, Aste 2024) — [2403.09267]
**"Deep Limit Order Book Forecasting"**

- **핵심**: NASDAQ 다종목 LOB mid-price 예측. **microstructural characteristic 이 deep learning 효과를 결정**. forecasting 능력이 항상 trading profitability 로 변환되지 않음 (이건 우리 fee-vs-magnitude 결과와 일치). LOBFrame open-source.
- **우리와의 관계**: **COMPLEMENTARY** — 그들은 supervised regression / classification, 우리는 LLM agent. 그들의 "forecasting → not always profitable" 결론이 우리 §Discussion 에 직접 인용 가능 (우리 13bps gross 가 fee 못 통과 결과의 학계 공감).
- **인용 우선순위**: ⭐⭐ §Related Work + §Discussion.

### B2-4. T-KAN HFT LOB (Makinde 2026) — [2601.02310]
**"Temporal Kolmogorov-Arnold Networks for HFT LOB Forecasting"**

- **핵심**: 표준 DeepLOB 의 **alpha decay** 문제 (k 증가 시 predictive power 손실) 를 KAN 의 learnable B-spline activation 으로 해결 시도. FI-2010 dataset.
- **우리와의 관계**: **COMPLEMENTARY** — 우리 saturation iter_014 + horizon 변화 측정의 architectural 대응. 우리는 LLM-level intervention (Fix #1), 이들은 model architecture (KAN).
- **인용 우선순위**: ⭐ §Related Work.

---

## ⭐ Optimal market making (parametric, MM 비교 baseline)

### B3-1. Logarithmic regret AS-MM (Cao, Šiška, Szpruch 2024) — [2409.02025]
**"Logarithmic regret in the ergodic Avellaneda-Stoikov market making model"**

- **핵심**: AS model 의 price sensitivity κ 를 maximum-likelihood 로 학습 시 regret O(ln² T). 핵심: **HJB equation 의 ergodic constant 가 misspecified parameter 에 대해 twice-differentiable** 보임.
- **우리와의 관계**: **CONTEXTUAL** — chain 2 가 향후 구현된다면 비교 대상. 현 우리는 chain 1 단계라 직접 비교 안 됨. KRX cash 의 sell tax 20bps 제약은 이들 모형 외부.
- **인용 우선순위**: ⭐ §Related Work (chain 2 future work).

### B3-2. Adaptive MM with Inventory Liquidation (Chávez-Casillas et al. 2024) — [2405.11444]
**"Adaptive Optimal Market Making with Inventory Liquidation Cost"**

- **핵심**: Discrete-time MM, **partial filling of limit orders** 모델링 (random demand coefficients). Brownian / martingale 가정 없는 일반 price process.
- **우리와의 관계**: **COMPLEMENTARY** — partial fill probability 모델은 chain 2 의 핵심 component. 우리 chain 2 plan 에 직접 적용 가능.
- **인용 우선순위**: ⭐⭐ §Future Work (chain 2 design).

### B3-3. Macroscopic Market Making (Guo, Jin, Nam 2023) — [2307.14129]
**"Macroscopic Market Making"**

- **핵심**: AS-MM 의 macroscopic version — discrete point process 대신 continuous flow process. MM 과 optimal execution 사이의 bridge.
- **우리와의 관계**: **TANGENTIAL** — 이론 framework, KRX retail HFT 직접 적용 어려움.
- **인용 우선순위**: ⭐ §Background.

### B3-4. Multi-currency FX inventory (Barzykin, Bergault, Guéant 2022) — [2207.04100]
**"Dealing with multi-currency inventory risk in FX cash markets"**

- **핵심**: Multi-pair FX dealer 의 inventory risk 관리. Skew 주문 + dealer-to-dealer hedging.
- **우리와의 관계**: **TANGENTIAL** — multi-symbol portfolio MM 의 inventory 관점. 우리 3-symbol KRX 와 직접 비교는 어려움.
- **인용 우선순위**: ⭐ §Future Work.

---

## ⭐ Agent-based simulation (LOB 시뮬)

### B6-2. Neural Stochastic ABM-LOB (Shi, Cartlidge 2023) — [2303.00080]
**"Neural Stochastic Agent-Based Limit Order Book Simulation: A Hybrid Methodology"**

- **핵심**: ABM (agent-based) + SM (stochastic models) 의 hybrid. ABM 은 historical data 에 ungrounded, SM 은 dynamic agent interaction 부재 — 이걸 결합.
- **우리와의 관계**: **TANGENTIAL** — 우리는 simulation 아니라 backtest 위주. chain 2 의 hftbacktest 가 일종의 ABM 이라 향후 연결 가능.
- **인용 우선순위**: ⭐ §Background.

---

## 그 외 문헌

### B4-1. Adaptive HFT Order Book (Yang 2021) — [2103.00264]
**"Forecasting high-frequency financial time series: an adaptive learning approach with the order book"**

- **핵심**: CSI 300 Index Futures, ARIMA + adaptive learning, one-step-ahead price forecasting.
- **우리와의 관계**: **TANGENTIAL** — 우리 KRX cash equity 와 다른 instrument. Imitation learning 도 RL 의 cousin이라 user 의 "RL 제외" 방향과 살짝 어긋남.
- **인용 우선순위**: skip (또는 §Related Work brief mention).

---

## 검색에서 누락 / 약함

1. **DeepLOB (Zhang et al. 2019, IEEE)** — 검색 결과에 직접 안 나옴 (가장 영향력 큰 paper). manually 인용 권장.
2. **Cartea, Jaimungal 의 책 / 논문** — non-arXiv 출판 우세, search 에 적게 잡힘.
3. **FinAgent / FinGPT 류** — daily frequency 위주, 우리 tick 과 거리 멈.
4. **Chinese 주가 / 일본 주가 KOSPI 비슷한 microstructure paper** — 한국 특화 paper 제한적.

---

## 직접 비교 우선순위 (paper writing 시)

### Top 5 (반드시 §Related Work + §Method 비교 포함)

1. **AlphaAgent** [2502.16789] — closest analog. 우리의 chain 1/2 분리 + KRX fee constraint + regime-state 가 차별점.
2. **Latent Microstructure Regimes** [2604.20949] — 우리 regime-state ablation 의 이론 backbone.
3. **Alpha Jungle MCTS** [2505.11122] — search algorithm 개선 방향, future work 비교.
4. **Deep LOB Forecasting (Briola)** [2403.09267] — supervised baseline, "forecast ≠ profit" 결론 인용.
5. **AlphaAgent's "alpha decay"** + 우리의 "saturation/random walk" 비교 가능.

### Bottom-line gaps (우리 contribution candidates)

위 paper 들이 다루지 않는 것:
- ✅ **Reward function design ablation** (Fix #1: WR → net_PnL) — AlphaAgent 는 reward = generic IC, 우리는 deployment-aligned net-PnL
- ✅ **Capped-post-fee phenomenon** 의 정식 명명 — 위 paper 들은 fee 를 거의 무시 (gross IC 만 보고)
- ✅ **Regime-state vs tick-trigger paradigm comparison** — Hiremath et al 은 detection, 우리는 measurement paradigm 자체의 변경
- ✅ **Cite-but-fail pattern** in LLM-generated specs — LLM agent reliability 의 microstructure-specific failure mode
- ✅ **KRX cash equity 의 sell tax constraint** 하의 LLM agent 가 보이는 systematic 행동 — paper 들이 fee 0 또는 simple maker-taker fee 가정

---

## 검색 메타데이터

- arxiv only (Google Scholar / OpenReview 미실행)
- 144 raw papers → 124 unique → 12 selected
- 검색 일시: 2026-04-27 07:30 KST
- 관련성 ranking: manual review of titles + abstracts
- 후속 작업: Top 5 의 full PDF download → summary.md 생성 (paper-search 의 §6 build_paper_folder)
