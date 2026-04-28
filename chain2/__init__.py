"""Chain 2 — Execution layer.

Takes a Chain 1 SignalSpec (fixed entry trigger) + an ExecutionSpec
(order type, PT/SL/time_stop, fees) and measures realistic net PnL.

Pipeline (Phase 2.0 minimal):
  SignalSpec  + ExecutionSpec  → execution_runner  → BacktestResult_v2
                                                      (cost_breakdown included)

See docs/chain2_design.md for design rationale and phase roadmap.
"""
