"""Smoke tests — exercise module imports, phase parsing, declared-graph parsing,
analyze stub path, hook-installer dry-run. No CGC/grace-cli required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_package_imports():
    import doubled_graph

    assert doubled_graph.__version__


def test_phase_default_when_no_agents_md(tmp_path: Path):
    from doubled_graph.policy.phase import read_phase

    assert read_phase(tmp_path) == "post_migration"


def test_phase_migration_parsed(tmp_path: Path):
    from doubled_graph.policy.phase import read_phase

    (tmp_path / "AGENTS.md").write_text(
        """
# Project

<!-- doubled-graph:phase:start -->
## doubled-graph phase
phase: migration
updated: 2026-04-18
<!-- doubled-graph:phase:end -->
""",
        encoding="utf-8",
    )
    assert read_phase(tmp_path) == "migration"


def test_phase_invalid_value_falls_back_to_default(tmp_path: Path):
    from doubled_graph.policy.phase import read_phase

    (tmp_path / "AGENTS.md").write_text(
        """
<!-- doubled-graph:phase:start -->
phase: gibberish
<!-- doubled-graph:phase:end -->
""",
        encoding="utf-8",
    )
    assert read_phase(tmp_path) == "post_migration"


def test_declared_graph_empty_when_no_docs(tmp_path: Path):
    from doubled_graph.graphs.declared import load_declared_graph

    g = load_declared_graph(tmp_path)
    assert g.modules == {}
    assert g.verification == {}
    assert g.loaded_from == []


def test_declared_graph_tolerates_malformed_xml(tmp_path: Path):
    from doubled_graph.graphs.declared import load_declared_graph

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "development-plan.xml").write_text("<Plan><Module id='", encoding="utf-8")
    g = load_declared_graph(tmp_path)
    assert any(item.startswith("!") for item in g.loaded_from)


def test_analyze_runs_without_cgc(tmp_path: Path, monkeypatch):
    """analyze() must return a structured result even when CGC import fails."""
    from doubled_graph.tools import analyze as analyze_mod
    from doubled_graph.integrations.cgc import CGCUnavailable

    class _FakeCGC:
        def __init__(self, *_args, **_kw):
            pass

        def analyze_full(self):
            raise CGCUnavailable("simulated missing CGC for smoke test")

        def analyze_incremental(self, _files):
            raise CGCUnavailable("simulated missing CGC for smoke test")

    monkeypatch.setattr(analyze_mod, "CGC", _FakeCGC)

    result = analyze_mod.analyze(repo_path=tmp_path, mode="full")
    assert result.mode_used == "full"
    assert any(w.code == "CGC_BACKEND_FAIL" for w in result.warnings)
    # Log event written.
    logs = list((tmp_path / ".doubled-graph" / "logs").iterdir())
    assert logs, "analyze should write a log event"


def test_analyze_writes_fingerprint_on_success(tmp_path: Path, monkeypatch):
    """Successful analyze must persist the fingerprint so next auto-mode picks
    incremental. Regression guard for task 3 in TODO_DEV.
    """
    from doubled_graph.integrations.cgc import AnalyzeStats
    from doubled_graph.storage import paths as sp
    from doubled_graph.tools import analyze as analyze_mod

    class _OKCGC:
        def __init__(self, *_args, **_kw):
            pass

        def analyze_full(self):
            return AnalyzeStats(files_processed=3, symbols_added=7)

        def analyze_incremental(self, _files):
            return AnalyzeStats(files_processed=1)

    monkeypatch.setattr(analyze_mod, "CGC", _OKCGC)

    res = analyze_mod.analyze(repo_path=tmp_path, mode="full")
    assert res.stats.files_processed == 3
    assert res.stats.symbols_added == 7
    assert sp.fingerprint_path(tmp_path).exists()


def test_impact_shape_without_cgc(tmp_path: Path, monkeypatch):
    """impact() must return a structurally valid result even when CGC errors."""
    from doubled_graph.integrations import cgc as cgc_mod
    from doubled_graph.tools import impact as impact_mod

    class _FailCGC:
        def __init__(self, *_a, **_k):
            pass

        def find_symbol(self, _n):
            raise cgc_mod.CGCUnavailable("simulated")

        def find_callers(self, _t, depth=3):
            raise cgc_mod.CGCUnavailable("simulated")

        def find_callees(self, _t, depth=3):
            raise cgc_mod.CGCUnavailable("simulated")

    monkeypatch.setattr(impact_mod, "CGC", _FailCGC)
    res = impact_mod.impact(repo_path=tmp_path, target="foo")
    assert res.target_resolved.name == "foo"
    assert res.risk.level in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "NONE")
    assert any(w.code == "CGC_BACKEND_FAIL" for w in res.warnings)


def test_impact_classifies_by_caller_count(tmp_path: Path, monkeypatch):
    """risk.level must escalate with direct-caller count. Guard for task 4."""
    from doubled_graph.integrations.cgc import Callsite, SymbolRecord
    from doubled_graph.tools import impact as impact_mod

    class _ManyCallersCGC:
        def __init__(self, *_a, **_k):
            pass

        def find_symbol(self, name):
            return [SymbolRecord(name=name, file="src/x.py", line=10)]

        def find_callers(self, _t, depth=3):
            return [
                Callsite(name=f"c{i}", file=f"src/c{i}.py", line=i, depth=1)
                for i in range(5)
            ]

        def find_callees(self, _t, depth=3):
            return []

    monkeypatch.setattr(impact_mod, "CGC", _ManyCallersCGC)
    res = impact_mod.impact(repo_path=tmp_path, target="foo")
    assert len(res.direct) == 5
    # 5 direct callers → HIGH band per _classify_risk
    assert res.risk.level == "HIGH"


def test_context_returns_contract_and_module(tmp_path: Path, monkeypatch):
    """context() must join CGC symbol, declared module, and source contract."""
    from doubled_graph.integrations.cgc import SymbolRecord, Callsite
    from doubled_graph.tools import context as ctx_mod

    # Declared graph: one module that owns src/
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "development-plan.xml").write_text(
        "<Plan><Module id='M-FOO'><purpose>Foo logic</purpose><path>src</path></Module></Plan>",
        encoding="utf-8",
    )
    (docs / "knowledge-graph.xml").write_text(
        "<Graph><Module id='M-FOO'><Export name='bar'/><CrossLink to='M-OTHER'/></Module></Graph>",
        encoding="utf-8",
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "# MODULE_CONTRACT\n# purpose: demo\n# links: M-OTHER\n# END_MODULE_CONTRACT\n\ndef bar():\n    pass\n",
        encoding="utf-8",
    )

    class _CGC:
        def __init__(self, *_a, **_k):
            pass

        def find_symbol(self, name):
            return [SymbolRecord(name=name, file=str(src / "a.py"), line=6, kind="function")]

        def find_callers(self, _t, depth=2):
            return [Callsite(name="caller", file=str(src / "b.py"), line=3, depth=1)]

        def find_callees(self, _t, depth=2):
            return []

    monkeypatch.setattr(ctx_mod, "CGC", _CGC)
    res = ctx_mod.context(repo_path=tmp_path, name="bar")
    assert res.symbol.file == "src/a.py"
    assert res.module.id == "M-FOO"
    assert res.module.purpose == "Foo logic"
    assert "MODULE_CONTRACT" in res.contract.text
    assert "M-OTHER" in res.contract.links
    assert any(c.name == "caller" for c in res.callers)


def test_detect_changes_finds_drift(tmp_path: Path, monkeypatch):
    """detect_changes must surface code_without_module, markup_missing,
    module_without_code, missing_verification.
    """
    from doubled_graph.tools import detect_changes as dc_mod

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "development-plan.xml").write_text(
        "<Plan>"
        "<Module id='M-ALIVE'><path>src/alive</path></Module>"
        "<Module id='M-ORPHAN'><path>src/gone</path></Module>"
        "</Plan>",
        encoding="utf-8",
    )
    src = tmp_path / "src" / "alive"
    src.mkdir(parents=True)
    (src / "x.py").write_text("def a(): pass\n", encoding="utf-8")
    new_area = tmp_path / "src" / "uncovered"
    new_area.mkdir()
    (new_area / "y.py").write_text("def b(): pass\n", encoding="utf-8")

    # Make files_for_scope return the two files (bypass git).
    monkeypatch.setattr(
        dc_mod,
        "_files_for_scope",
        lambda _r, _s, _b, _sr: ["src/alive/x.py", "src/uncovered/y.py"],
    )

    # Stub CGC so symbols_in_file returns something useful for the uncovered file.
    from doubled_graph.integrations.cgc import SymbolsInFile, SymbolRecord

    class _CGC:
        def __init__(self, *_a, **_k):
            pass

        def symbols_in_file(self, path):
            return SymbolsInFile(
                path=path,
                functions=[SymbolRecord(name="b", file=path, line=1)],
            )

    monkeypatch.setattr(dc_mod, "CGC", _CGC)

    res = dc_mod.detect_changes(repo_path=tmp_path, scope="all")
    assert any(c.file == "src/uncovered/y.py" for c in res.drift.code_without_module)
    assert any(
        c.file == "src/uncovered/y.py" and "b" in c.functions
        for c in res.drift.code_without_module
    )
    assert any(m.module_id == "M-ORPHAN" for m in res.drift.module_without_code)
    assert any(mv.module_id == "M-ALIVE" for mv in res.drift.missing_verification)
    assert any(mm.file in ("src/alive/x.py", "src/uncovered/y.py") for mm in res.drift.markup_missing)


def test_cli_impact_invokes_tool(tmp_path: Path, capsys, monkeypatch):
    """`doubled-graph impact <target>` must dispatch into tools/impact."""
    from doubled_graph import cli
    from doubled_graph.tools import impact as impact_mod

    class _CGC:
        def __init__(self, *_a, **_k):
            pass

        def find_symbol(self, _n):
            return []

        def find_callers(self, _t, depth=3):
            return []

        def find_callees(self, _t, depth=3):
            return []

    monkeypatch.setattr(impact_mod, "CGC", _CGC)
    rc = cli.main(argv=["impact", "foo", "--repo", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["target_resolved"]["name"] == "foo"
    assert payload["risk"]["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "NONE")


def test_cli_detect_changes_runs(tmp_path: Path, capsys, monkeypatch):
    from doubled_graph import cli
    from doubled_graph.tools import detect_changes as dc_mod

    monkeypatch.setattr(dc_mod, "_files_for_scope", lambda *_a: [])
    rc = cli.main(argv=["detect-changes", "--scope", "all", "--repo", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["scope_used"] == "all"


def test_setup_dry_run_produces_plan(tmp_path: Path):
    """`doubled-graph setup --dry-run` must not touch fs/network but must
    return a structured plan including each stage. Regression guard for task 1.
    """
    from doubled_graph.setup import run_setup

    (tmp_path / ".git").mkdir()
    report = run_setup(repo_path=tmp_path, ide="claude-code", dry_run=True)
    assert report["dry_run"] is True
    assert report["mcp_register"]["status"] == "dry_run"
    assert report["analyze"]["status"] == "dry_run"
    # No .mcp.json should have been created.
    assert not (tmp_path / ".mcp.json").exists()


def test_setup_registers_claude_code_mcp(tmp_path: Path, monkeypatch):
    """Setup must add doubled-graph entry to .mcp.json without clobbering it."""
    from doubled_graph.setup import run_setup

    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"existing": {"command": "x"}}}),
        encoding="utf-8",
    )
    # Avoid running real analyze / bun add.
    from doubled_graph import setup as setup_mod

    monkeypatch.setattr(setup_mod, "_install_grace_cli", lambda _dry: {"status": "skipped"})
    monkeypatch.setattr(setup_mod, "_first_analyze", lambda _r, _d: {"status": "skipped"})

    report = run_setup(repo_path=tmp_path, ide="claude-code")
    assert report["ok"] is True
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert "existing" in data["mcpServers"]  # preserved
    assert data["mcpServers"]["doubled-graph"]["command"] == "doubled-graph"
    assert data["mcpServers"]["doubled-graph"]["args"] == ["serve"]


def test_hooks_installer_dry_run(tmp_path: Path):
    from doubled_graph.hooks_installer import install_hooks

    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    report = install_hooks(repo_path=tmp_path, post_commit=True, dry_run=True)
    assert report["post_commit"] == "dry-run"


def test_hooks_installer_actually_installs_post_commit(tmp_path: Path):
    from doubled_graph.hooks_installer import install_hooks

    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    report = install_hooks(repo_path=tmp_path, post_commit=True)
    assert report["post_commit"] == "installed"
    hook = tmp_path / ".git" / "hooks" / "post-commit"
    assert hook.exists()
    assert "doubled-graph analyze" in hook.read_text()
    # executable bit set
    assert hook.stat().st_mode & 0o111


def test_claude_code_hook_json_merge(tmp_path: Path):
    from doubled_graph.hooks_installer import install_hooks

    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"theme": "dark", "hooks": {"PreToolUse": []}}), encoding="utf-8"
    )
    install_hooks(repo_path=tmp_path, claude_code=True)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "PreToolUse" in data["hooks"]  # existing preserved
    assert data["theme"] == "dark"
    assert data["hooks"]["PostToolUse"]
    assert "doubled-graph" in data["hooks"]["PostToolUse"][0]["hooks"][0]["command"]


def test_cli_status_runs(tmp_path: Path, capsys, monkeypatch):
    from doubled_graph import cli

    monkeypatch.chdir(tmp_path)
    rc = cli.main(argv=["status", "--repo", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "config" in payload
    assert payload["phase"] in ("migration", "post_migration")


def test_cli_skill_gateways_emit_directive(tmp_path: Path, capsys):
    """Every skill-gateway (`init`, `plan`, `execute`, …) must:
      - emit a JSON directive with delegated_to=upstream-skill:<grace-X>,
      - log the intent to `.doubled-graph/logs/` so audit can trace who asked.
    This keeps the methodology in a single doubled-graph namespace even for
    agent-level skill invocations.
    """
    from doubled_graph import cli

    cases = [
        ("init", "grace-init"),
        ("plan", "grace-plan"),
        ("execute", "grace-execute"),
        ("verification", "grace-verification"),
        ("reviewer", "grace-reviewer"),
        ("fix", "grace-fix"),
        ("ask", "grace-ask"),
        ("health", "grace-status"),
        ("refactor", "grace-refactor"),
    ]
    for local, upstream in cases:
        rc = cli.main(argv=[local, "--repo", str(tmp_path)])
        assert rc == 0, f"{local} should succeed"
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["delegated_to"] == f"upstream-skill:{upstream}"

    # multiagent-execute with profile arg.
    rc = cli.main(argv=["multiagent-execute", "--profile", "safe", "--repo", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["delegated_to"] == "upstream-skill:grace-multiagent-execute"
    assert payload["args"]["profile"] == "safe"

    # All intents must be in the log.
    logs_dir = tmp_path / ".doubled-graph" / "logs"
    assert logs_dir.exists()
    combined = "".join(p.read_text(encoding="utf-8") for p in logs_dir.iterdir())
    for _, upstream in cases:
        assert f'"skill": "{upstream}"' in combined, f"{upstream} intent should be logged"


def test_cli_refresh_returns_directive(tmp_path: Path, capsys):
    """`doubled-graph refresh` is a gateway — it must emit a structured directive
    instructing the agent to invoke the upstream grace-refresh skill, and log
    the intent. It must not try to run grace-refresh as a CLI (there is none).
    """
    from doubled_graph import cli

    rc = cli.main(argv=["refresh", "--scope", "targeted", "--modules", "M-AUTH", "--repo", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["delegated_to"] == "upstream-skill:grace-refresh"
    assert payload["args"]["scope"] == "targeted"
    assert payload["args"]["modules"] == ["M-AUTH"]
    # Intent must be logged to the day's jsonl.
    logs_dir = tmp_path / ".doubled-graph" / "logs"
    assert logs_dir.exists()
    found = False
    for p in logs_dir.iterdir():
        text = p.read_text(encoding="utf-8")
        if "refresh_requested" in text and "M-AUTH" in text:
            found = True
            break
    assert found, "refresh intent should be logged"


def test_phase_set_creates_agents_md_if_absent(tmp_path: Path):
    """`doubled-graph phase set` on an empty repo must create AGENTS.md with
    the phase-block — otherwise the first migration setup breaks.
    """
    from doubled_graph.policy.phase import read_phase, set_phase

    result = set_phase(tmp_path, "migration", reason="starting migration")
    assert result["current"] == "migration"
    assert result["created_file"] is True
    assert result["appended_block"] is True
    assert read_phase(tmp_path) == "migration"


def test_phase_set_patches_existing_block(tmp_path: Path):
    """Switching phase on a repo with existing AGENTS.md must preserve
    surrounding content byte-for-byte and update only the block.
    """
    from doubled_graph.policy.phase import read_phase, set_phase

    original = (
        "# Project\n\n"
        "Some intro paragraph.\n\n"
        "<!-- doubled-graph:phase:start -->\n"
        "## doubled-graph phase\n"
        "phase: migration\n"
        "updated: 2026-04-18\n"
        "<!-- doubled-graph:phase:end -->\n\n"
        "## Other section\nContent.\n"
    )
    (tmp_path / "AGENTS.md").write_text(original, encoding="utf-8")

    result = set_phase(tmp_path, "post_migration", reason="migration complete")
    assert result["previous"] == "migration"
    assert result["current"] == "post_migration"
    assert result["created_file"] is False
    assert result["appended_block"] is False

    new = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Project" in new and "## Other section" in new  # preserved
    assert read_phase(tmp_path) == "post_migration"


def test_cli_phase_set(tmp_path: Path, capsys):
    from doubled_graph import cli

    rc = cli.main(
        argv=["phase", "set", "post_migration", "--reason", "test", "--repo", str(tmp_path)]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["current"] == "post_migration"


def test_cli_lint_accepts_path_and_verbose(tmp_path: Path, capsys, monkeypatch):
    """`doubled-graph lint --path . --verbose` must work as-typed in docs —
    `--path` is an alias for `--repo`, `--verbose` forwards to upstream.
    """
    from doubled_graph import cli
    from doubled_graph.integrations import grace_cli as gc_mod

    called = {}

    def fake_lint(self, verbose=False):
        called["verbose"] = verbose
        called["repo"] = str(self.repo_path)
        return {"ok": True}

    monkeypatch.setattr(gc_mod.GraceCLI, "lint", fake_lint)
    monkeypatch.setattr(gc_mod.shutil, "which", lambda _c: "/fake/grace")

    rc = cli.main(argv=["lint", "--path", str(tmp_path), "--verbose"])
    assert rc == 0
    assert called["verbose"] is True
    assert called["repo"] == str(tmp_path.resolve())


def test_cli_refresh_dry_run_in_directive(tmp_path: Path, capsys):
    from doubled_graph import cli

    rc = cli.main(argv=["refresh", "--scope", "full", "--dry-run", "--repo", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["args"]["dry_run"] is True
    assert "preview mode" in payload["instructions"].lower() or "dry_run=true" in payload["instructions"]


def test_cli_phase_get(tmp_path: Path, capsys):
    """`doubled-graph phase get` must print current phase — default post_migration
    when no AGENTS.md block exists. Agents rely on this for drift decisions.
    """
    from doubled_graph import cli

    rc = cli.main(argv=["phase", "get", "--repo", str(tmp_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "post_migration"


def test_cli_lint_gateway_surfaces_missing_grace(tmp_path: Path, capsys, monkeypatch):
    """`doubled-graph lint` must fail cleanly (GRACE_CLI_MISSING) when grace is
    not on PATH — the user gets a useful install hint instead of a traceback.
    """
    from doubled_graph import cli

    # Force "not on PATH" by replacing shutil.which in the integration module.
    from doubled_graph.integrations import grace_cli as gc_mod

    monkeypatch.setattr(gc_mod.shutil, "which", lambda _cmd: None)
    rc = cli.main(argv=["lint", "--repo", str(tmp_path)])
    assert rc == 3
    err = capsys.readouterr().err
    payload = json.loads(err)
    assert payload["error"] == "GRACE_CLI_MISSING"
