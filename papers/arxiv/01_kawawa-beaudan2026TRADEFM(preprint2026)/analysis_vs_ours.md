# TradeFM (2026) 정밀 분석 — 우리 framework 와의 비교

**Paper**: Kawawa-Beaudan, Sood, Papasotiriou, Borrajo, Veloso (2026)
**Title**: TradeFM: A Generative Foundation Model for Trade-flow and Market Microstructure
**Affiliation**: J.P. Morgan AI Research (Manuela Veloso, Daniel Borrajo)
**arXiv**: `2602.23784v1` (2026-02-27)
**29 pages, preprint**

---

## 1. TradeFM 의 핵심 — 한 문단

524M-parameter decoder-only Transformer (Llama-family architecture). >9K US equities × 368 거래일 (2024-02 ~ 2025-09) 의 **trade event stream** (LOB snapshot 아님!) 으로 pretraining. Trade event 를 (Δt, δp, v, a, s) 5-tuple 로 표현하고 universal tokenization (mixed-base encoding) 으로 16,384 vocabulary 로 압축. Closed-loop simulator (deterministic LOB matching engine) 와 통합해 **synthetic market trajectory 생성**. Stylized facts (heavy-tail, vol clustering, no autocorr) 재현. **Compound Hawkes baseline 대비 2-3× 낮은 K-S distance**, US 학습 후 China/Japan **zero-shot generalization**.

---

## 2. 무엇을 하는 paper 인가 / 무엇을 하지 않는가

### ✅ 한다
1. **Generative microstructure simulation** — synthetic 1-asset trade event stream 생성
2. **Cross-asset transfer learning** — 9K stocks 통합 학습으로 universal representation
3. **Stylized fact reproduction** — heavy tail, vol clustering, no return autocorr
4. **Realism evaluation** — Wasserstein distance, K-S statistic, perplexity
5. **Conditional generation** — liquidity / market-vs-participant 인디케이터로 출력 제어
6. **Counterfactual stress testing** (Appendix) — "10× normal frequency" 같은 anomalous order flow injection

### ❌ 하지 않는다
1. ❌ **Trading agent 없음** — strategy 생성/실행 안 함
2. ❌ **LLM 기반 추론 없음** — pretrained LLM 안 씀, scratch 에서 초기화한 생성 모델
3. ❌ **Fee / cost 분석 없음** — gross simulation, deployment economics 미고려
4. ❌ **Profit metric 없음** — Sharpe, expectancy, WR 모두 미산출
5. ❌ **Spec generation 없음** — formula / strategy 자동 생성 안 함

### 자신들이 인정하는 future work (Section 10 결론)

> "Training learning-based trading agents via interaction with the simulator (preliminary explorations in Appendix D.4, D.5, D.6)"

→ **그들 자신이 "trading agent" 영역은 future work 라고 명시**. 우리가 그 future work 의 한 instance.

---

## 3. 우리 framework 와의 본질적 차이

### 3.1 AI 의 사용 방법 (가장 큰 차이)

| 차원 | TradeFM | 우리 chain 1 |
|---|---|---|
| **AI architecture** | Custom Transformer 524M, scratch pretrained | Off-the-shelf LLM (Sonnet 4.6 등) prompt-engineered |
| **Training** | 10.7B tokens, A100×3 GPUs, weeks | No training — 0 GPU |
| **Output** | Discrete trade event tokens (next event prediction) | Markdown-style SignalSpec (formula + threshold + horizon) |
| **Reasoning** | Implicit (in latent space) | Explicit (LLM의 hypothesis 텍스트) |
| **Interpretability** | Low (token-level autoregression) | High (human-readable formula + cited references) |

→ 두 paradigm 은 **완전히 다른 AI-finance 관계**. TradeFM = "synthesize the market", 우리 = "synthesize a strategy for the market".

### 3.2 무엇을 모델링하는가

