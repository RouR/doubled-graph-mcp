"""Minimal CLI dispatcher — wraps MCP server + utility subcommands.

Why this CLI exists:
  doubled-graph is the single gateway between the methodology and its two
  underlying tools (CodeGraphContext and grace-marketplace CLI). Every user
  or agent interaction goes through `doubled-graph <subcommand>`. The CLI
  never contains business logic — it just dispatches into tools/ or
  integrations/.

Subcommand groups:
  Direct-action (our tool):
    - serve            : start MCP server (stdio JSON-RPC)
    - analyze          : build/refresh computed graph (wraps CGC library)
    - init-hooks       : install git + Claude Code hooks
    - status           : print config, phase, index freshness
    - phase            : read or switch phase (migration <-> post_migration)

  Wrappers over `grace` CLI (upstream, Bun) — methodology talks to these
  through doubled-graph so the user never sees two tool names:
    - lint             : grace lint
    - module show/find : grace module show / find
    - file show        : grace file show

  Stubs (returning NOT_IMPLEMENTED_MVP until Phase 5 follow-up):
    - impact, context, detect-changes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_serve(_args: argparse.Namespace) -> int:
    """Start the MCP server on stdio."""
    from doubled_graph.server import run_stdio

    run_stdio()
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    from doubled_graph.tools.analyze import analyze

    repo = Path(args.repo or ".").resolve()
    result = analyze(
        repo_path=repo,
        mode=args.mode,
        since_ref=args.since_ref,
        paths=args.paths,
        force=args.force,
    )
    if not args.silent:
        print(json.dumps(result.model_dump(), indent=2, default=str))
    return 0


def _cmd_init_hooks(args: argparse.Namespace) -> int:
    from doubled_graph.hooks_installer import install_hooks

    repo = Path(args.repo or ".").resolve()
    report = install_hooks(
        repo_path=repo,
        post_commit=args.post_commit or args.all,
        claude_code=args.claude_code or args.all,
        prepare_commit_msg=args.prepare_commit_msg,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """Summary of repo state: active config + current phase.

    Used by CI and by agents at session start to verify the gateway sees the
    repo correctly before any destructive action.
    """
    from doubled_graph.config import load_config
    from doubled_graph.policy.phase import read_phase

    repo = Path(args.repo or ".").resolve()
    cfg = load_config(repo)
    phase = read_phase(repo)
    print(json.dumps({"config": cfg.model_dump(), "phase": phase}, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# Wrappers over `grace` CLI (upstream Bun tool). Kept thin — we do NOT
# interpret output here, just forward. Methodology references these names
# (`doubled-graph lint`, `doubled-graph module show`, …) so users and agents
# have a single entry point. If the upstream grace CLI signature changes, the
# change is localized in `integrations/grace_cli.py`.
# ---------------------------------------------------------------------------


def _cmd_lint(args: argparse.Namespace) -> int:
    """`grace lint` gateway — validates anchor pairing, block uniqueness, cross-refs.

    Methodology invariant: this gate runs before commit and in CI. Exposing it
    via our CLI keeps the methodology tool-name-consistent (one namespace).
    """
    from doubled_graph.integrations.grace_cli import GraceCLI, GraceCLIMissing

    # `--path` is an alias for `--repo` (upstream `grace lint --path .` uses
    # the same semantic — we accept both so hand-typed invocations from docs
    # work without rewording).
    repo = Path(args.path or args.repo or ".").resolve()
    try:
        result = GraceCLI(repo).lint(verbose=bool(args.verbose))
    except GraceCLIMissing as e:
        print(json.dumps({"error": "GRACE_CLI_MISSING", "detail": str(e)}), file=sys.stderr)
        return 3
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_module_show(args: argparse.Namespace) -> int:
    """`grace module show <id|path>` gateway — module record with optional verification.

    Agents use this to read MODULE_CONTRACT + dependencies + (opt) V-M-* before
    edits. Single entry via doubled-graph avoids agents drifting between tool
    names across prompts.
    """
    from doubled_graph.integrations.grace_cli import GraceCLI, GraceCLIMissing

    repo = Path(args.repo or ".").resolve()
    try:
        rec = GraceCLI(repo).module_show(args.target, with_verification=args.with_verification)
    except GraceCLIMissing as e:
        print(json.dumps({"error": "GRACE_CLI_MISSING", "detail": str(e)}), file=sys.stderr)
        return 3
    print(json.dumps(rec.__dict__, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_module_find(args: argparse.Namespace) -> int:
    """`grace module find <query>` gateway — search modules by id/name/path/annotation.

    Useful for the migration `03-draft-plan` and maintenance `on-drift-detected`
    flows where agent needs to resolve "which M-* does this file belong to".
    """
    from doubled_graph.integrations.grace_cli import GraceCLI, GraceCLIMissing

    repo = Path(args.repo or ".").resolve()
    try:
        result = GraceCLI(repo)._run(["module", "find", args.query, "--path", str(repo)])
    except GraceCLIMissing as e:
        print(json.dumps({"error": "GRACE_CLI_MISSING", "detail": str(e)}), file=sys.stderr)
        return 3
    # Upstream returns free-form text; we forward as-is under a "stdout" field.
    print(json.dumps({"query": args.query, "stdout": result}, indent=2, ensure_ascii=False))
    return 0


def _cmd_file_show(args: argparse.Namespace) -> int:
    """`grace file show <path>` gateway — MODULE_CONTRACT/MAP/CHANGE_SUMMARY extractor.

    Used by `on-before-edit` and `grace-fix`-style flows to read only the
    relevant contract+blocks instead of loading whole files into the LLM
    context (important for local models with short context windows).
    """
    from doubled_graph.integrations.grace_cli import GraceCLI, GraceCLIMissing

    repo = Path(args.repo or ".").resolve()
    try:
        rec = GraceCLI(repo).file_show(args.path, contracts=args.contracts, blocks=args.blocks)
    except GraceCLIMissing as e:
        print(json.dumps({"error": "GRACE_CLI_MISSING", "detail": str(e)}), file=sys.stderr)
        return 3
    print(json.dumps(rec.__dict__, indent=2, ensure_ascii=False, default=str))
    return 0


# ---------------------------------------------------------------------------
# Skill-gateway subcommands. Each maps 1:1 to an upstream grace-marketplace
# skill. The gateway does NOT execute the skill (skills are agent-level, not
# subprocess-level) — it emits a structured directive the agent interprets as
# "trigger upstream skill X with args Y in your IDE's skill system", and logs
# the intent for audit.
#
# Why route every skill through the gateway:
#   - One namespace in all methodology prompts (`doubled-graph <verb>`).
#   - A single place to enforce phase-aware policy and log intent.
#   - Upstream skills can be renamed / reorganised without rewriting prompts.
# ---------------------------------------------------------------------------


_SKILL_GATEWAYS: dict[str, tuple[str, str]] = {
    "init": (
        "grace-init",
        "Bootstrap docs/*.xml + AGENTS.md in an empty repo. Idempotent.",
    ),
    "plan": (
        "grace-plan",
        "Build development-plan.xml + knowledge-graph.xml; draft verification. Two approval gates (architecture, verification draft).",
    ),
    "execute": (
        "grace-execute",
        "Run the plan sequentially phase by phase; approval gate on Step 1.",
    ),
    "multiagent-execute": (
        "grace-multiagent-execute",
        "Run the plan in parallel-safe waves. Profile controls approval cadence (safe/balanced/fast).",
    ),
    "verification": (
        "grace-verification",
        "Generate/update tests, attach log markers to critical paths, keep verification-plan.xml in sync.",
    ),
    "reviewer": (
        "grace-reviewer",
        "Review scope: module / wave / full repo. Checks markup, contracts, CrossLinks, verification coverage.",
    ),
    "fix": (
        "grace-fix",
        "Debug a bug or contract violation within the existing contract; record CHANGE_SUMMARY. Does NOT modify contracts — those go through plan.",
    ),
    "ask": (
        "grace-ask",
        "Answer a project question using computed + declared graphs; cites artifacts.",
    ),
    "health": (
        "grace-status",
        "Project health overview: artifact coverage, graph sync, verification coverage, open DRIFT.md entries. Read-only.",
    ),
    "refactor": (
        "grace-refactor",
        "Rename/move/split/merge/extract modules with coordinated artifact+anchor+verification updates.",
    ),
}


def _make_skill_gateway(local_name: str, upstream: str, summary: str):
    """Build a CLI handler that emits a skill-invocation directive for `upstream`.

    Why a factory: 10 nearly identical handlers would bloat the file. The per-
    skill differences are only: upstream name, extra args (if any). Factored
    out, each entry in _SKILL_GATEWAYS stays a one-liner.
    """

    def _cmd(args: argparse.Namespace) -> int:
        from doubled_graph.storage import paths as sp

        repo = Path(args.repo or ".").resolve()

        # Gather extra free-form args (each gateway may define its own).
        extra = {k: v for k, v in vars(args).items() if k not in {"func", "command", "repo"}}

        directive = {
            "delegated_to": f"upstream-skill:{upstream}",
            "summary": summary,
            "args": extra,
            "instructions": (
                f"Trigger the upstream `{upstream}` skill in your IDE's skill system. "
                "Args above are guidance; the skill itself reads docs/*.xml and AGENTS.md "
                "for full context. Report the result — commits, approval outcome, any "
                "errors — back to the user."
            ),
        }

        try:
            with sp.today_log_path(repo).open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {"event": "skill_requested", "skill": upstream, "args": extra}
                    )
                    + "\n"
                )
        except OSError:
            pass

        print(json.dumps(directive, indent=2, ensure_ascii=False))
        return 0

    _cmd.__name__ = f"_cmd_skill_{local_name.replace('-', '_')}"
    _cmd.__doc__ = f"Gateway for upstream skill `{upstream}`: {summary}"
    return _cmd


def _cmd_refresh(args: argparse.Namespace) -> int:
    """Gateway for upstream skill `grace-refresh` — declared-graph sync with code.

    Why this exists as a doubled-graph subcommand:
      `grace-refresh` is a skill (agent-invoked), not a CLI binary. But from
      the methodology's point of view, refresh is a core operation that every
      prompt invokes. Routing through our namespace (`doubled-graph refresh`)
      gives us:
        - one consistent entry point in all prompts (no mixing CLI/skill),
        - a place to log intent (`.doubled-graph/logs/`),
        - a place to enforce policy (phase-aware refresh if needed later).

      Since skills can't be triggered from subprocess, this command prints a
      structured directive instructing the agent to invoke the upstream skill.
      The agent reads the directive and performs the skill call via IDE.
    """
    from doubled_graph.storage import paths as sp

    repo = Path(args.repo or ".").resolve()

    directive = {
        "delegated_to": "upstream-skill:grace-refresh",
        "args": {
            "scope": args.scope,
            "modules": list(args.modules) if args.modules else None,
            "dry_run": bool(args.dry_run),
        },
        "instructions": (
            "Trigger the upstream `grace-refresh` skill in your IDE's skill system "
            "with the above args. If the skill is unavailable in your IDE, edit "
            "docs/*.xml manually per methodology/artifacts.md. "
            + ("With dry_run=true, the agent should run the skill in preview mode: compute "
               "the diff against docs/*.xml but do NOT write changes. Report the diff to the user."
               if args.dry_run else "Report back the diff.")
        ),
        "expected_outputs": [
            "docs/knowledge-graph.xml (updated)" if not args.dry_run else "docs/knowledge-graph.xml (proposed diff, not written)",
            "docs/development-plan.xml (updated if modules/phases changed)" if not args.dry_run else "docs/development-plan.xml (proposed diff)",
        ],
    }

    # Log intent so later detect_changes / audit can trace "who asked for this".
    try:
        with sp.today_log_path(repo).open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "refresh_requested", "args": directive["args"]}) + "\n")
    except OSError:
        pass

    print(json.dumps(directive, indent=2, ensure_ascii=False))
    return 0


def _cmd_phase(args: argparse.Namespace) -> int:
    """Read or set the repo phase (migration <-> post_migration).

    Why here and not a separate tool: phase is the root policy switch of the
    methodology — agents must read it before every drift decision. The phase
    lives as a block in AGENTS.md (not a secondary file) so it's visible at
    PR-review time; this subcommand is the single writer, avoiding hand-edits.
    """
    from doubled_graph.policy.phase import read_phase, set_phase

    repo = Path(args.repo or ".").resolve()
    if args.action == "get":
        print(read_phase(repo))
        return 0
    # `set` — atomic rewrite of AGENTS.md phase-block.
    result = set_phase(repo, args.value, reason=args.reason)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_impact(args: argparse.Namespace) -> int:
    from doubled_graph.tools.impact import impact

    repo = Path(args.repo or ".").resolve()
    result = impact(
        repo_path=repo,
        target=args.target,
        direction=args.direction,
        depth=args.depth,
        include_tests=not args.no_tests,
        scope=args.scope,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    from doubled_graph.tools.context import context

    repo = Path(args.repo or ".").resolve()
    result = context(
        repo_path=repo,
        name=args.name,
        depth_callers=args.depth_callers,
        depth_callees=args.depth_callees,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


def _cmd_detect_changes(args: argparse.Namespace) -> int:
    from doubled_graph.tools.detect_changes import detect_changes

    repo = Path(args.repo or ".").resolve()
    result = detect_changes(
        repo_path=repo,
        scope=args.scope,
        base_ref=args.base_ref,
        since_ref=args.since_ref,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    from doubled_graph.setup import run_setup

    repo = Path(args.repo or ".").resolve()
    report = run_setup(
        repo_path=repo,
        ide=args.ide,
        skip_grace_cli=args.skip_grace_cli,
        skip_hooks=args.skip_hooks,
        skip_analyze=args.skip_analyze,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 1


def main(argv_default: list[str] | None = None, argv: list[str] | None = None) -> int:
    """Entry point.

    - `argv` (explicit) overrides anything — used by tests.
    - `argv_default` is used only when no sys.argv was passed (e.g. `python -m doubled_graph`).
    """
    parser = argparse.ArgumentParser(prog="doubled-graph")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Start MCP server on stdio")
    p_serve.set_defaults(func=_cmd_serve)

    p_an = sub.add_parser("analyze", help="One-shot analyze (hooks/CI)")
    p_an.add_argument("--repo", help="Repository path (default: cwd)")
    p_an.add_argument("--mode", choices=["auto", "full", "incremental"], default="auto")
    p_an.add_argument("--since-ref", default=None)
    p_an.add_argument("--paths", nargs="*", default=None)
    p_an.add_argument("--force", action="store_true")
    p_an.add_argument("--silent", action="store_true")
    p_an.set_defaults(func=_cmd_analyze)

    p_hooks = sub.add_parser("init-hooks", help="Install hooks")
    p_hooks.add_argument("--repo")
    p_hooks.add_argument("--all", action="store_true")
    p_hooks.add_argument("--post-commit", action="store_true")
    p_hooks.add_argument("--claude-code", action="store_true")
    p_hooks.add_argument("--prepare-commit-msg", action="store_true")
    p_hooks.add_argument("--dry-run", action="store_true")
    p_hooks.set_defaults(func=_cmd_init_hooks)

    p_status = sub.add_parser("status", help="Show config + phase + freshness")
    p_status.add_argument("--repo")
    p_status.set_defaults(func=_cmd_status)

    # Gateway wrappers over `grace` CLI (upstream). Keeping these under our
    # namespace so methodology talks to a single tool.
    p_lint = sub.add_parser("lint", help="Validate anchors, block uniqueness, and UC/M/V-M references")
    p_lint.add_argument("--repo")
    p_lint.add_argument("--path", default=None, help="alias for --repo")
    p_lint.add_argument("--verbose", action="store_true")
    p_lint.set_defaults(func=_cmd_lint)

    p_mod = sub.add_parser("module", help="Module records: show / find")
    mod_sub = p_mod.add_subparsers(dest="module_cmd", required=True)
    p_mod_show = mod_sub.add_parser("show", help="Show module record (contract, exports, deps)")
    p_mod_show.add_argument("target")
    p_mod_show.add_argument("--with-verification", action="store_true")
    p_mod_show.add_argument("--repo")
    p_mod_show.set_defaults(func=_cmd_module_show)
    p_mod_find = mod_sub.add_parser("find", help="Resolve module by id/name/path/annotation")
    p_mod_find.add_argument("query")
    p_mod_find.add_argument("--repo")
    p_mod_find.set_defaults(func=_cmd_module_find)

    p_file = sub.add_parser("file", help="File-level records: show")
    file_sub = p_file.add_subparsers(dest="file_cmd", required=True)
    p_file_show = file_sub.add_parser("show", help="Extract MODULE_CONTRACT / CONTRACT:fn / BLOCK_* sections")
    p_file_show.add_argument("path")
    p_file_show.add_argument("--contracts", action="store_true")
    p_file_show.add_argument("--blocks", action="store_true")
    p_file_show.add_argument("--repo")
    p_file_show.set_defaults(func=_cmd_file_show)

    # Gateway for the upstream `grace-refresh` skill — single invocation namespace.
    p_refresh = sub.add_parser(
        "refresh",
        help="Sync docs/*.xml with code (declared ← computed). scope=targeted|full; --dry-run for preview.",
    )
    p_refresh.add_argument("--scope", choices=["targeted", "full"], default="targeted")
    p_refresh.add_argument("--modules", nargs="*", help="module ids, e.g. M-AUTH-VALIDATE")
    p_refresh.add_argument("--dry-run", action="store_true", help="preview diff, do not write")
    p_refresh.add_argument("--repo")
    p_refresh.set_defaults(func=_cmd_refresh)

    # Methodology operations whose actual work is LLM-driven (agent-side skill
    # execution). Each subcommand emits a structured directive (args + intent
    # log) that the agent interprets and executes inside the IDE.
    for local_name, (upstream, summary) in _SKILL_GATEWAYS.items():
        sp_skill = sub.add_parser(local_name, help=summary)
        sp_skill.add_argument("--repo")
        # Skill-specific args: multiagent-execute has a profile.
        if local_name == "multiagent-execute":
            sp_skill.add_argument(
                "--profile",
                choices=["safe", "balanced", "fast"],
                default="balanced",
                help="wave-level approval cadence",
            )
        sp_skill.set_defaults(func=_make_skill_gateway(local_name, upstream, summary))

    # Phase policy — single writer/reader of AGENTS.md phase-block.
    p_phase = sub.add_parser("phase", help="Read or set phase (migration | post_migration)")
    phase_sub = p_phase.add_subparsers(dest="action", required=True)
    p_phase_get = phase_sub.add_parser("get", help="Print current phase")
    p_phase_get.add_argument("--repo")
    p_phase_get.set_defaults(func=_cmd_phase)
    p_phase_set = phase_sub.add_parser("set", help="Set phase (atomic rewrite of AGENTS.md phase-block)")
    p_phase_set.add_argument("value", choices=["migration", "post_migration"])
    p_phase_set.add_argument("--reason", default="")
    p_phase_set.add_argument("--repo")
    p_phase_set.set_defaults(func=_cmd_phase)

    # Native graph tools — no longer stubs.
    p_impact = sub.add_parser("impact", help="Blast-radius analysis for a symbol")
    p_impact.add_argument("target")
    p_impact.add_argument(
        "--direction", choices=["upstream", "downstream", "both"], default="upstream"
    )
    p_impact.add_argument("--depth", type=int, default=3)
    p_impact.add_argument("--no-tests", action="store_true", help="exclude test files from dependents")
    p_impact.add_argument("--scope", choices=["full", "module", "file"], default="full")
    p_impact.add_argument("--repo")
    p_impact.set_defaults(func=_cmd_impact)

    p_ctx = sub.add_parser("context", help="360° view on a symbol (computed+declared+source)")
    p_ctx.add_argument("name")
    p_ctx.add_argument("--depth-callers", type=int, default=2, dest="depth_callers")
    p_ctx.add_argument("--depth-callees", type=int, default=2, dest="depth_callees")
    p_ctx.add_argument("--repo")
    p_ctx.set_defaults(func=_cmd_context)

    p_dc = sub.add_parser("detect-changes", help="Drift between computed and declared graphs")
    p_dc.add_argument(
        "--scope", choices=["staged", "branch", "all", "compare"], default="staged"
    )
    p_dc.add_argument("--base-ref", default="main", dest="base_ref")
    p_dc.add_argument("--since-ref", default="HEAD~1", dest="since_ref")
    p_dc.add_argument("--repo")
    p_dc.set_defaults(func=_cmd_detect_changes)

    # Onboarding — single-shot bootstrap for new users.
    p_setup = sub.add_parser(
        "setup",
        help="Onboard: install grace CLI, copy prompts, register MCP, install hooks, first analyze",
    )
    p_setup.add_argument("--repo", help="target repository (default: cwd)")
    p_setup.add_argument(
        "--ide",
        choices=["auto", "claude-code", "cursor", "continue", "none"],
        default="auto",
        help="which IDE's MCP config to write (auto-detected by default)",
    )
    p_setup.add_argument("--skip-grace-cli", action="store_true", help="don't try to `bun add -g`")
    p_setup.add_argument("--skip-hooks", action="store_true", help="don't install git post-commit hook")
    p_setup.add_argument("--skip-analyze", action="store_true", help="don't run first full analyze")
    p_setup.add_argument("--dry-run", action="store_true", help="plan only; no fs/network changes")
    p_setup.set_defaults(func=_cmd_setup)

    if argv is not None:
        effective = argv
    elif argv_default is not None and len(sys.argv) == 1:
        effective = argv_default
    else:
        effective = None  # let argparse read sys.argv[1:]
    args = parser.parse_args(effective)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
