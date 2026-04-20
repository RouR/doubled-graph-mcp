"""Shared meta block for tool responses."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from doubled_graph import __version__
from doubled_graph.policy.phase import Phase, read_phase


class Meta(BaseModel):
    phase: str
    tool_version: str = __version__
    timestamp_iso: str
    trace_id: str


def build_meta(repo_path: Path, trace_id: str | None = None) -> Meta:
    phase: Phase = read_phase(repo_path)
    return Meta(
        phase=phase,
        tool_version=__version__,
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        trace_id=trace_id or uuid.uuid4().hex[:12],
    )