| TradeFM | 우리 |
|---|---|
| `P(e_t | e_<t)` — 다음 trade event | `Spec(formula, threshold, horizon, direction)` — 매매 신호 정책 |
| Order flow 의 통계적 분포 | Mid-price drift 의 directional 예측 |
| Generative distribution matching | Discriminative direction prediction |

### 3.3 평가 metric

| TradeFM | 우리 |
|---|---|
| K-S statistic, Wasserstein distance | Win rate, expectancy_bps, n_trades |
| Stylized fact reproduction | Capped-post-fee, deployable threshold |
| Perplexity (next token uncertainty) | Mutation-improvement rate, cite-but-fail rate |

→ TradeFM 은 *realism* 측정, 우리는 *profitability* 측정.

### 3.4 시장

| TradeFM | 우리 |
|---|---|
| US (9K equities), zero-shot APAC (CN/JP) | KRX (3 sym × 8 dates) |
| Cross-asset, cross-geography 일반화 | Single-market, multi-symbol |
| Fee 무시 | KRX 23bps RT, sell tax 20bps hard constraint |

### 3.5 Frequency / data type

**둘 다 tick-level** (이게 처음으로 진정한 frequency overlap).
- TradeFM: 100ms-resolution trade events (US equities)
- 우리: 100ms tickdata_krx parquet snapshots

다른 점: TradeFM 은 **trade event stream** (orders / cancels / fills 시퀀스), 우리는 **LOB snapshot stream** (bid/ask price + qty 10-level + total + 매분당 derived primitives). TradeFM 의 partial observability 주장이 우리에게도 적용됨.

---

## 4. 학습 가능한 것 — 우리 framework 강화 후보

### 4.1 우리가 차용 가능한 것

1. **Scale-invariant features**: `relative_price_depth = (p_order − p_mid) / p_mid` (bps). 우리 chain 1 의 calibration table (D1) 이 비슷한 motivation 이나, TradeFM 의 더 systematic 한 정규화 (log-transformed volume, normalized depth) 를 chain 1.5 에 도입 가능.

2. **EW-VWAP mid-price estimator**: 단순 (bid+ask)/2 보다 robust한 mid 추정. 우리 mid_px primitive 를 EW-VWAP 으로 교체 검토.

3. **Universal tokenization**: 우리 spec 의 primitive 를 trade-event tokenization 처럼 discrete vocabulary 로 표현하면 LLM 이 더 효율적으로 reasoning 할 수 있을 수도. 단 우리 primitive 는 이미 discrete (whitelist) 이라 직접 적용은 마진 효과.

4. **Counterfactual stress testing**: 우리 v3/v4 결과를 TradeFM 같은 synthetic market 에 적용해 generalization test 가능. *Robustness benchmark* 로 활용.

### 4.2 우리가 그들에게 줄 수 있는 것

1. **Strategy generation layer** — TradeFM 자신의 future work. 우리 chain 1 framework 가 그 plug-in 일 수 있음.
2. **Cite-but-fail pattern** — Foundation model 도 microstructure category B3 류 failure 를 일으키는지 측정. 우리의 LLM agent 측정이 baseline.
3. **Net-PnL objective** — TradeFM 평가는 모두 realism metric. Deployment objective (net PnL) 과의 격차 측정은 우리 영역.

### 4.3 결합 가능 시나리오 (long-term)

```
TradeFM (synthetic market)  ← provides realistic event streams
     ↓
Our chain 1 (LLM spec gen) ← discovers strategies on synthetic markets  
     ↓
Cross-validation on real KRX data
     ↓
Robustness 측정: synthetic-trained spec 이 real KRX 에서 작동하는지
```

이 시나리오는 우리 paper 의 "Future Work" 후보.

---

## 5. Paper writing 시 비교 framing

### 5.1 §Related Work — 정확한 한 문단

