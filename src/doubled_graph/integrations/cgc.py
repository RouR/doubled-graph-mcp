"""CodeGraphContext integration (thin wrapper).

All CGC-specific imports are lazy — the package is declared as a dependency
but we still degrade gracefully if it's not importable at runtime (e.g., during
module-level scaffolding tests, or if the user installed a broken version).

Real behavior is concentrated in this file so `tools/*.py` never imports CGC
directly. Public methods return plain dataclasses / primitives — no CGC types
leak out. If upstream CGC changes a signature, the change stays localized here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


class CGCUnavailable(RuntimeError):
    """Raised when codegraphcontext cannot be imported or initialized."""


@dataclass
class AnalyzeStats:
    files_processed: int = 0
    symbols_added: int = 0
    symbols_removed: int = 0
    symbols_updated: int = 0
    edges_added: int = 0
    edges_removed: int = 0


@dataclass
class Callsite:
    name: str
    file: str
    line: int
    kind: str = "function"  # "function" | "class" | "method"
    depth: int = 1


@dataclass
class SymbolRecord:
    name: str
    file: str
    line: int
    kind: str = "function"
    source: str = ""
    docstring: str = ""


@dataclass
class SymbolsInFile:
    """Lightweight projection of what CGC knows about a file — used by
    `detect_changes` to diff against the declared graph.
    """

    path: str
    functions: list[SymbolRecord] = field(default_factory=list)
    classes: list[SymbolRecord] = field(default_factory=list)


class CGC:
    """Lazy facade over CodeGraphContext.

    Public surface (stable):
      - analyze_full() / analyze_incremental()
      - find_callers() / find_callees()
      - find_symbol() — resolve a name to candidate records
      - symbols_in_file() — list of symbols defined in a file
      - cypher() — raw escape hatch

    Everything CGC-specific (DB backend fallbacks, query shapes) is confined
    to this class. If upstream API shifts, we adapt here and the four MCP
    tools keep working unchanged.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._db = None
        self._builder = None
        self._finder = None

    def _ensure(self) -> None:
        """Initialize CGC lazily.

        Why lazy: CGC imports pull in graph DB drivers (FalkorDB Lite / KuzuDB /
        Neo4j) and tree-sitter language grammars. Paying that cost on every CLI
        startup is wasteful — most subcommands (`phase get`, `lint`, skill
        gateways) never touch CGC.
        """
        if self._builder is not None:
            return
        try:
            from codegraphcontext.core import get_database_manager  # type: ignore
            from codegraphcontext.tools.code_finder import CodeFinder  # type: ignore
            from codegraphcontext.tools.graph_builder import GraphBuilder  # type: ignore
        except Exception as e:  # pragma: no cover — environment-dependent
            raise CGCUnavailable(
                f"codegraphcontext is not importable: {e}. "
                "Install via `pip install codegraphcontext` and verify backend availability."
            ) from e
        try:
            self._db = get_database_manager()
        except Exception as e:  # pragma: no cover — backend-dependent
            raise CGCUnavailable(
                f"CGC backend failed to initialise: {e}. "
                "Check FalkorDB Lite / KuzuDB install or NEO4J_* env vars."
            ) from e
        self._builder = GraphBuilder(self._db)
        self._finder = CodeFinder(self._db)

    # ------------------------------------------------------------------
    # analyze
    # ------------------------------------------------------------------

    def analyze_full(self) -> AnalyzeStats:
        """Index the whole repository into CGC's computed graph.

        CGC's add_repository_to_graph does not return stats, so we approximate
        by counting files encountered on disk. Real symbol counts can be fetched
        later via `cypher` if needed.
        """
        self._ensure()
        assert self._builder is not None
        self._builder.add_repository_to_graph(self.repo_path, is_dependency=False)
        files = _count_source_files(self.repo_path)
        return AnalyzeStats(files_processed=files)

    def analyze_incremental(self, changed_files: Iterable[Path]) -> AnalyzeStats:
        """Update computed graph only for the given files.

        Strategy: for each file, delete its subgraph and reparse it. After
        reparsing, re-link calls/inheritance across the collected file-data.
        CGC's GraphBuilder exposes these steps individually — we just wire
        them.
        """
        self._ensure()
        assert self._builder is not None
        stats = AnalyzeStats()
        all_file_data: list[dict] = []
        imports_map: dict = {}
        for raw in changed_files:
            p = Path(raw)
            abs_p = p if p.is_absolute() else (self.repo_path / p)
            try:
                self._builder.delete_file_from_graph(str(abs_p))
                stats.symbols_removed += 1
            except Exception:  # noqa: BLE001
                pass
            try:
                data = self._builder.parse_file(self.repo_path, abs_p, is_dependency=False)
                if isinstance(data, dict) and not data.get("error") and not data.get("unsupported"):
                    all_file_data.append(data)
                    imp = data.get("imports")
                    if isinstance(imp, dict):
                        imports_map.update(imp)
                    stats.files_processed += 1
                    stats.symbols_added += len(data.get("functions", []) or []) + len(
                        data.get("classes", []) or []
                    )
            except Exception:  # noqa: BLE001
                # Per-file failure is not fatal — surface via warning in analyze().
                pass

        if all_file_data:
            try:
                self._builder.link_function_calls(all_file_data, imports_map)
                self._builder.link_inheritance(all_file_data, imports_map)
            except Exception:  # noqa: BLE001
                pass
        return stats

    # ------------------------------------------------------------------
    # query
    # ------------------------------------------------------------------

    def find_symbol(self, name: str) -> list[SymbolRecord]:
        """Resolve a symbol name to candidate records.

        Used by `impact.target_resolved` and `context.symbol`. CGC's finder
        returns dicts; we project to a stable dataclass.
        """
        self._ensure()
        assert self._finder is not None
        try:
            raw = self._finder.find_by_function_name(
                name, fuzzy_search=False, repo_path=str(self.repo_path)
            )
        except Exception:  # noqa: BLE001
            return []
        return [_to_symbol_record(r) for r in (raw or [])]

    def find_callers(self, target: str, depth: int = 3) -> list[Callsite]:
        """Upstream (who-calls-this) traversal.

        Backbone of `impact` risk classification.
        """
        return self._relationships("find_all_callers", target, depth)

    def find_callees(self, target: str, depth: int = 3) -> list[Callsite]:
        """Downstream (what-does-this-call) traversal."""
        return self._relationships("find_all_callees", target, depth)

    def _relationships(self, query_type: str, target: str, depth: int) -> list[Callsite]:
        self._ensure()
        assert self._finder is not None
        try:
            resp = self._finder.analyze_code_relationships(
                query_type=query_type,
                target=target,
                repo_path=str(self.repo_path),
            )
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(resp, dict):
            return []
        raw = resp.get("results") or []
        out: list[Callsite] = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            d = int(r.get("depth") or r.get("distance") or 1)
            if d > depth:
                continue
            name = r.get("name") or r.get("function") or r.get("caller") or r.get("callee") or ""
            if not name:
                continue
            out.append(
                Callsite(
                    name=str(name),
                    file=str(r.get("file") or r.get("path") or ""),
                    line=int(r.get("line") or r.get("line_number") or 0),
                    kind=str(r.get("kind") or r.get("type") or "function"),
                    depth=d,
                )
            )
        return out

    def symbols_in_file(self, rel_path: str) -> SymbolsInFile:
        """List functions/classes defined in a file (by path).

        Best-effort via Cypher against the File→Function/Class edges. If the
        backend rejects the query (dialect mismatch), returns an empty record
        so callers degrade gracefully.
        """
        self._ensure()
        rows = self.cypher(
            "MATCH (f:File)<-[:CONTAINS*0..]-(n) "
            "WHERE f.path ENDS WITH $path AND (n:Function OR n:Class) "
            "RETURN n.name AS name, f.path AS file, n.line_number AS line, labels(n) AS labels",
            {"path": rel_path},
        )
        result = SymbolsInFile(path=rel_path)
        for row in rows:
            labels = row.get("labels") or []
            kind = "class" if "Class" in labels else "function"
            rec = SymbolRecord(
                name=str(row.get("name") or ""),
                file=str(row.get("file") or rel_path),
                line=int(row.get("line") or 0),
                kind=kind,
            )
            if kind == "class":
                result.classes.append(rec)
            else:
                result.functions.append(rec)
        return result

    def cypher(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Raw Cypher escape hatch.

        Not exposed to agents via MCP (too backend-dependent); used internally
        for a handful of queries that the high-level CGC API does not cover
        (e.g. "what symbols does this file define").
        """
        self._ensure()
        assert self._db is not None
        driver = None
        try:
            driver = self._db.get_driver()
        except Exception:  # noqa: BLE001
            return []
        if driver is None:
            return []
        try:
            with driver.session() as session:
                result = session.run(query, params or {})
                return [dict(row) for row in result]
        except Exception:  # noqa: BLE001
            return []


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_SOURCE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".java", ".kt", ".go", ".rs", ".rb", ".php", ".cs",
    ".cpp", ".cc", ".c", ".h", ".hpp", ".swift", ".scala", ".hs",
}

_IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".doubled-graph", ".gitnexus", "dist", "build", ".tox",
}


def _count_source_files(root: Path) -> int:
    n = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & _IGNORE_DIRS:
            continue
        if p.suffix.lower() in _SOURCE_EXTS:
            n += 1
    return n


def _to_symbol_record(r: dict[str, Any]) -> SymbolRecord:
    return SymbolRecord(
        name=str(r.get("name") or ""),
        file=str(r.get("path") or r.get("file") or ""),
        line=int(r.get("line_number") or r.get("line") or 0),
        kind=str(r.get("kind") or r.get("type") or "function"),
        source=str(r.get("source") or ""),
        docstring=str(r.get("docstring") or ""),
    )
