"""`detect_changes` tool — drift between computed (CGC) and declared (docs/*.xml).

Cross-references the two graphs and categorises the drift:
  - code_without_module   : live code files not owned by any M-*
  - module_without_code   : M-* with no living source files
  - stale_crosslinks      : declared CrossLinks with no computed edges
  - missing_verification  : M-* missing V-M-* entries
  - markup_missing        : touched files without MODULE_CONTRACT / MODULE_MAP

`contract_mismatch` would require signature-level parsing and is left as a
warning in the MVP (ROADMAP.md). The four categories above are load-bearing
for `on-before-commit` and cover the drift types the methodology blocks on.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from doubled_graph.graphs.declared import load_declared_graph
from doubled_graph.integrations.cgc import CGC, CGCUnavailable
from doubled_graph.tools._meta import Meta, build_meta


class CodeWithoutModule(BaseModel):
    file: str
    functions: list[str] = Field(default_factory=list)
    reason: str = ""


class ModuleWithoutCode(BaseModel):
    module_id: str
    reason: str = ""


class StaleCrosslink(BaseModel):
    from_module: str
    to_module: str
    reason: str = ""


class MissingVerification(BaseModel):
    module_id: str
    reason: str = ""


class MarkupMissing(BaseModel):
    file: str
    missing: list[str] = Field(default_factory=list)


class Drift(BaseModel):
    code_without_module: list[CodeWithoutModule] = Field(default_factory=list)
    module_without_code: list[ModuleWithoutCode] = Field(default_factory=list)
    stale_crosslinks: list[StaleCrosslink] = Field(default_factory=list)
    missing_verification: list[MissingVerification] = Field(default_factory=list)
    markup_missing: list[MarkupMissing] = Field(default_factory=list)


class ResolutionHint(BaseModel):
    phase: str
    action: str


class DetectWarning(BaseModel):
    code: str
    detail: str = ""


class DetectChangesResult(BaseModel):
    scope_used: str
    files_examined: list[str] = Field(default_factory=list)
    drift: Drift = Field(default_factory=Drift)
    resolution_hint_by_phase: ResolutionHint
    warnings: list[DetectWarning] = Field(default_factory=list)
    meta: Meta


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _files_for_scope(repo: Path, scope: str, base_ref: str, since_ref: str) -> list[str]:
    if scope == "staged":
        return _git(["diff", "--name-only", "--cached"], repo)
    if scope == "branch":
        return _git(["diff", "--name-only", f"{base_ref}...HEAD"], repo)
    if scope == "compare":
        return _git(["diff", "--name-only", since_ref, "HEAD"], repo)
    # all — list every tracked file; falls back to walking fs if git unavailable
    files = _git(["ls-files"], repo)
    if files:
        return files
    return [
        str(p.relative_to(repo))
        for p in repo.rglob("*")
        if p.is_file() and ".git" not in p.parts and ".doubled-graph" not in p.parts
    ]


# ---------------------------------------------------------------------------
# markup scan
# ---------------------------------------------------------------------------


def _markup_missing(repo: Path, file_rel: str) -> list[str]:
    """Heuristic markup check: presence of MODULE_CONTRACT / MODULE_MAP tags.

    We don't validate structure — that's `doubled-graph lint`'s job. Here we
    only flag files that have zero methodology markers, which is the signal
    `detect_changes` uses to suggest running `grace-reviewer`.
    """
    p = repo / file_rel
    if not p.exists() or not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    missing: list[str] = []
    if "MODULE_CONTRACT" not in text:
        missing.append("MODULE_CONTRACT")
    if "MODULE_MAP" not in text:
        missing.append("MODULE_MAP")
    return missing


def _owned_by_module(file_rel: str, modules: dict) -> str | None:
    best = None
    for mod in modules.values():
        for p in mod.paths:
            if not p:
                continue
            if file_rel == p or file_rel.startswith(p.rstrip("/") + "/"):
                if best is None or len(p) > len(best[0]):
                    best = (p, mod.id)
    return best[1] if best else None


def _module_has_living_files(repo: Path, mod) -> bool:
    for p in mod.paths:
        if not p:
            continue
        target = repo / p
        if target.exists():
            return True
    return False


_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".php", ".cs"}


def _is_source(file_rel: str) -> bool:
    return Path(file_rel).suffix.lower() in _SOURCE_EXTS


def _resolution_hint(phase: str) -> ResolutionHint:
    if phase == "migration":
        return ResolutionHint(
            phase="migration",
            action="code = ground-truth; update docs/*.xml to match reality.",
        )
    return ResolutionHint(
        phase="post_migration",
        action="artifacts = ground-truth. For each drift — ask user: new requirement | bug | not-know. For scope=staged — block commit until resolved.",
    )


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


def detect_changes(
    repo_path: Path,
    scope: str = "staged",
    base_ref: str = "main",
    since_ref: str = "HEAD~1",
    include_unchanged: bool = False,  # noqa: ARG001 — reserved for v2
) -> DetectChangesResult:
    meta = build_meta(repo_path)
    warnings: list[DetectWarning] = []
    declared = load_declared_graph(repo_path)

    files = _files_for_scope(repo_path, scope, base_ref, since_ref)
    files = [f for f in files if _is_source(f)]

    drift = Drift()
    cgc = CGC(repo_path)

    # code_without_module + markup_missing + functions-per-file via CGC
    for f in files:
        owner = _owned_by_module(f, declared.modules)
        fns: list[str] = []
        if not owner:
            try:
                sif = cgc.symbols_in_file(f)
                fns = [s.name for s in sif.functions]
            except CGCUnavailable as e:
                warnings.append(DetectWarning(code="CGC_BACKEND_FAIL", detail=str(e)))
            except Exception:  # noqa: BLE001
                fns = []
            drift.code_without_module.append(
                CodeWithoutModule(
                    file=f,
                    functions=fns,
                    reason="no M-* in development-plan.xml matches this path",
                )
            )
        missing_markup = _markup_missing(repo_path, f)
        if missing_markup:
            drift.markup_missing.append(MarkupMissing(file=f, missing=missing_markup))

    # module_without_code — iterate declared modules
    for mod in declared.modules.values():
        if not mod.paths:
            # Module with no paths declared — treat as orphan only if we're scanning all
            if scope == "all":
                drift.module_without_code.append(
                    ModuleWithoutCode(module_id=mod.id, reason="no <path> declared for module")
                )
            continue
        if not _module_has_living_files(repo_path, mod):
            drift.module_without_code.append(
                ModuleWithoutCode(
                    module_id=mod.id,
                    reason="listed in development-plan.xml but no matching files on disk",
                )
            )

    # missing_verification — M-* with no V-M-*
    mids_with_verif = {v.module_id for v in declared.verification.values() if v.module_id}
    for mid in declared.modules:
        if mid not in mids_with_verif:
            drift.missing_verification.append(
                MissingVerification(
                    module_id=mid,
                    reason="code exists, module exists, but no V-M-* entries in verification-plan.xml",
                )
            )

    # stale_crosslinks — declared CrossLink but no computed edge
    # MVP: mark as stale only if target module doesn't exist; a full edge check
    # requires cross-file call data which belongs to a v2 implementation.
    for mod in declared.modules.values():
        for target in mod.crosslinks:
            if target and target not in declared.modules:
                drift.stale_crosslinks.append(
                    StaleCrosslink(
                        from_module=mod.id,
                        to_module=target,
                        reason="CrossLink target module is not declared in knowledge-graph.xml",
                    )
                )

    return DetectChangesResult(
        scope_used=scope,
        files_examined=files,
        drift=drift,
        resolution_hint_by_phase=_resolution_hint(meta.phase),
        warnings=warnings,
        meta=meta,
    )
