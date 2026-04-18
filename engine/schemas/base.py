"""Base class for all handoff schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class HandoffBase(BaseModel):
    """Common fields every agent handoff must carry."""

    model_config = ConfigDict(extra="forbid")

    strategy_id: Optional[str]
    timestamp: datetime
    agent_name: Literal["alpha-designer", "execution-designer", "feedback-analyst"]
    model_version: str
    draft_md_path: str
