"""Signal function template (rendered per SignalSpec).

The code-generator copies this file, replaces the marked regions, and writes
the result under `iterations/iter_<N>/code/<spec_id>.py`.

Template version: v0.1.0_basic
"""
from __future__ import annotations

# === BEGIN GENERATED IMPORTS ===
# code-generator fills in the specific primitive imports here.
# Example output:
#   from signal_primitives import obi_1, microprice_dev_bps, spread_bps
# === END GENERATED IMPORTS ===


# === BEGIN GENERATED CONSTANTS ===
# code-generator fills in:
#   SPEC_ID: str
#   THRESHOLD: float
#   DIRECTION: str  ('long_if_pos' or 'long_if_neg')
#   HORIZON_TICKS: int
# === END GENERATED CONSTANTS ===


def signal(snap) -> float:
    """Compute the signal scalar from a single snapshot.

    Args:
        snap: Snapshot object or dict carrying bid_px, bid_qty, ask_px, ask_qty
              arrays (10 levels) and scalar fields TOTAL_*_RSQN,
              TOTAL_*_RSQN_ICDC, ACML_VOL, and an optional `_prev` attribute
              for stateful primitives.

    Returns:
        Scalar signal value. The orchestrator applies THRESHOLD/DIRECTION to
        convert this into an up/down prediction.
    """
    # === BEGIN GENERATED BODY ===
    # code-generator fills in the formula here. Example:
    #   return obi_1(snap)
    # or:
    #   obi = obi_1(snap)
    #   spr = spread_bps(snap)
    #   return obi if spr < 10.0 else 0.0
    # === END GENERATED BODY ===
    raise NotImplementedError("code-generator did not render BODY")
