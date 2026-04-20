"""`impact` tool — blast-radius analysis.

Methodology rule (CLAUDE.md, prompts/maintenance/on-before-edit): the agent
MUST call impact before editing any symbol and MUST stop if `risk.level` is
HIGH/CRITICAL. So this function is the guardrail that keeps runaway edits from
breaking downstream callers, verification entries, or declared critical-path
flows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from doubled_graph.graphs.declared import DeclaredGraph, load_declared_graph
from doubled_graph.integrations.cgc import CGC, Callsite, CGCUnavailable
from doubled_graph.tools._meta import Meta, build_meta


class TargetResolved(BaseModel):
    name: str
    file: str | None = None
    line: int | None = None
    kind: str | None = None
    module_id: str | None = None


class Dependent(BaseModel):
    name: str
    file: str | None = None
    line: int | None = None
    module_id: str | None = None
    depth: int = 1


class AffectedModule(BaseModel):
    id: str
    exports_changed: bool = False
    crosslinks_to: list[str] = Field(default_factory=list)


class AffectedVerification(BaseModel):
    id: str
    kind: str


class Risk(BaseModel):
    level: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    reasons: list[str] = Field(default_factory=list)


class ImpactWarning(BaseModel):
    code: str
    detail: str = ""


class ImpactResult(BaseModel):
    target_resolved: TargetResolved
    direct: list[Dependent] = Field(default_factory=list)
    transitive: list[Dependent] = Field(default_factory=list)
    affected_modules: list[AffectedModule] = Field(default_factory=list)
    affected_verification: list[AffectedVerification] = Field(default_factory=list)
    risk: Risk
    warnings: list[ImpactWarning] = Field(default_factory=list)
    meta: Meta


# ---------------------------------------------------------------------------
# risk & declared-graph helpers
# ---------------------------------------------------------------------------


def _classify_risk(
    direct_count: int,
    touches_verification: bool,
    phase: str,
    on_critical_path: bool = False,
) -> Risk:
    reasons: list[str] = []
    if direct_count == 0:
        level: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
        reasons.append("no direct callers in computed graph (may still have transitive)")
    elif direct_count <= 3:
        level = "MEDIUM"
        reasons.append(f"direct callers count = {direct_count}")
    elif direct_count <= 10:
        level = "HIGH"
        reasons.append(f"direct callers count = {direct_count}")
    else:
        level = "CRITICAL"
        reasons.append(f"direct callers count = {direct_count}")

    if touches_verification:
        reasons.append("touches verification entries (V-M-*)")
        if level == "LOW":
            level = "MEDIUM"
        elif level == "MEDIUM":
            level = "HIGH"

    if on_critical_path:
        reasons.append("member of a declared critical-path flow (development-plan.xml)")
        level = "CRITICAL"

    if phase == "post_migration":
        reasons.append("phase=post_migration — contract drift check required before edit")

    return Risk(level=level, reasons=reasons)


def _module_for_file(graph: DeclaredGraph, file_rel: str) -> str | None:
    """Resolve which M-* owns a file path, by prefix match on Module.paths."""
    if not file_rel:
        return None
    best: tuple[int, str] | None = None
    for mod in graph.modules.values():
        for p in mod.paths:
            if not p:
                continue
            if file_rel == p or file_rel.startswith(p.rstrip("/") + "/"):
                score = len(p)
                if best is None or score > best[0]:
                    best = (score, mod.id)
    return best[1] if best else None


def _verifications_for_module(graph: DeclaredGraph, module_id: str) -> list[AffectedVerification]:
    return [
        AffectedVerification(id=v.id, kind=v.kind or "")
        for v in graph.verification.values()
        if v.module_id == module_id
    ]


def _is_on_critical_path(graph: DeclaredGraph, module_id: str | None) -> bool:
    if not module_id:
        return False
    mod = graph.modules.get(module_id)
    if mod is None:
        return False
    # MVP: declared schema doesn't surface a flag yet; reserved for extension.
    return False


def _to_dependent(cs: Callsite, graph: DeclaredGraph, repo_path: Path) -> Dependent:
    rel = cs.file
    try:
        if rel and Path(cs.file).is_absolute():
            rel = str(Path(cs.file).relative_to(repo_path))
    except ValueError:
        pass
    return Dependent(
        name=cs.name,
        file=rel or None,
        line=cs.line or None,
        module_id=_module_for_file(graph, rel or ""),
        depth=cs.depth,
    )


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


def impact(
    repo_path: Path,
    target: str,
    direction: str = "upstream",
    depth: int = 3,
    include_tests: bool = True,
    scope: str = "full",
) -> ImpactResult:
    meta = build_meta(repo_path)
    warnings: list[ImpactWarning] = []
    try:
        declared = load_declared_graph(repo_path)
    except Exception as e:  # noqa: BLE001
        declared = DeclaredGraph()
        warnings.append(ImpactWarning(code="DECLARED_MALFORMED", detail=str(e)))

    cgc = CGC(repo_path)
    target_resolved = TargetResolved(name=target)

    direct: list[Dependent] = []
    transitive: list[Dependent] = []

    try:
        # Resolve target
        candidates = cgc.find_symbol(target)
        if len(candidates) == 1:
            sym = candidates[0]
            rel = sym.file
            try:
                if rel and Path(sym.file).is_absolute():
                    rel = str(Path(sym.file).relative_to(repo_path))
            except ValueError:
                pass
            target_resolved = TargetResolved(
                name=sym.name,
                file=rel or None,
                line=sym.line or None,
                kind=sym.kind,
                module_id=_module_for_file(declared, rel or ""),
            )
        elif len(candidates) > 1:
            warnings.append(
                ImpactWarning(
                    code="INVALID_INPUT",
                    detail=f"{len(candidates)} candidates match '{target}'; narrow with module.fn or file path.",
                )
            )

        # Upstream / downstream traversal
        callsites: list[Callsite] = []
        if direction in ("upstream", "both"):
            callsites.extend(cgc.find_callers(target, depth=depth))
        if direction in ("downstream", "both"):
            callsites.extend(cgc.find_callees(target, depth=depth))

        if not include_tests:
            callsites = [c for c in callsites if not _looks_like_test(c.file)]

        for cs in callsites:
            dep = _to_dependent(cs, declared, repo_path)
            (direct if cs.depth <= 1 else transitive).append(dep)

    except CGCUnavailable as e:
        warnings.append(ImpactWarning(code="CGC_BACKEND_FAIL", detail=str(e)))
    except Exception as e:  # noqa: BLE001
        warnings.append(ImpactWarning(code="CGC_BACKEND_FAIL", detail=f"{type(e).__name__}: {e}"))

    # Affected modules: unique module ids from direct + transitive
    affected_ids: list[str] = []
    for dep in direct + transitive:
        if dep.module_id and dep.module_id not in affected_ids:
            affected_ids.append(dep.module_id)
    affected_modules = [
        AffectedModule(
            id=mid,
            crosslinks_to=list(declared.modules[mid].crosslinks) if mid in declared.modules else [],
        )
        for mid in affected_ids
    ]

    # Affected verification: union over target + affected modules
    verif_ids: list[AffectedVerification] = []
    seen: set[str] = set()
    for mid in [target_resolved.module_id, *affected_ids]:
        if not mid:
            continue
        for v in _verifications_for_module(declared, mid):
            if v.id not in seen:
                seen.add(v.id)
                verif_ids.append(v)

    risk = _classify_risk(
        direct_count=len(direct),
        touches_verification=bool(verif_ids),
        phase=meta.phase,
        on_critical_path=_is_on_critical_path(declared, target_resolved.module_id),
    )

    return ImpactResult(
        target_resolved=target_resolved,
        direct=direct,
        transitive=transitive,
        affected_modules=affected_modules,
        affected_verification=verif_ids,
        risk=risk,
        warnings=warnings,
        meta=meta,
    )


def _looks_like_test(file_path: str) -> bool:
    if not file_path:
        return False
    lower = file_path.lower()
    return (
        "/tests/" in lower
        or "/test/" in lower
        or "/__tests__/" in lower
        or lower.startswith("tests/")
        or lower.startswith("test/")
        or lower.endswith("_test.py")
        or lower.endswith(".test.ts")
        or lower.endswith(".test.tsx")
        or lower.endswith(".test.js")
        or lower.endswith(".spec.ts")
        or lower.endswith(".spec.js")
    )
