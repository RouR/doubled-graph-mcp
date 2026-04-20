"""MCP server — registers the four tools and serves them over stdio.

Notes on MCP-SDK usage:

The `mcp` Python package (Anthropic) provides a low-level stdio server.
This file targets the public API shape as of the 0.9.x line (April 2026).
If the SDK API surface drifts, the wiring is localized here — tools/* stay
unchanged.

If `mcp` is not installed, `run_stdio` raises a clear error. That's
intentional: without a transport, there's no useful MCP server to start.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from doubled_graph.tools.analyze import analyze as tool_analyze
from doubled_graph.tools.context import context as tool_context
from doubled_graph.tools.detect_changes import detect_changes as tool_detect_changes
from doubled_graph.tools.impact import impact as tool_impact


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # -------- Doubled-graph native tools (act on computed × declared graphs) --------
    {
        "name": "analyze",
        "description": "Build or incrementally update the computed code graph (CGC). Returns stats and warnings. See TOOLS.md §1.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["auto", "full", "incremental"], "default": "auto"},
                "since_ref": {"type": ["string", "null"], "default": None},
                "paths": {"type": ["array", "null"], "items": {"type": "string"}, "default": None},
                "force": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "impact",
        "description": "Blast-radius analysis for a symbol. MUST be called before editing. See TOOLS.md §2.",
        "inputSchema": {
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string"},
                "direction": {"type": "string", "enum": ["upstream", "downstream", "both"], "default": "upstream"},
                "depth": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                "include_tests": {"type": "boolean", "default": True},
                "scope": {"type": "string", "enum": ["full", "module", "file"], "default": "full"},
            },
        },
    },
    {
        "name": "context",
        "description": "360° view on a symbol (computed+declared+source). See TOOLS.md §3.",
        "inputSchema": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "depth_callers": {"type": "integer", "default": 2, "minimum": 0, "maximum": 5},
                "depth_callees": {"type": "integer", "default": 2, "minimum": 0, "maximum": 5},
            },
        },
    },
    {
        "name": "detect_changes",
        "description": "Detect drift between computed (CGC) and declared (docs/*.xml) graphs. See TOOLS.md §4.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["staged", "branch", "all", "compare"], "default": "staged"},
                "base_ref": {"type": "string", "default": "main"},
                "since_ref": {"type": "string", "default": "HEAD~1"},
                "include_unchanged": {"type": "boolean", "default": False},
            },
        },
    },
    # Artifact validation and navigation — thin wrappers over underlying tooling.
    {
        "name": "lint",
        "description": "Validate doubled-graph artifacts: anchor pairing, block uniqueness within file, reference integrity UC-* → M-* → V-M-*.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "module_show",
        "description": "Return a module record: contract (pre/post/invariants), public exports, dependencies; optionally its V-M-* verification entries.",
        "inputSchema": {
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string"},
                "with_verification": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "module_find",
        "description": "Resolve a module by id, name, path substring or annotation. Returns the matching M-* record(s).",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
        },
    },
    {
        "name": "file_show",
        "description": "Extract MODULE_CONTRACT / CONTRACT:fn / BLOCK_* / CHANGE_SUMMARY sections from a file — the anchor-framed slice, not the whole file. Use this instead of reading the full file when only the contract/blocks are needed.",
        "inputSchema": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "contracts": {"type": "boolean", "default": True},
                "blocks": {"type": "boolean", "default": True},
            },
        },
    },
    # Methodology operations that need agent-side skill execution. These return
    # a structured directive (args + instructions for the agent) rather than
    # doing the work in-process — the underlying work is LLM-driven.
    {
        "name": "refresh",
        "description": "Synchronize docs/*.xml with the current code (declared graph ← computed graph). scope=targeted updates named modules; scope=full recomputes the whole declared graph. dry_run=true computes diff without writing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["targeted", "full"], "default": "targeted"},
                "modules": {"type": ["array", "null"], "items": {"type": "string"}, "default": None},
                "dry_run": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "init",
        "description": "Bootstrap the methodology in an empty repo: create docs/*.xml (requirements, technology, development-plan, knowledge-graph, verification-plan, operational-packets) and AGENTS.md with the phase-block. Idempotent — skips files that already exist.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "plan",
        "description": "Build or extend development-plan.xml + knowledge-graph.xml, drafting verification entries. Runs two approval gates: module architecture, then verification draft — halts between them for user sign-off.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "execute",
        "description": "Run the plan sequentially, phase by phase, generating code with anchors and tests. Halts at the execution-plan approval gate before starting, and shows diffs after each phase.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "multiagent_execute",
        "description": "Run the plan in parallel-safe waves. profile=safe gets approval per wave + full review per module; balanced gets one up-front approval + scoped reviews; fast skips mid-run approvals, auditing only at phase end.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "enum": ["safe", "balanced", "fast"], "default": "balanced"}
            },
        },
    },
    {
        "name": "verification",
        "description": "Generate/update tests for modules, attach log-anchored markers to critical code paths, and keep verification-plan.xml aligned with actual test files.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "reviewer",
        "description": "Review scope: one module, one wave, or full-repo integrity. Checks anchor markup, contract/signature agreement, CrossLink accuracy, verification coverage.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "fix",
        "description": "Debug a reported bug or contract violation: navigate computed+declared graphs to locate the cause, apply a fix within the existing contract, record a CHANGE_SUMMARY entry. Does NOT modify contracts — those go through plan.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ask",
        "description": "Answer a natural-language question about the project by querying computed and declared graphs. Responses cite the artifacts (M-*, V-M-*, CrossLinks) they used.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "health",
        "description": "Project health overview: artifact coverage by criticality, graph-sync state, verification coverage, open DRIFT.md entries. Read-only.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "refactor",
        "description": "Rename / move / split / merge / extract module(s) with coordinated updates to artifacts, anchors, and verification. Preserves cross-reference integrity; no silent drift introduced.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _dispatch(tool_name: str, args: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    """Route an MCP tool call to the right implementation.

    Why this function exists: MCP server.py is transport-only — all business
    logic lives in tools/* and integrations/*. Dispatch keeps that separation
    explicit and makes it trivial to add new gateway wrappers.
    """
    if tool_name == "analyze":
        return tool_analyze(repo_path=repo_path, **args).model_dump(mode="json")
    if tool_name == "impact":
        return tool_impact(repo_path=repo_path, **args).model_dump(mode="json")
    if tool_name == "context":
        return tool_context(
            repo_path=repo_path,
            name=args.get("name", ""),
            depth_callers=int(args.get("depth_callers", 2)),
            depth_callees=int(args.get("depth_callees", 2)),
        ).model_dump(mode="json")
    if tool_name == "detect_changes":
        return tool_detect_changes(
            repo_path=repo_path,
            scope=args.get("scope", "staged"),
            base_ref=args.get("base_ref", "main"),
            since_ref=args.get("since_ref", "HEAD~1"),
            include_unchanged=bool(args.get("include_unchanged", False)),
        ).model_dump(mode="json")

    # Gateway wrappers — lazy-import grace_cli so the MCP server doesn't fail
    # to start just because grace CLI isn't on PATH yet.
    if tool_name in ("lint", "module_show", "module_find", "file_show"):
        from doubled_graph.integrations.grace_cli import GraceCLI, GraceCLIMissing

        try:
            cli = GraceCLI(repo_path)
            if tool_name == "lint":
                return {"result": cli.lint()}
            if tool_name == "module_show":
                rec = cli.module_show(args["target"], with_verification=bool(args.get("with_verification")))
                return {"result": rec.__dict__}
            if tool_name == "module_find":
                out = cli._run(["module", "find", args["query"], "--path", str(repo_path)])  # noqa: SLF001
                return {"result": {"query": args["query"], "stdout": out}}
            if tool_name == "file_show":
                rec = cli.file_show(
                    args["path"],
                    contracts=bool(args.get("contracts", True)),
                    blocks=bool(args.get("blocks", True)),
                )
                return {"result": rec.__dict__}
        except GraceCLIMissing as e:
            return {"error": "GRACE_CLI_MISSING", "detail": str(e)}
        except Exception as e:  # noqa: BLE001 — surface as structured error
            return {"error": "GRACE_CLI_ERROR", "detail": str(e)}

    # Skill-gateway tools — emit a directive, no execution (skills are agent-level).
    # Kept in a single place so the upstream-skill mapping is one dictionary.
    skill_map = {
        "refresh": "grace-refresh",
        "init": "grace-init",
        "plan": "grace-plan",
        "execute": "grace-execute",
        "multiagent_execute": "grace-multiagent-execute",
        "verification": "grace-verification",
        "reviewer": "grace-reviewer",
        "fix": "grace-fix",
        "ask": "grace-ask",
        "health": "grace-status",
        "refactor": "grace-refactor",
    }
    if tool_name in skill_map:
        from doubled_graph.storage import paths as sp

        upstream = skill_map[tool_name]
        try:
            with sp.today_log_path(repo_path).open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps({"event": "skill_requested", "skill": upstream, "args": args}) + "\n"
                )
        except OSError:
            pass
        return {
            "delegated_to": f"upstream-skill:{upstream}",
            "args": args,
            "instructions": (
                f"Trigger the upstream `{upstream}` skill in your IDE's skill system. "
                "Skills are agent-level, not CLI — this MCP tool only logs the intent "
                "and returns this directive; the actual skill invocation happens in "
                "your IDE. Report back the result."
            ),
        }

    return {"error": "UNKNOWN_TOOL", "tool": tool_name}


def run_stdio(repo_path: Path | None = None) -> None:
    """Start the MCP server. Blocks until stdin closes."""
    repo = (repo_path or Path.cwd()).resolve()

    try:
        # Lazy import — keeps unit tests runnable without the full MCP SDK.
        from mcp.server import Server  # type: ignore
        from mcp.server.stdio import stdio_server  # type: ignore
        from mcp.types import Tool, TextContent  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "mcp package not available. Install via `pip install mcp` (>=0.9)."
        ) from e

    server = Server("doubled-graph")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Tool]:
        return [
            Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        result = _dispatch(name, arguments or {}, repo)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    import anyio

    async def _main() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(_main)
