"""Filesystem layout of .doubled-graph/."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def root(repo_path: Path) -> Path:
    return repo_path / ".doubled-graph"


def cache_dir(repo_path: Path) -> Path:
    d = root(repo_path) / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir(repo_path: Path) -> Path:
    d = root(repo_path) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fingerprint_path(repo_path: Path) -> Path:
    return cache_dir(repo_path) / "code-fingerprint.json"


def declared_cache_path(repo_path: Path) -> Path:
    return cache_dir(repo_path) / "declared.json"


def crossref_cache_path(repo_path: Path) -> Path:
    return cache_dir(repo_path) / "crossref.json"


def today_log_path(repo_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return logs_dir(repo_path) / f"{stamp}.jsonl"
