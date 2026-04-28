"""Chain 1.5 — Signal enhancement layer.

Takes a Chain 1 SignalSpec (fixed entry trigger) and optimizes:
  - Exit policy: PT / SL / trailing (early-exit within max_hold)
  - max_hold_ticks: tick-level time cap
  - Optional extra regime_gate

Still uses mid-to-mid pricing (no fees, no spread). Chain 2 later applies
real-world execution on top of a Chain 1.5 EnhancedSignalSpec.
"""
