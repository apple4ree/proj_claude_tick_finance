# Experiments Directory

Each experiment is self-contained with:
- `spec.md` or `README.md` — experiment design + hypothesis
- `run.py` or `*.py` — reproduction script (or reference to `scripts/`)
- `results.json` — primary aggregate output
- `per_run/` — individual run artifacts if applicable
- `figures/` — experiment-specific figures

## Experiment Index

| ID | Name | Purpose | Status |
|---|---|---|---|
| exp_a | Tick pilot corpus | Baseline 4-mode failure taxonomy | Done (n=20 in `strategies/strat_*`) |
| exp_b | Horizon sweep (BTC) | Fee-saturation threshold $h^*$ | Done (results.json); expand to ETH/SOL → exp_g |
| exp_c | Prompt intervention | Mitigation map simulation | Simulation done; live partial pending |
| exp_d | Adversarial recall | Invariant checker calibration | Done (7/7 PASS) |
| exp_e | Cross-engine parity | Engine-agnostic claim | Done (F7 parity) |
| exp_f | Bar positive control | Profitability @ daily horizon | Done (n=15 in `strategies/bar_*`) |
| exp_g | Multi-symbol horizon sweep | Generalize exp_b to 3 symbols | **In progress (this session)** |
| exp_h | Risk-adjusted metrics | Calmar/Sortino/alpha-vs-BH | **In progress** |
| exp_i | Live prompt intervention | Validate simulation (exp_c) | **In progress** |

## Artifact Standard

Every strategy run should produce in its strategy directory:
- `spec.yaml`, `strategy.py` — configuration & logic
- `report.json` — metrics (return, sharpe, MDD, roundtrips, violations)
- `trace.json` — fills + equity_curve + mid_series
- `analysis_trace.json`, `analysis_trace.md` — FIFO-matched roundtrips + summary
- `report.html` — interactive Plotly report
- `equity_dd.png` — static snapshot

Produced by `scripts/bar_full_artifacts.py` (bar) or `engine/runner` + `scripts/analyze_trace.py` (tick).
