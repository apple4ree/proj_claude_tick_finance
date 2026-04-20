# Limit Order Book Dynamics in Matching Markets: Microstructure, Spread, and Execution Slippage

**Authors:** Yao Wu
**Venue:** None 2025
**Links:** [arXiv](https://arxiv.org/abs/2511.20606v2) · [PDF](https://arxiv.org/pdf/2511.20606v2)

## Abstract
Conventional models of matching markets assume that monetary transfers can clear markets by compensating for utility differentials. However, empirical patterns show that such transfers often fail to close structural preference gaps. This paper introduces a market microstructure framework that models matching decisions as a limit order book system with rigid bid ask spreads. Individual preferences are represented by a latent preference state matrix, where the spread between an agent's internal ask price (the unconditional maximum) and the market's best bid (the reachable maximum) creates a structural liquidity constraint. We establish a Threshold Impossibility Theorem showing that linear compensation cannot close these spreads unless it induces a categorical identity shift. A dynamic discrete choice execution model further demonstrates that matches occur only when the market to book ratio crosses a time decaying liquidity threshold, analogous to order execution under inventory pressure. Numerical experiments validate persistent slippage, regional invariance of preference orderings, and high tier zero spread executions. The model provides a unified microstructure explanation for matching failures, compensation inefficiency, and post match regret in illiquid order driven environments.

## 한줄 요약
Limit Order Book Dynamics in Matching Markets: Microstructure, Spread, and Execution Slippage — 2025년 Wu의 작업.

## 왜 이 프로젝트와 관련 있는가
Matching market에서의 spread + execution slippage — 우리 엔진의 queue-position fills + 5ms latency 가정과 비교 가능. execution slippage measurement 측면.

## BibTeX
```bibtex
@article{wu2025,
  title = { Limit Order Book Dynamics in Matching Markets: Microstructure, Spread, and Execution Slippage },
  author = { Yao Wu },
  year = {2025},
  journal = {None}
}
```
