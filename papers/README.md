# paper-search 결과

**프로젝트 요약**

본 저장소는 NeurIPS 2026 Datasets & Benchmarks 트랙에 투고 예정인 논문
*The Tick-Level Fidelity Gap: LLM-Generated Trading Code Under Microstructure Scrutiny*의 연구 코드베이스입니다. 핵심 기여는 **(C1)** LLM이 자가 선언한 spec으로부터 invariant를 deterministic하게 추론하여 코드 생성 실패를 탐지, **(C2)** normal vs. strict 두 모드로 실행하는 counterfactual PnL attribution으로 위반의 *크기*를 분리, **(C3)** engine-agnostic 측정 레이어(handoff schema + verify_outputs), **(C4)** 틱-레벨에서 기존 bar-level 벤치마크(FactorMiner / AlphaForgeBench 등)가 놓치는 네 가지 실패 유형을 구조적으로 카탈로그화합니다. 최근 관련 연구는 `docs/` 에 10편 수집되어 있으며, 본 paper-search는 그 외의 외부 최신 관련 연구를 자동 수집했습니다.

## 사용된 검색 쿼리 (English)

- `LLM agent trading strategy code generation backtest fidelity`
- `LLM alpha factor mining benchmark financial market multi-agent`
- `limit order book tick backtest market microstructure LLM`
- `code generation specification verification drift measurement LLM agent`

## 학회별 결과 수

| Category | Count |
|----------|-------|
| NeurIPS / ICLR / ICML / COLM / AAAI (target venues) | 0 (매칭된 고해상도 메타데이터 없음 — 대부분 arxiv_only로 분류됨) |
| arxiv_only (folded) | 10 (106개 후보에서 랭킹 후 선정) |
| **TOTAL 선정** | **10** |

## Themes across papers

1. **Limit order book 시뮬레이션과 microstructure 모델링이 성숙 단계에 진입**
   [briola2024], [briola2025], [jain2024 (two papers)], [bergault2024], [wu2025], [figal2025] 모두 deep learning 또는 mechanistic 모델로 LOB dynamics를 정교하게 재현하는 방법론을 제시. 이는 우리가 쓰는 10-level + 5ms latency + queue-position fills 엔진이 academic consensus와 일치한다는 증거이자, 우리가 제공하는 **측정 레이어**가 이 기반 위에서 작동해야 한다는 포지션을 강화.

2. **Multi-agent LLM의 금융 시장 진입 — dual-mode / order-level simulator가 대세화**
   [papadakis2025] (StockSim): multi-agent LLMs를 **order-level** simulator의 **dual-mode**로 평가. 이는 우리 counterfactual attribution (normal / strict 이중 실행)과 동일 철학. 이 논문이 가장 직접적인 동시대 경쟁작으로 차별점을 논문에서 명시 필요.

3. **Spec-to-code 변환에서의 drift / 계약 위반이 general AI safety 문제로 부상**
   [yu2025] (Spec2RTL-Agent, hardware RTL 도메인), [bhardwaj2026] (Agent Behavioral Contracts, general autonomy 도메인). 양쪽 모두 "LLM agent chain에서 spec fidelity를 runtime에 enforce"를 주제로 한다 — 우리 Pydantic handoff schema + verify_outputs 레이어의 cross-domain evidence. 금융 tick 도메인 고유 기여와 구분해서 인용.

4. **Tick-size 및 small-tick regime은 LOB 모델링의 structural challenge**
   [jain2024, no tick-size too small]: tick-size가 작을수록 price grid가 dense해지면서 LOB 모델 가정이 깨짐. 우리 `sl_overshoot` invariant가 sub-tick SL thresholds를 탐지한다는 C5 주장과 맞닿음 — KRX archival 언급 시 인용 가치 있음.

5. **Sparse / informal / non-standard market의 order book regime 다양성**
   [bergault2024, electricity], [figal2025, informal currency]: 전형적 stock/crypto 외의 market에서도 LOB 메커니즘이 의미가 있음을 보여줌. 우리 engine-agnosticism 주장(C3)을 뒷받침하는 간접 증거.

## Convergences

