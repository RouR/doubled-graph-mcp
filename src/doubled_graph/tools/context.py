"""`context` tool — 360-view on a symbol.

Joins computed graph (CGC) with declared graph (docs/*.xml) and extracts the
MODULE_CONTRACT / CONTRACT:fn block from source. See TOOLS.md §3.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from doubled_graph.graphs.declared import load_declared_graph
from doubled_graph.integrations.cgc import CGC, Callsite, CGCUnavailable
from doubled_graph.tools._meta import Meta, build_meta


class ContextSymbol(BaseModel):
    name: str
    file: str | None = None
    line: int | None = None
    kind: str | None = None
    source: str = ""
    docstring: str = ""


class ContextContract(BaseModel):
    source: str = "source-scan"
    text: str = ""
    links: list[str] = Field(default_factory=list)


class ContextModule(BaseModel):
    id: str | None = None
    purpose: str = ""
    exports: list[str] = Field(default_factory=list)
    crosslinks: list[str] = Field(default_factory=list)


class ContextCallsite(BaseModel):
    name: str
    file: str | None = None
    line: int | None = None
    module_id: str | None = None
    depth: int = 1


class ContextVerification(BaseModel):
    id: str
    kind: str = ""


class ContextWarning(BaseModel):
    code: str
    detail: str = ""


class ContextResult(BaseModel):
    symbol: ContextSymbol
    contract: ContextContract
    module: ContextModule
    callers: list[ContextCallsite] = Field(default_factory=list)
    callees: list[ContextCallsite] = Field(default_factory=list)
    verification: list[ContextVerification] = Field(default_factory=list)
    warnings: list[ContextWarning] = Field(default_factory=list)
    meta: Meta


# ---------------------------------------------------------------------------
# contract extraction
# ---------------------------------------------------------------------------


_CONTRACT_MARKERS = [
    # (start regex, end regex)
    (re.compile(r"(?:^|\n)\s*#+\s*MODULE_CONTRACT\b", re.IGNORECASE),
     re.compile(r"\n\s*#+\s*END[_ ]MODULE_CONTRACT\b", re.IGNORECASE)),
    (re.compile(r"(?:^|\n)\s*(?:\*|//|#)\s*CONTRACT:\s*(\w+)", re.IGNORECASE), None),
]


def _extract_contract(file_path: Path, symbol: str) -> str:
    """Best-effort extraction of a contract block near a symbol.

    Looks for:
      - a file-level `MODULE_CONTRACT` / `END_MODULE_CONTRACT` block
      - a `CONTRACT: <symbol>` line immediately above the symbol

    Returns the raw text (verbatim) or "" if nothing matches. Keeps parsing
    lenient — any parse failure degrades to empty, never raises.
    """
    if not file_path or not file_path.exists():
        return ""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    # Module contract block
    m = re.search(r"MODULE_CONTRACT\b(.*?)END[_ ]MODULE_CONTRACT", text, flags=re.S | re.IGNORECASE)
    if m:
        return m.group(0).strip()

    # CONTRACT: <symbol> ... (next blank line or symbol def)
    pattern = re.compile(
        r"(?:^|\n)([ \t]*(?:#|//|\*)[^\n]*CONTRACT:\s*" + re.escape(symbol) + r"[^\n]*(?:\n[ \t]*(?:#|//|\*)[^\n]*)*)",
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if m:
        return m.group(1).strip()
    return ""


def _crosslink_targets(contract_text: str) -> list[str]:
    """Extract M-*/V-M-* identifiers mentioned inside a contract block."""
    if not contract_text:
        return []
    ids = re.findall(r"\b(?:V-)?M-[A-Z0-9][A-Z0-9\-]*\b", contract_text)
    # preserve order, dedupe
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _module_for_file(declared, file_rel: str) -> str | None:
    if not file_rel:
        return None
    best = None
    for mod in declared.modules.values():
        for p in mod.paths:
            if not p:
                continue
            if file_rel == p or file_rel.startswith(p.rstrip("/") + "/"):
                if best is None or len(p) > len(best[0]):
                    best = (p, mod.id)
    return best[1] if best else None


def _to_callsite(cs: Callsite, declared, repo_path: Path) -> ContextCallsite:
    rel = cs.file
    try:
        if rel and Path(cs.file).is_absolute():
            rel = str(Path(cs.file).relative_to(repo_path))
    except ValueError:
        pass
    return ContextCallsite(
        name=cs.name,
        file=rel or None,
        line=cs.line or None,
        module_id=_module_for_file(declared, rel or ""),
        depth=cs.depth,
    )


def context(
    repo_path: Path,
    name: str,
    depth_callers: int = 2,
    depth_callees: int = 2,
) -> ContextResult:
    meta = build_meta(repo_path)
    warnings: list[ContextWarning] = []
    declared = load_declared_graph(repo_path)

    cgc = CGC(repo_path)
    symbol = ContextSymbol(name=name)
    callers: list[ContextCallsite] = []
    callees: list[ContextCallsite] = []

    try:
        candidates = cgc.find_symbol(name)
        if not candidates:
            warnings.append(
                ContextWarning(code="NOT_FOUND", detail=f"symbol '{name}' not found in computed graph")
            )
        elif len(candidates) > 1:
            warnings.append(
                ContextWarning(
                    code="AMBIGUOUS",
                    detail=f"{len(candidates)} matches for '{name}'; using first. Narrow with module.fn.",
                )
            )
        if candidates:
            sym = candidates[0]
            rel = sym.file
            try:
                if rel and Path(sym.file).is_absolute():
                    rel = str(Path(sym.file).relative_to(repo_path))
            except ValueError:
                pass
            symbol = ContextSymbol(
                name=sym.name,
                file=rel or None,
                line=sym.line or None,
                kind=sym.kind,
                source=sym.source,
                docstring=sym.docstring,
            )

        for cs in cgc.find_callers(name, depth=depth_callers):
            callers.append(_to_callsite(cs, declared, repo_path))
        for cs in cgc.find_callees(name, depth=depth_callees):
            callees.append(_to_callsite(cs, declared, repo_path))
    except CGCUnavailable as e:
        warnings.append(ContextWarning(code="CGC_BACKEND_FAIL", detail=str(e)))
    except Exception as e:  # noqa: BLE001
        warnings.append(ContextWarning(code="CGC_BACKEND_FAIL", detail=f"{type(e).__name__}: {e}"))

    # Contract text
    contract_text = ""
    if symbol.file:
        contract_text = _extract_contract(repo_path / symbol.file, symbol.name)
    contract = ContextContract(text=contract_text, links=_crosslink_targets(contract_text))

    # Module record
    module_id = _module_for_file(declared, symbol.file or "")
    module = ContextModule(id=module_id)
    if module_id and module_id in declared.modules:
        dm = declared.modules[module_id]
        module = ContextModule(
            id=module_id,
            purpose=dm.purpose,
            exports=list(dm.exports),
            crosslinks=list(dm.crosslinks),
        )

    # Verification records for this module
    verification = [
        ContextVerification(id=v.id, kind=v.kind or "")
        for v in declared.verification.values()
        if v.module_id == module_id
    ]

    return ContextResult(
        symbol=symbol,
        contract=contract,
        module=module,
        callers=callers,
        callees=callees,
        verification=verification,
        warnings=warnings,
        meta=meta,
    )