> *Concurrent work has explored generative foundation models for market microstructure. **TradeFM** (Kawawa-Beaudan et al., 2026), a 524M-parameter Transformer trained from scratch on 9K+ US equities' trade event streams, demonstrates that scale-invariant tokenization enables zero-shot cross-geography generalization for **synthetic market simulation**. While TradeFM and our work share the trade-event abstraction and tick-level frequency, they target orthogonal goals: TradeFM produces *generative simulators* evaluated by stylized-fact realism (K-S distance, perplexity), whereas our framework produces *executable trading specifications* evaluated by deployment economics (net expectancy after KRX fees). TradeFM explicitly identifies "training learning-based trading agents via interaction with the simulator" as future work — our chain 1 framework operationalizes that direction at the LLM-agent level rather than the foundation-model-from-scratch level.*

### 5.2 §Discussion — 두 paradigm 비교 표

| Dimension | TradeFM (scratch FM) | Ours (LLM agent) |
|---|---|---|
| AI architecture | Custom Transformer 524M | Off-the-shelf LLM |
| Training cost | 3 A100s × weeks | $0 GPU, $X/spec inference |
| Output | Trade event tokens | Executable spec |
| Interpretability | Low | High (formula + cited refs) |
| Goal | Synthetic market | Deployable strategy |
| Eval metric | Realism (K-S) | Profitability (expectancy) |

### 5.3 §Introduction — positioning 문장

> *We present the first LLM-agent-driven framework for tick-level trading strategy discovery in fee-constrained markets. While concurrent work (TradeFM, AlphaForgeBench) advances foundation-model and LLM-as-researcher paradigms separately, our contribution lies in their intersection — operationalizing LLM agents to produce executable specifications evaluated under realistic deployment economics (KRX cash equity, 23 bps RT fee floor including 20 bps sell tax) on 100ms tick data.*

---

## 6. 인용 우선순위

⭐⭐⭐ **반드시 인용**:
- §Related Work: TradeFM 의 scale-invariant features + closed-loop simulator
- §Discussion: foundation-model vs LLM-agent paradigm 비교
- §Future Work: TradeFM-as-simulator + our chain 1 통합 시나리오

⭐⭐ **상황 따라**:
- §Method: scale-invariant feature design 영감
- §Limitations: TradeFM 같은 generative-model 의 cross-validation 부재 인정

⭐ **선택**:
- §Background: Sirignano-Cont (2021) "Universal Price Formation" 인용 (TradeFM 의 motivation 원조)

---

## 7. 결정적 요약

**TradeFM 은 우리의 직접 경쟁자가 아니라 complementary work**.

| | TradeFM | 우리 |
|---|---|---|
| 무엇을 만드는가 | 시장 그 자체의 representation | 시장에서 작동할 정책 |
| 누구의 view | God's-eye (cross-asset, billions of tokens) | Researcher's-eye (LLM reasoning + cheat sheet) |
| 결과 평가 | "이게 진짜 같은가" | "이게 돈을 버는가" |
| 우리에게 의미 | 미래 통합 가능한 simulator infrastructure | 현재 framework 의 paradigm cousin |

→ 두 work 는 **paradigm 이 다르지만 frequency 가 같음**. 따라서 paper 의 **§Related Work + §Discussion 에서 명확한 분리/비교**가 필수. 표절/유사성 risk 는 매우 낮음 (architecture/goal/metric 모두 직교).

---

## 부록: TradeFM 의 자체 해석 (Conclusion 인용)

> "We have shown that the complex, emergent dynamics of financial markets can be learned directly from raw, heterogeneous order flow. Our end-to-end methodology... allows a single generative Transformer to generalize across thousands of diverse assets without asset-specific calibration. ... The closed-loop simulator opens several directions for future work: privacy-preserving synthetic data generation for illiquid assets, **stress testing under counterfactual scenarios**, and **training learning-based trading agents via interaction with the simulator** (preliminary explorations in Appendix D.4, D.5, D.6). Validating TradeFM's utility for these downstream applications remains a key priority."

→ **"learning-based trading agents" = 우리 framework**. JPM 의 future work 가 우리 work 의 일부 영역과 일치.
