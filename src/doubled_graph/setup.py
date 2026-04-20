"""`doubled-graph setup` — single-shot onboarding.

Runs the steps a first-time user would otherwise do by hand:

  1. Verify Bun is available (required by the upstream grace CLI).
  2. Install / verify `@osovv/grace-cli` globally via `bun add -g`.
  3. Copy bundled methodology assets (prompts/ + methodology/) into the repo.
     Assets live in `doubled_graph/data/...` inside the wheel, loaded via
     `importlib.resources`. No methodology-repo clone needed.
  4. Detect the user's IDE and register the MCP server:
       - Claude Code → `.mcp.json`
       - Cursor      → `.cursor/mcp.json`
       - Continue    → `.continue/config.json`
       - fallback    → print a manual instruction
  5. Install the `git post-commit` hook (`doubled-graph analyze --mode incremental`).
  6. Run the first full analyze pass (`doubled-graph analyze --mode full`).

Every step returns a structured record. Failures on optional steps (grace-cli,
analyze) are reported but do not fail the whole run — `ok` flips to False only
when a step that blocks usefulness (no IDE register, no hooks) errors out.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _detect_ide(repo: Path) -> str:
    """Best-effort IDE detection.

    Order: explicit markers in the repo win; otherwise check `which` for
    known IDE CLIs. Falls back to "none".
    """
    if (repo / ".claude").is_dir() or (repo / ".mcp.json").exists():
        return "claude-code"
    if (repo / ".cursor").is_dir():
        return "cursor"
    if (repo / ".continue").is_dir():
        return "continue"
    # CLI heuristics — last resort, user can override via --ide.
    if _have("claude"):
        return "claude-code"
    if _have("cursor"):
        return "cursor"
    return "none"


# ---------------------------------------------------------------------------
# bundled assets
# ---------------------------------------------------------------------------


def _copy_bundle(subdir: str, dest: Path, dry_run: bool) -> dict[str, Any]:
    """Copy a directory from `doubled_graph.data.<subdir>` into `dest`.

    Uses importlib.resources so this works both from an installed wheel and
    from an editable checkout. Missing bundle → surface, don't crash.
    """
    try:
        root = resources.files("doubled_graph").joinpath("data").joinpath(subdir)
    except (ModuleNotFoundError, AttributeError):
        return {"status": "skipped", "reason": f"bundle '{subdir}' not found in package"}

    if not root.is_dir():
        return {"status": "skipped", "reason": f"bundle '{subdir}' not present"}

    copied: list[str] = []
    skipped: list[str] = []

    def _walk(r, d: Path) -> None:
        for entry in r.iterdir():
            target = d / entry.name
            if entry.is_dir():
                if not dry_run:
                    target.mkdir(parents=True, exist_ok=True)
                _walk(entry, target)
            else:
                if target.exists():
                    skipped.append(str(target.relative_to(dest.parent)))
                    continue
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(entry.read_bytes())
                copied.append(str(target.relative_to(dest.parent)))

    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    _walk(root, dest)
    return {"status": "ok", "copied": copied, "skipped_existing": skipped, "dest": str(dest)}


# ---------------------------------------------------------------------------
# grace CLI (upstream Bun package)
# ---------------------------------------------------------------------------


def _install_grace_cli(dry_run: bool) -> dict[str, Any]:
    if not _have("bun"):
        return {
            "status": "bun_missing",
            "hint": "Install Bun from https://bun.sh/ then rerun `doubled-graph setup`.",
        }
    if _have("grace"):
        return {"status": "already_installed"}
    if dry_run:
        return {"status": "dry_run", "cmd": "bun add -g @osovv/grace-cli"}
    out = subprocess.run(
        ["bun", "add", "-g", "@osovv/grace-cli"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return {"status": "failed", "stderr": out.stderr.strip()[:400]}
    return {"status": "installed"}


# ---------------------------------------------------------------------------
# MCP registration per IDE
# ---------------------------------------------------------------------------


def _mcp_server_entry() -> dict[str, Any]:
    return {
        "command": "doubled-graph",
        "args": ["serve"],
    }


def _register_mcp(repo: Path, ide: str, dry_run: bool) -> dict[str, Any]:
    if ide == "none":
        return {
            "status": "manual",
            "hint": (
                "No supported IDE detected. Register doubled-graph manually as an "
                "MCP server with `command=doubled-graph args=['serve']`."
            ),
        }

    if ide == "claude-code":
        cfg = repo / ".mcp.json"
        return _merge_json_mcp(cfg, key="mcpServers", name="doubled-graph", dry_run=dry_run)
    if ide == "cursor":
        cfg = repo / ".cursor" / "mcp.json"
        return _merge_json_mcp(cfg, key="mcpServers", name="doubled-graph", dry_run=dry_run)
    if ide == "continue":
        cfg = repo / ".continue" / "config.json"
        return _merge_json_mcp(cfg, key="mcpServers", name="doubled-graph", dry_run=dry_run)
    return {"status": "unknown_ide", "ide": ide}


def _merge_json_mcp(cfg_path: Path, key: str, name: str, dry_run: bool) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as e:
            return {"status": "failed", "reason": f"invalid existing JSON at {cfg_path}: {e}"}
    servers = data.setdefault(key, {})
    if not isinstance(servers, dict):
        return {"status": "failed", "reason": f"{cfg_path}:{key} is not an object"}

    if name in servers:
        return {"status": "already_registered", "path": str(cfg_path)}
    servers[name] = _mcp_server_entry()
    if dry_run:
        return {"status": "dry_run", "path": str(cfg_path), "entry": servers[name]}
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "registered", "path": str(cfg_path)}


# ---------------------------------------------------------------------------
# hooks + first analyze
# ---------------------------------------------------------------------------


def _install_hooks(repo: Path, dry_run: bool) -> dict[str, Any]:
    if not (repo / ".git").exists():
        return {"status": "not_a_git_repo", "hint": "Run `git init` first."}
    from doubled_graph.hooks_installer import install_hooks

    report = install_hooks(repo_path=repo, post_commit=True, dry_run=dry_run)
    return {"status": "ok", "report": report}


def _first_analyze(repo: Path, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"status": "dry_run", "cmd": "doubled-graph analyze --mode full"}
    from doubled_graph.tools.analyze import analyze

    try:
        res = analyze(repo_path=repo, mode="full", force=True)
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "detail": f"{type(e).__name__}: {e}"}
    return {
        "status": "ok",
        "mode_used": res.mode_used,
        "duration_ms": res.duration_ms,
        "warnings": [w.code for w in res.warnings],
    }


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


def run_setup(
    repo_path: Path,
    ide: str = "auto",
    skip_grace_cli: bool = False,
    skip_hooks: bool = False,
    skip_analyze: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {"repo": str(repo_path), "dry_run": dry_run}

    # 1. Grace CLI
    report["grace_cli"] = (
        {"status": "skipped"} if skip_grace_cli else _install_grace_cli(dry_run)
    )

    # 2. Bundled prompts + methodology
    report["prompts"] = _copy_bundle("prompts", repo_path / "prompts", dry_run)
    report["methodology"] = _copy_bundle("methodology", repo_path / "methodology", dry_run)

    # 3. IDE MCP registration
    resolved_ide = ide if ide != "auto" else _detect_ide(repo_path)
    report["ide_detected"] = resolved_ide
    report["mcp_register"] = _register_mcp(repo_path, resolved_ide, dry_run)

    # 4. Hooks
    report["hooks"] = {"status": "skipped"} if skip_hooks else _install_hooks(repo_path, dry_run)

    # 5. First analyze
    report["analyze"] = (
        {"status": "skipped"} if skip_analyze else _first_analyze(repo_path, dry_run)
    )

    # Overall ok: MCP registered (or manual hint returned) + hooks installed (or skipped).
    mcp_ok = report["mcp_register"]["status"] in (
        "registered", "already_registered", "manual", "dry_run"
    )
    hooks_ok = report["hooks"]["status"] in ("ok", "skipped")
    report["ok"] = mcp_ok and hooks_ok
    return report
