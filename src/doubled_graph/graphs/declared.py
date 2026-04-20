"""Parser for the declared graph (docs/*.xml produced by grace-marketplace).

MVP scope: parse minimal set from development-plan.xml and knowledge-graph.xml
using the stdlib `xml.etree.ElementTree`. Real grace XML schema needs to be
verified against actual templates in research/grace-marketplace-main/ — this
module defines the shape we consume but tolerates missing fields.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeclaredModule:
    id: str
    purpose: str = ""
    paths: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    crosslinks: list[str] = field(default_factory=list)


@dataclass
class DeclaredVerification:
    id: str
    module_id: str
    kind: str = ""


@dataclass
class DeclaredGraph:
    modules: dict[str, DeclaredModule] = field(default_factory=dict)
    verification: dict[str, DeclaredVerification] = field(default_factory=dict)
    loaded_from: list[str] = field(default_factory=list)


def _safe_parse(path: Path) -> ET.Element | None:
    if not path.exists():
        return None
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        return None


def load_declared_graph(repo_path: Path) -> DeclaredGraph:
    """Load declared graph from the conventional docs/ location.

    Why we need an in-process parser (vs always shelling to `grace`):
      doubled-graph's `detect_changes` operation has to cross-reference the
      declared graph with the CGC-computed graph on every call. Forking the
      grace CLI per cross-ref would add noticeable latency on large repos.
      We parse once, cache in-process, and hand CGC-comparable structures to
      `graphs/crossref.py`.

    Tolerant to missing / malformed files — returns whatever it can parse.
    Malformed files are reported in `loaded_from` with a `!` prefix so the
    caller can surface it as a methodology warning instead of a hard error
    (a half-initialised repo mid-migration should still be queryable).
    """
    graph = DeclaredGraph()
    docs = repo_path / "docs"

    dev_plan = docs / "development-plan.xml"
    root = _safe_parse(dev_plan)
    if root is not None:
        graph.loaded_from.append(str(dev_plan))
        # TODO[schema-verify]: actual grace-marketplace XML tag names to be confirmed
        # against skills/grace/grace-init/assets/docs/development-plan.xml.template
        for mod in root.iter("Module"):
            mid = mod.get("id") or mod.findtext("id") or ""
            if not mid:
                continue
            graph.modules[mid] = DeclaredModule(
                id=mid,
                purpose=mod.findtext("purpose", default="") or "",
                paths=[p.text for p in mod.iter("path") if p.text],
            )
    elif dev_plan.exists():
        graph.loaded_from.append(f"!{dev_plan}")

    kg = docs / "knowledge-graph.xml"
    root = _safe_parse(kg)
    if root is not None:
        graph.loaded_from.append(str(kg))
        for mod in root.iter("Module"):
            mid = mod.get("id") or mod.findtext("id") or ""
            existing = graph.modules.get(mid) or DeclaredModule(id=mid)
            for ex in mod.iter("Export"):
                name = ex.get("name") or ex.text or ""
                if name:
                    existing.exports.append(name)
            for cl in mod.iter("CrossLink"):
                target = cl.get("to") or cl.text or ""
                if target:
                    existing.crosslinks.append(target)
            graph.modules[mid] = existing
    elif kg.exists():
        graph.loaded_from.append(f"!{kg}")

    vp = docs / "verification-plan.xml"
    root = _safe_parse(vp)
    if root is not None:
        graph.loaded_from.append(str(vp))
        for v in root.iter("Verification"):
            vid = v.get("id") or ""
            mid = v.get("module") or ""
            if vid:
                graph.verification[vid] = DeclaredVerification(
                    id=vid, module_id=mid, kind=v.get("kind", "")
                )
    elif vp.exists():
        graph.loaded_from.append(f"!{vp}")

    return graph
