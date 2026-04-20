"""Phase policy — read `phase:` from AGENTS.md.

Format contract (see METHODOLOGY_DRAFT.md § 9.3):

    <!-- doubled-graph:phase:start -->
    ## doubled-graph phase
    phase: migration    # or post_migration
    updated: 2026-04-18
    <!-- doubled-graph:phase:end -->

Default when block or `phase:` line is missing: post_migration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

Phase = Literal["migration", "post_migration"]

_BLOCK_START = "<!-- doubled-graph:phase:start -->"
_BLOCK_END = "<!-- doubled-graph:phase:end -->"
_PHASE_RE = re.compile(r"^\s*phase:\s*(\w+)\s*(?:#.*)?$", re.MULTILINE)


def set_phase(repo_path: Path, value: Phase, reason: str = "") -> dict:
    """Rewrite the phase-block in AGENTS.md atomically.

    Why this is a single-writer API: phase is the root policy switch. Hand-
    editing AGENTS.md is error-prone (easy to break the HTML-comment sentinels
    and silently confuse the parser). This function keeps a stable contract:
      - If the block is missing, it appends one at end of AGENTS.md.
      - If AGENTS.md is missing, it creates one with just the phase block.
      - Existing content outside the block is preserved byte-for-byte.
      - Writes the new file atomically via a temp file + rename.

    Returns a dict `{path, previous, current, created_file, appended_block}`.
    """
    from datetime import datetime, timezone
    import tempfile

    agents_md = repo_path / "AGENTS.md"
    created_file = False
    appended_block = False
    previous: Phase | None = None

    if agents_md.exists():
        original = agents_md.read_text(encoding="utf-8")
        previous = read_phase(repo_path)
    else:
        original = ""
        created_file = True

    today = datetime.now(timezone.utc).date().isoformat()
    reason_line = f"\n<!-- reason: {reason} -->" if reason else ""
    new_block = (
        f"{_BLOCK_START}\n"
        f"## doubled-graph phase\n"
        f"phase: {value}\n"
        f"updated: {today}{reason_line}\n"
        f"{_BLOCK_END}"
    )

    if _BLOCK_START in original and _BLOCK_END in original:
        before, rest = original.split(_BLOCK_START, 1)
        _old_block, after = rest.split(_BLOCK_END, 1)
        new_text = before + new_block + after
    else:
        sep = "\n\n" if original and not original.endswith("\n") else "\n"
        new_text = original + sep + new_block + "\n"
        appended_block = True

    # Atomic write: temp file in same dir, then rename. Avoids half-written state.
    agents_md.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(agents_md.parent),
        prefix=".agents-md.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(new_text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(agents_md)

    return {
        "path": str(agents_md),
        "previous": previous,
        "current": value,
        "created_file": created_file,
        "appended_block": appended_block,
    }


def read_phase(repo_path: Path, default: Phase = "post_migration") -> Phase:
    """Return the current methodology phase from AGENTS.md.

    Why this one function is load-bearing:
      Every drift-resolution prompt, every `impact` risk classification, and
      every `detect_changes` verdict branches on phase. We deliberately keep
      the phase in a single, grep-able block in AGENTS.md (not env vars, not
      CLI flags) so PR review sees the switch, and every tool path converges
      on read_phase() rather than re-parsing independently.

      Default=post_migration because that's the safer policy (artifacts are
      ground-truth; drift blocks merges). An absent block shouldn't
      accidentally unlock migration-mode's looser rules.
    """
    agents_md = repo_path / "AGENTS.md"
    if not agents_md.exists():
        return default
    text = agents_md.read_text(encoding="utf-8", errors="replace")
    if _BLOCK_START not in text or _BLOCK_END not in text:
        return default
    block = text.split(_BLOCK_START, 1)[1].split(_BLOCK_END, 1)[0]
    m = _PHASE_RE.search(block)
    if not m:
        return default
    value = m.group(1).strip()
    if value in ("migration", "post_migration"):
        return value  # type: ignore[return-value]
    # Invalid value — surface via grace lint; here we fall back to default.
    return default
