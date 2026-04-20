"""`analyze` tool — full or incremental re-index of computed graph."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from doubled_graph.integrations.cgc import CGC, CGCUnavailable
from doubled_graph.storage import paths as sp
from doubled_graph.tools._meta import Meta, build_meta


class AnalyzeWarning(BaseModel):
    code: str
    file: str | None = None
    detail: str = ""


class AnalyzeStats(BaseModel):
    files_processed: int = 0
    symbols_added: int = 0
    symbols_removed: int = 0
    symbols_updated: int = 0
    edges_added: int = 0
    edges_removed: int = 0


class AnalyzeResult(BaseModel):
    mode_used: str
    duration_ms: int = 0
    stats: AnalyzeStats = Field(default_factory=AnalyzeStats)
    warnings: list[AnalyzeWarning] = Field(default_factory=list)
    meta: Meta


def _git_head(repo: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def _git_changed_files(repo: Path, since_ref: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", since_ref, "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _haskell_warnings(files: list[str]) -> list[AnalyzeWarning]:
    return [
        AnalyzeWarning(
            code="HASKELL_PARSER_UNSTABLE",
            file=f,
            detail="CGC tree-sitter-haskell parser is marked modified/unstable in the vendored snapshot.",
        )
        for f in files
        if f.endswith(".hs")
    ]


def _write_fingerprint(repo: Path, mode_used: str, head: str, files: list[str]) -> None:
    payload = {
        "head": head,
        "mode": mode_used,
        "files": files,
        "updated_iso": datetime.now(timezone.utc).isoformat(),
    }
    try:
        sp.fingerprint_path(repo).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def analyze(
    repo_path: Path,
    mode: str = "auto",
    since_ref: str | None = None,
    paths: list[str] | None = None,
    force: bool = False,
) -> AnalyzeResult:
    """Entry point shared by CLI (`doubled-graph analyze`) and MCP tool.

    Both hooks (post-commit / PostToolUse) and MCP clients converge here so
    logging, phase-policy, warnings, and fingerprint all behave consistently.
    """
    meta = build_meta(repo_path)
    warnings: list[AnalyzeWarning] = []
    t0 = time.monotonic()

    resolved_mode = mode
    if mode == "auto":
        resolved_mode = "full" if force or not sp.fingerprint_path(repo_path).exists() else "incremental"

    changed: list[str] = []
    if resolved_mode == "incremental":
        ref = since_ref or "HEAD~1"
        changed = _git_changed_files(repo_path, ref)
        if paths:
            changed = [c for c in changed if any(c.startswith(p) for p in paths)]
        warnings.extend(_haskell_warnings(changed))

    cgc = CGC(repo_path)
    stats = AnalyzeStats()
    try:
        if resolved_mode == "full":
            s = cgc.analyze_full()
        else:
            s = cgc.analyze_incremental([Path(p) for p in changed])
        stats = AnalyzeStats(
            files_processed=s.files_processed,
            symbols_added=s.symbols_added,
            symbols_removed=s.symbols_removed,
            symbols_updated=s.symbols_updated,
            edges_added=s.edges_added,
            edges_removed=s.edges_removed,
        )
        _write_fingerprint(repo_path, resolved_mode, _git_head(repo_path), changed)
    except CGCUnavailable as e:
        warnings.append(AnalyzeWarning(code="CGC_BACKEND_FAIL", detail=str(e)))
    except Exception as e:  # noqa: BLE001 — surface any unexpected CGC failure as a warning, not a crash
        warnings.append(
            AnalyzeWarning(
                code="CGC_ANALYZE_FAIL",
                detail=f"{type(e).__name__}: {e}",
            )
        )

    result = AnalyzeResult(
        mode_used=resolved_mode,
        duration_ms=int((time.monotonic() - t0) * 1000),
        stats=stats,
        warnings=warnings,
        meta=meta,
    )

    try:
        with sp.today_log_path(repo_path).open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "analyze", "result": result.model_dump(mode="json")}) + "\n")
    except OSError:
        pass

    return result
