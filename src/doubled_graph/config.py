"""Configuration loading for `.doubled-graph/config.json`."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CGCConfig(BaseModel):
    backend: str = "auto"
    backend_overrides: dict[str, str] = Field(default_factory=dict)


class Config(BaseModel):
    version: str = "1"
    repo_name: str = "unknown"
    repo_path: str
    cgc: CGCConfig = Field(default_factory=CGCConfig)
    grace_cli_command: str = "grace"
    phase_source: str = "AGENTS.md"
    phase_default: str = "post_migration"


def config_path(repo_path: Path) -> Path:
    return repo_path / ".doubled-graph" / "config.json"


def load_config(repo_path: Path) -> Config:
    """Load config or return a defaults-populated instance if missing."""
    p = config_path(repo_path)
    if not p.exists():
        return Config(repo_name=repo_path.name, repo_path=str(repo_path))
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Config(**data)


def save_config(repo_path: Path, cfg: Config) -> None:
    p = config_path(repo_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, indent=2)
