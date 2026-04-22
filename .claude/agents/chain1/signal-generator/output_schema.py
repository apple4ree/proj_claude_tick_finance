"""Output schema for signal-generator (stage ①)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import SignalSpec  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field, model_validator  # noqa: E402


class GenerateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specs: list[SignalSpec] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _unique_spec_ids(self) -> GenerateOutput:
        ids = [s.spec_id for s in self.specs]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate spec_ids: {ids}")
        return self
