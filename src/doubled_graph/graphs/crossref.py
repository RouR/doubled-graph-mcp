"""Crossref between declared and computed graphs.

MVP status: pure interface — the heavy lifting (matching observed CGC nodes
to declared M-* records, detecting contract mismatches) is deliberately left
for post-review implementation. This module exists so detect_changes.py and
downstream callers have stable import targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from doubled_graph.graphs.declared import DeclaredGraph


@dataclass
class Crossref:
    matches: list[tuple[str, str]] = field(default_factory=list)  # (module_id, file_path)
    code_without_module: list[dict] = field(default_factory=list)
    module_without_code: list[dict] = field(default_factory=list)
    contract_mismatch: list[dict] = field(default_factory=list)
    stale_crosslinks: list[dict] = field(default_factory=list)
    missing_verification: list[dict] = field(default_factory=list)


def crossref_computed_and_declared(
    declared: DeclaredGraph,
    computed_files: list[str],
) -> Crossref:
    """Stub matcher — returns empty drift. Real implementation goes here."""
    return Crossref()
