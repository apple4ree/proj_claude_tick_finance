# AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models

**Authors:** W Zhang, M Zhao, J Gao, J You, H Jia, Y Zhao
**Venue:** arxiv_only 2026
**Confidence:** low
**Links:** [arXiv](https://arxiv.org/abs/2602.18481) · [PDF](https://arxiv.org/pdf/2602.18481)

## Abstract
introduces a hierarchical multi-agent system with conceptual  of whether the market is  cryptocurrency or US equity. This  trading benchmarks remain insufficient for measuring an LLM

## TL;DR
AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models — abstract 기반 1줄 요약은 본 파일 Abstract 블록과 ## 왜 관련 있는가 참조.

## Method
Abstract만으로 method 세부는 부분적. 풀 논문에서 (a) pipeline, (b) evaluation 방법, (c) dataset/benchmark 확인 필요.

## Result
Abstract가 수치 claim을 제공하는 경우 그대로, 아니면 '개선 주장 + 비교 대상'만 기재. 상세 수치는 풀 논문.

## Critical Reading
- 평가 해상도 (bar/tick/order-level) 확인 필요
- Reproducibility (model version, seed, data window) 공개 여부
- 우리 C4 4 failure modes 관점에서 어느 축(spec drift / micro-domain / handoff / invariant blindspot)이 누락인지

## 왜 이 프로젝트와 관련 있는가
paper_outline.md §1 abstract와 §2 Related Work에서 이미 직접 baseline으로 명시. KDD'26 AlphaForgeBench는 daily OHLCV 해상도에서 hierarchical multi-agent trading을 평가 → 우리 핵심 C4 'bar-level 평가가 실패 모드를 가린다' 주장의 primary target.

## Figures

![Figure 1](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-01.png)
> Figure 1: Figure 1: The framework of AlphaForgeBench.

![Figure 2](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-02.png)
> Figure 2: Figure 2: Multi-metric radar profiles on LLM-augmented

![Figure 3](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-03.png)
> Figure 3: Figure 3: Sharpe Ratio by difficulty level on LLM-augmented

![Figure 4](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-04.png)
> Figure 4: Figure 4: Sharpe Ratio by asset on LLM-augmented queries

![Figure 5](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-05.png)
> Figure 5: Figure 5: Aligned cumulative return curves on LLM-

![Figure 6](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-06.png)
> Figure 6: Figure 6: Cross-run instability of gemini-3-pro-preview under different decoding temperatures.

![Figure 7](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-07.png)
> Figure 7: Figure 7: Decision instability across decoding temperatures

![Figure 8](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-08.png)
> Figure 8: Figure 8: Cross-run instability of gemini-3-flash-preview under different decoding temperatures.

![Figure 9](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-09.png)
> Figure 9: Figure 9: Decision instability across decoding temperatures

![Figure 10](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-10.png)
> Figure 10: Figure 10: Cross-run instability of deepseek-v3.2 under different decoding temperatures.

![Figure 11](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-11.png)
> Figure 11: Figure 11: Decision instability across decoding temperatures

![Figure 12](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-12.png)
> Figure 12: Figure 12: Cross-run instability of grok-4.1-fast under different decoding temperatures.

![Figure 13](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-13.png)
> Figure 13: Figure 13: Decision instability across decoding temperatures (grok-

![Figure 14](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-14.png)
> Figure 14: Figure 14: Cross-run instability of claude-sonnet-4.5 under different decoding temperatures.

![Figure 15](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-15.png)
> Figure 15: Figure 15: Decision instability across decoding temperatures

![Figure 16](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-16.png)
> Figure 16: Figure 16: Cross-run instability of gpt-5.2 under different decoding temperatures.

![Figure 17](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-17.png)
> Figure 17: Figure 17: Decision instability across decoding temperatures (gpt-

![Figure 18](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-18.png)
> Figure 18: Figure 18 exhibit clear separation and distinct characteristic shapes that are reproducible. Several patterns emerge:

![Figure 19](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-18.png)
> Figure 19: Figure 18: Normalized radar chart of model performance on the Stage 1 real-world benchmark across five metrics. Each

![Figure 20](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-19.png)
> Figure 20: Figure 19: Grouped bar chart comparing Sharpe Ratio (SR), Annualized Return Rate (ARR), and Sortino Ratio (SoR) across six

![Figure 21](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-20.png)
> Figure 21: Figure 20: Per-asset grouped bar chart comparing six LLMs across key metrics on the Stage 1 real-world benchmark. Each

![Figure 22](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-21.png)
> Figure 22: Figure 21: Per-asset box plot of strategy performance distributions on the Stage 1 real-world benchmark. Each box summarizes

![Figure 23](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-22.png)
> Figure 23: Figure 22 shows the distribution of four core financial metrics (Sharpe Ratio, Maximum Drawdown, Annualized Return, and Number of

![Figure 24](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-22.png)
> Figure 24: Figure 22: Distribution of core financial metrics across six LLMs on the Stage 1 real-world benchmark. Each box summarizes 633

![Figure 25](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-23.png)
> Figure 25: Figure 23: Aligned return curves across all assets (smoothed with 20-query moving average, 25–75% quantile band). Queries

![Figure 26](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-24.png)
> Figure 26: Figure 24: Per-asset aligned return curves (Part 1: BTCUSDT, ETHUSDT, AAPL, GOOGL).

![Figure 27](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-25.png)
> Figure 27: Figure 25: Per-asset aligned return curves (Part 2: MSFT, NVDA, TSLA).

![Figure 28](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-26.png)
> Figure 28: Figure 26: Radar chart of normalized model performance on the Stage 2 benchmark across five metrics at both temperature

![Figure 29](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-27.png)
> Figure 29: Figure 27: Heatmap of Sharpe Ratio across models and difficulty levels on the Stage 2 benchmark. Darker colors indicate

![Figure 30](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-28.png)
> Figure 30: Figure 28: Grouped bar chart of Sharpe Ratio across difficulty levels (L1, L2, L3) for six LLMs on the Stage 2 benchmark.

![Figure 31](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-29.png)
> Figure 31: Figure 29: Performance trends across difficulty levels (model-averaged). Core metrics generally decline from Level 1 to Level

![Figure 32](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-30.png)
> Figure 32: Figure 30: Detailed performance breakdown across 9 fine-grained difficulty levels. Each level (L1, L2, L3) is subdivided into easy,

![Figure 33](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-31.png)
> Figure 33: Figure 31: Boxplot distributions across 9 fine-grained difficulty levels. Box boundaries represent the interquartile range (IQR),

![Figure 34](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-32.png)
> Figure 34: Figure 32: Boxplot distributions aggregated by three main difficulty levels (L1, L2, L3). This coarse-grained view highlights the

![Figure 35](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-33.png)
> Figure 35: Figure 33: Comparison of standard deviation and mean performance across temperature settings (T=0.0 vs T=0.7). The minimal

![Figure 36](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-34.png)
> Figure 36: Figure 34 provides a visual summary of model performance across all seven assets, facilitating direct comparison of asset-specific

![Figure 37](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-34.png)
> Figure 37: Figure 34: Grouped bar chart of model performance across all seven assets (BTCUSDT, ETHUSDT, AAPL, GOOGL, MSFT, NVDA,

![Figure 38](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-35.png)
> Figure 38: Figure 35: Model performance ranking visualization. Bar heights represent aggregate performance scores computed across all

![Figure 39](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-36.png)
> Figure 39: Figure 36: Grouped bar chart comparing all models across core metrics. Each metric is normalized to facilitate cross-metric

![Figure 40](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-37.png)
> Figure 40: Figure 37: Boxplot distributions by model across all evaluation instances. Box width (IQR) indicates consistency, with narrow

![Figure 41](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-38.png)
> Figure 41: Figure 38: Robustness analysis showing performance stability across multiple runs.

![Figure 42](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-39.png)
> Figure 42: Figure 39: Cross-asset robustness analysis. Box plots show performance distribution across 7 different assets.

![Figure 43](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-40.png)
> Figure 43: Figure 40: gemini-3-pro-preview performance across 9 difficulty levels.

![Figure 44](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-41.png)
> Figure 44: Figure 41: Best-performing strategies generated by gemini-3-pro-preview.

![Figure 45](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-42.png)
> Figure 45: Figure 42: gpt-5.2 performance across 9 difficulty levels.

![Figure 46](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-43.png)
> Figure 46: Figure 43: Best-performing strategies generated by gpt-5.2.

![Figure 47](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-44.png)
> Figure 47: Figure 44: claude-sonnet-4.5 performance across 9 difficulty levels.

![Figure 48](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-45.png)
> Figure 48: Figure 45: Best-performing strategies generated by claude-sonnet-4.5.

![Figure 49](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-46.png)
> Figure 49: Figure 46: gemini-3-flash-preview performance across 9 difficulty levels.

![Figure 50](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-47.png)
> Figure 50: Figure 47: Best-performing strategies generated by gemini-3-flash-preview.

![Figure 51](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-48.png)
> Figure 51: Figure 48: deepseek-v3.2 performance across 9 difficulty levels.

![Figure 52](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-49.png)
> Figure 52: Figure 49: Best-performing strategies generated by deepseek-v3.2.

![Figure 53](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-50.png)
> Figure 53: Figure 50: grok-4.1-fast performance across 9 difficulty levels.

![Figure 54](2026-zhang-alphaforgebench-benchmarking-end-to-end-trading-strategy/figures/fig-51.png)
> Figure 54: Figure 51: Best-performing strategies generated by grok-4.1-fast.


## BibTeX
```bibtex
@inproceedings{zhang2026alphaforgebench,
  title = {AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models},
  author = {W Zhang and M Zhao and J Gao and J You and H Jia and Y Zhao},
  year = {2026},
  booktitle = {arXiv preprint arXiv …},
  url = {https://arxiv.org/abs/2602.18481},
}
```