- **LOB-scale simulation이 academic mainstream**: 8편 중 6편이 LOB 정밀 시뮬을 다룬다 ([briola×2], [jain×2], [bergault], [wu]). bar-level 대 tick-level 해상도 차이가 *가정의 문제*가 아니라 *measurement resolution의 실증적 문제*임에 합의.
- **Multi-agent LLM + finance는 2025–2026 급부상 트렌드**: [papadakis2025] + `docs/` 내 FactorMiner / AlphaForgeBench / Beyond Prompting이 모두 같은 시기. 따라서 저자군 간 포지셔닝과 차별점 명시가 리뷰어 설득에 핵심.
- **Spec fidelity의 runtime enforcement가 agent-centric safety의 신흥 topic**: [yu2025], [bhardwaj2026] 모두 이 방향. 우리 기여가 domain-specific(tick-level trading)이라는 점을 강조해야 "유사 연구에 흡수된다" 판정을 피함.

## Disagreements / open questions

- **Order-level simulation이 충분한가 vs. 틱-레벨이 필요한가**: [papadakis2025] StockSim은 order-level을 충분한 것으로 간주. 우리 논문은 *spec-implementation drift*는 order-level simulator가 못 잡는 **틱 마이크로구조 결합 실패**를 생산한다고 주장해야 한다. 이 disagreement가 C4의 논문 전체 주장이 된다.
- **Spec drift measurement: static vs dynamic**: [yu2025]는 static spec 변환 정확도에 초점. [bhardwaj2026]는 runtime enforcement. 우리는 "dual-mode counterfactual backtest"라는 *dynamic 정량화*를 주장 — 양쪽 사이에 독자적 포지션.
- **Short-horizon edge의 재현성**: [briola2024, briola2025]는 deep model의 short-horizon LOB 예측 능력이 높다고 주장. 우리 첫 iteration 결과 (BTC 1h roc_168h strategy가 pooled EV를 BTC-only로 전달하지 못함, IR +2.35 but absolute -7%)는 short-horizon 재현성이 *symbol-dependent*라는 조심스러운 observation을 제공. 직접 반박은 아니지만 "cross-symbol robust도 개별 심볼로 오면 drift"라는 뉘앙스를 우리 데이터로 문서화 가능.

## Gaps (우리 프로젝트의 기여 공간)

- **LLM-generated 코드의 spec-invariant inference를 trading 도메인에 적용한 사례가 이 코퍼스에 없음**: [yu2025]는 hardware RTL, [bhardwaj2026]는 general autonomy. *LLM × LOB × runtime spec invariant* 삼각 교차가 uncovered — 정확히 C1.
- **Counterfactual PnL attribution (dual-mode normal vs strict)을 정량화한 작업이 이 코퍼스에 없음**: [papadakis2025]는 simulator dual-mode이지만 *LLM spec 위반 기여를 PnL 단위로 분리*하지는 않음 — 정확히 C2의 독창성.
- **Engine-agnostic measurement layer라는 포지셔닝 자체가 부재**: 대부분 single-engine 결과. 우리가 "(spec, fill-list) records 위에서 동작하는 측정 레이어"라고 framing하면 새 축을 만듦 — C3.
- **LLM × tick-level trading strategy generation 조합이 literature에 공백**: `docs/` 내 수집된 10편 (FactorMiner 등) 및 본 search 결과 10편 모두 합쳐 *LLM-agent chain이 tick 해상도에서 코드 생성*하는 사례 없음 — 우리 project가 이 blue ocean을 열 수 있음을 literature review 섹션에서 명시.

## 실행 메타데이터

- **생성 일시**: 2026-04-19T04:40:00Z
- **사용된 소스**: arXiv ✓ · OpenReview ✗ (credentials 미설정 — `OPENREVIEW_USERNAME` / `OPENREVIEW_PASSWORD` 환경 변수 필요) · Google Scholar ✓
- **파라미터**: `--top 10 --years 2` (2024–2026 범위)
- **원본 후보 수**: arXiv 48 (4 queries × ≤20 results) + Google Scholar 80 (4 queries × 20) = 128
- **중복 제거 후**: 106 고유 후보
- **최종 선정**: 10 (arxiv_only 범주)
- **학회별 상세 venue 매칭은 불가 (gscholar의 venue 텍스트가 비정형)** — 범주는 arxiv_only로 통합됨. OpenReview 자격 추가 후 재실행하면 NeurIPS/ICLR/ICML 등 정규 venue로 분류 가능.

## Follow-up 권장

1. **OpenReview credentials 설정 후 재실행** — NeurIPS D&B 트랙을 겨냥하므로 해당 venue에서 유사 투고 검색이 중요.
2. **docs/ 내 PDF와의 cross-reference** — 이미 수집된 10편 (FactorMiner, AlphaForgeBench 등)과 본 search 결과 간 중복/상보성 분석.
3. **Related Work 초안 작성** — 본 README의 Themes / Convergences / Disagreements / Gaps를 섹션 구조로 확장.
