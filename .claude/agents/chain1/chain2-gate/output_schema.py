"""Output schema for chain2-gate (stage 6_promotion_gate)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import Chain2GateOutput  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402


class GateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_output: Chain2GateOutput
