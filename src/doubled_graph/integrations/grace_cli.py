"""grace-cli (Bun binary) integration — subprocess wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GraceCLIMissing(RuntimeError):
    """Raised when `grace` executable is not in $PATH."""


@dataclass
class ModuleRecord:
    id: str
    purpose: str = ""
    exports: list[str] | None = None
    crosslinks: list[str] | None = None
    raw: dict | None = None


@dataclass
class FileRecord:
    path: str
    module_contract: str | None = None
    module_map: list[str] | None = None
    contracts: list[dict] | None = None
    blocks: list[dict] | None = None
    change_summary: list[dict] | None = None
    raw: dict | None = None


class GraceCLI:
    """Thin subprocess wrapper around the upstream `grace` CLI (Bun, MIT).

    Why this class: grace CLI is the only lightweight way to query grace
    artifacts (`docs/*.xml`, module records, file-level anchors) without
    re-implementing the parser. Everywhere in doubled-graph where we need
    those, we go through this wrapper — never shell out inline — so that:

      1. If `grace` CLI is missing, we fail with one consistent error
         (`GraceCLIMissing`) instead of cryptic FileNotFoundError.
      2. When upstream changes its flag names / stdout format, the fix is
         localized here (not in every caller).
      3. Our gateway commands (`doubled-graph lint|module|file`) have a
         predictable boundary to subprocess.
    """

    def __init__(self, repo_path: Path, command: str = "grace"):
        self.repo_path = repo_path
        self.command = command

    def _check(self) -> None:
        """Verify the grace binary is on PATH, auto-installing if a JS runtime is available."""
        if shutil.which(self.command) is not None:
            return

        _PACKAGE = "@osovv/grace-cli"
        _INSTALLERS = [
            ["bun", "add", "-g", _PACKAGE],
            ["npm", "install", "-g", _PACKAGE],
            ["yarn", "global", "add", _PACKAGE],
            ["pnpm", "add", "-g", _PACKAGE],
        ]
        for cmd in _INSTALLERS:
            if shutil.which(cmd[0]) is None:
                continue
            import sys
            print(f"`grace` not found — installing via {cmd[0]}…", file=sys.stderr)
            result = subprocess.run(cmd, capture_output=False)
            if result.returncode == 0 and shutil.which(self.command) is not None:
                return
            break  # installer found but failed — fall through to error

        raise GraceCLIMissing(
            f"`{self.command}` is not on $PATH and could not be installed automatically. "
            "Run manually: `npm install -g @osovv/grace-cli` (requires bun/npm/yarn/pnpm)."
        )

    def _run(self, args: list[str]) -> str:
        """Run `grace <args>` synchronously, capture stdout, raise on non-zero exit.

        Intentionally plain: no streaming, no async, no retries. Callers that
        need richer handling should wrap this, not fork it.
        """
        self._check()
        proc = subprocess.run(
            [self.command, *args],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"grace {' '.join(args)} failed (rc={proc.returncode}): {proc.stderr.strip()}"
            )
        return proc.stdout

    def lint(self, verbose: bool = False) -> dict:
        """Run `grace lint` — the upstream validator of anchors and references.

        Why we expose this: `grace lint` is a methodology gate (pre-commit and
        pre-merge). Exposing it through `doubled-graph lint` keeps CI configs
        tool-name-consistent (one binary in the scripts).
        """
        # TODO[integration]: confirm `grace lint --json` availability; else parse textual output.
        args = ["lint", "--path", str(self.repo_path)]
        if verbose:
            args.append("--verbose")
        out = self._run(args)
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"raw": out}

    def module_show(self, id_or_path: str, with_verification: bool = False) -> ModuleRecord:
        """Fetch module record: contract + exports + deps + (opt.) V-M-* list.

        Called from `on-before-edit` and `grace-fix`-style flows when the agent
        needs to read the contract BEFORE opening the code — saves context
        window, which matters a lot for local models.
        """
        args = ["module", "show", id_or_path, "--path", str(self.repo_path)]
        if with_verification:
            args += ["--with", "verification"]
        # TODO[integration]: confirm stdout schema. MVP stub: return raw.
        out = self._run(args)
        return ModuleRecord(id=id_or_path, raw={"stdout": out})

    def file_show(self, path: str, contracts: bool = True, blocks: bool = True) -> FileRecord:
        """Extract only anchor-framed sections of a file (not full content).

        The cornerstone of RAG-over-anchors: instead of dumping a 2000-line
        file into the LLM prompt, we fetch just CONTRACT + BLOCK_* the model
        needs. Without this, long files blow out local-model context budgets.
        """
        args = ["file", "show", path, "--path", str(self.repo_path)]
        if contracts:
            args.append("--contracts")
        if blocks:
            args.append("--blocks")
        out = self._run(args)
        return FileRecord(path=path, raw={"stdout": out})
