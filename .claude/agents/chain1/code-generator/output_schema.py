"""Output schema for code-generator (stage ②.5)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))

from schemas import GeneratedCode  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402


class CodegenOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: GeneratedCode
