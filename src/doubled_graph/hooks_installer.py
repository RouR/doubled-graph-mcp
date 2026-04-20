"""Install hooks: git post-commit + Claude Code PostToolUse (+ optional prepare-commit-msg).

Behavior contract lives in HOOKS.md. This module is side-effecting on disk,
so every action is reported in the returned dict for the caller to print.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

POST_COMMIT_SCRIPT = """#!/usr/bin/env bash
# Installed by doubled-graph init-hooks (v0.1.0)
# Purpose: refresh computed graph after commit. See HOOKS.md §1.
# To disable: chmod -x .git/hooks/post-commit

set -u

if ! command -v doubled-graph >/dev/null 2>&1; then
  exit 0
fi

if [[ "${DOUBLED_GRAPH_INHIBIT_HOOK:-0}" = "1" ]]; then
  exit 0
fi

(
  doubled-graph analyze --mode incremental --since-ref HEAD~1 --silent \\
    >> .doubled-graph/logs/post-commit.log 2>&1
) &

exit 0
"""


CLAUDE_HOOK_ENTRY = {
    "matcher": "Edit|Write|MultiEdit",
    "hooks": [
        {
            "type": "command",
            "command": 'doubled-graph analyze --mode incremental --paths "$CLAUDE_FILE_PATH" --silent',
        }
    ],
}


def _ensure_storage(repo: Path) -> None:
    (repo / ".doubled-graph" / "logs").mkdir(parents=True, exist_ok=True)
    (repo / ".doubled-graph" / "cache").mkdir(parents=True, exist_ok=True)


def _install_post_commit(repo: Path, dry_run: bool) -> dict:
    hooks_dir = repo / ".git" / "hooks"
    if not hooks_dir.exists():
        return {"post_commit": "skipped", "reason": f".git/hooks not found at {hooks_dir}"}
    target = hooks_dir / "post-commit"
    action = "replace" if target.exists() else "create"
    if dry_run:
        return {"post_commit": "dry-run", "action": action, "path": str(target)}

    # Soft-safety: if file exists and is non-empty AND doesn't contain our signature — back up.
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        if "doubled-graph init-hooks" not in existing:
            backup = target.with_suffix(".backup")
            target.rename(backup)
            replaced = f"existing hook preserved at {backup}"
        else:
            replaced = "existing doubled-graph hook overwritten"
    else:
        replaced = None

    target.write_text(POST_COMMIT_SCRIPT, encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {"post_commit": "installed", "path": str(target), "note": replaced}


def _install_claude_code(repo: Path, dry_run: bool) -> dict:
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"claude_code": "error", "reason": f"cannot parse {settings}"}
    hooks = data.setdefault("hooks", {})
    post_tool_use = hooks.setdefault("PostToolUse", [])

    already = any(
        h.get("matcher") == CLAUDE_HOOK_ENTRY["matcher"]
        and any("doubled-graph" in (c.get("command", "") or "") for c in h.get("hooks", []))
        for h in post_tool_use
        if isinstance(h, dict)
    )
    if already:
        return {"claude_code": "already_present", "path": str(settings)}
    if dry_run:
        return {"claude_code": "dry-run", "path": str(settings), "would_add": CLAUDE_HOOK_ENTRY}

    post_tool_use.append(CLAUDE_HOOK_ENTRY)
    settings.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"claude_code": "installed", "path": str(settings)}


def install_hooks(
    repo_path: Path,
    post_commit: bool = False,
    claude_code: bool = False,
    prepare_commit_msg: bool = False,
    dry_run: bool = False,
) -> dict:
    """Install the methodology's automation hooks.

    Why this is a single entry point: the methodology requires (or strongly
    recommends) three hooks working together — git post-commit baseline,
    Claude Code PostToolUse accelerator, and optional prepare-commit-msg
    provenance. Installing them one-by-one from README instructions is fragile
    (merges with existing hooks, JSON-merge bugs). `doubled-graph init-hooks`
    is the single tested path that handles those edge cases.
    """
    _ensure_storage(repo_path)
    report: dict = {"repo": str(repo_path), "dry_run": dry_run}

    if not (post_commit or claude_code or prepare_commit_msg):
        # Default: install the baseline post-commit only.
        post_commit = True

    if post_commit:
        report.update(_install_post_commit(repo_path, dry_run))
    if claude_code:
        report.update(_install_claude_code(repo_path, dry_run))
    if prepare_commit_msg:
        report["prepare_commit_msg"] = "not_implemented_in_mvp"

    # Ensure .gitignore covers our cache/logs (but not config.json).
    gi = repo_path / ".gitignore"
    add_lines = [".doubled-graph/logs/", ".doubled-graph/cache/"]
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    missing = [line for line in add_lines if line not in existing]
    if missing and not dry_run:
        with gi.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n# doubled-graph\n" + "\n".join(missing) + "\n")
        report["gitignore"] = f"appended: {missing}"
    elif missing:
        report["gitignore"] = f"would-append: {missing}"

    return report
