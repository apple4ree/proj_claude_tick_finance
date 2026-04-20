# QuantCode-Bench: A Benchmark for Evaluating the Ability of Large Language Models to Generate Executable Algorithmic Trading Strategies

**Authors:** Alexey Khoroshilov, Alexey Chernysh, Orkhan Ekhtibarov, Nini Kamkia, Dmitry Zmitrovich
**Venue:** arxiv_only 2026
**Confidence:** low
**Links:** [arXiv](http://arxiv.org/abs/2604.15151v1) · [PDF](https://arxiv.org/pdf/2604.15151v1)

## Abstract
Large language models have demonstrated strong performance on general-purpose programming tasks, yet their ability to generate executable algorithmic trading strategies remains underexplored. Unlike standard code benchmarks, trading-strategy generation requires simultaneous mastery of domain-specific financial logic, knowledge of a specialized API, and the ability to produce code that is not only syntactically correct but also leads to actual trades on historical data. In this work, we present QuantCode-Bench, a benchmark for the systematic evaluation of modern LLMs in generating strategies for the Backtrader framework from textual descriptions in English. The benchmark contains 400 tasks of varying difficulty collected from Reddit, TradingView, StackExchange, GitHub, and synthetic sources. Evaluation is conducted through a multi-stage pipeline that checks syntactic correctness, successful backtest execution, the presence of trades, and semantic alignment with the task description using an LLM judge. We compare state-of-the-art models in two settings: single-turn, where the strategy must be generated correctly on the first attempt, and agentic multi-turn, where the model receives iterative feedback and may repair its errors. We analyze the failure modes across different stages of the pipeline and show that the main limitations of current models are not related to syntax, but rather to the correct operationalization of trading logic, proper API usage, and adherence to task semantics. These findings suggest that trading strategy generation constitutes a distinct class of domain-specific code generation tasks in which success requires not only technical correctness, but also alignment between natural-language descriptions, financial logic, and the observable behavior of the strategy on data.

## TL;DR
QuantCode-Bench: A Benchmark for Evaluating the Ability of Large Language Models to Generate Executable Algorithmic Trading Strategies — abstract 기반 1줄 요약은 본 파일 Abstract 블록과 ## 왜 관련 있는가 참조.

## Method
Abstract만으로 method 세부는 부분적. 풀 논문에서 (a) pipeline, (b) evaluation 방법, (c) dataset/benchmark 확인 필요.

## Result
Abstract가 수치 claim을 제공하는 경우 그대로, 아니면 '개선 주장 + 비교 대상'만 기재. 상세 수치는 풀 논문.

## Critical Reading
- 평가 해상도 (bar/tick/order-level) 확인 필요
- Reproducibility (model version, seed, data window) 공개 여부
- 우리 C4 4 failure modes 관점에서 어느 축(spec drift / micro-domain / handoff / invariant blindspot)이 누락인지

## 왜 이 프로젝트와 관련 있는가
가장 직접 경쟁작 (2026): LLM-generated executable algorithmic trading strategies의 전용 벤치마크. 우리 paper는 'bar-level pass rate가 높아도 tick-level fidelity는 무너진다'는 논증을 하므로 QuantCode-Bench의 평가 해상도(bar vs tick)를 §2 Related Work 및 §5 결과에서 반드시 대조. 우리 C4 프레이밍의 primary target.

## Figures
<!-- Figure extraction 결과가 있으면 이 섹션에 자동 append됨. 빈 채로 두면 extraction 실패/paywall. -->

## BibTeX
```bibtex
@article{khoroshilov2026quantcode,
  title = {QuantCode-Bench: A Benchmark for Evaluating the Ability of Large Language Models to Generate Executable Algorithmic Trading Strategies},
  author = {Alexey Khoroshilov and Alexey Chernysh and Orkhan Ekhtibarov and Nini Kamkia and Dmitry Zmitrovich},
  year = {2026},
  booktitle = {arXiv},
  eprint = {2604.15151v1},
  archivePrefix = {arXiv},
  url = {http://arxiv.org/abs/2604.15151v1},
}
```
