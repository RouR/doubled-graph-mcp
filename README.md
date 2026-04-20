# doubled-graph

**MCP facade for LLM-driven codebases.** Four tools — `analyze`, `impact`, `context`, `detect_changes` — that combine a computed AST graph (via [CodeGraphContext](https://github.com/Shashankss1205/CodeGraphContext)) with a declared methodology graph (via [grace-marketplace](https://github.com/osovv/grace)) so your agent can reason about blast radius and drift before it edits code.

License: MIT.

---

## What it does

Large codebases break LLM agents two ways:
1. They edit without knowing who calls the function → regression.
2. They edit without knowing the declared contract → silent drift.

`doubled-graph` gives the agent one gateway over two graphs:

| Graph | Source | Answers |
|-------|--------|---------|
| **Computed** | CodeGraphContext (tree-sitter AST → graph DB) | who calls X, what X calls, where X is defined |
| **Declared** | grace-marketplace artifacts (`docs/*.xml`) | which module owns X, its contract, its verification entries |

Four MCP tools expose the cross-reference:

| Tool | Use | When |
|------|-----|------|
| `analyze` | build/update the computed graph | after commit, on CI, at onboarding |
| `impact` | blast radius + risk for a symbol | **before** editing |
| `context` | 360° view (symbol + contract + module + callers/callees) | before non-trivial edits |
| `detect_changes` | drift between code and artifacts | **before** commit |

Plus 11 gateway tools that thin-wrap grace-marketplace operations (`lint`, `module_show`, `file_show`, `refresh`, skills like `init`/`plan`/`execute`/`fix`/...) so your agent talks to a single namespace.

---

## Install

```bash
pip install doubled-graph
```

Requires Python 3.11+. On first use, CGC will pick an embedded graph backend (FalkorDB Lite on Linux, KuzuDB on Windows; or Neo4j if configured via `NEO4J_URI`).

---

## Onboard a repo

One command sets everything up:

```bash
doubled-graph setup
```

That will:
1. install `@osovv/grace-cli` globally via `bun add -g` (skipped if Bun is not present),
2. copy bundled `prompts/` and `methodology/` into the repo,
3. register doubled-graph as an MCP server for the detected IDE (Claude Code / Cursor / Continue),
4. install a `git post-commit` hook that keeps the computed graph fresh,
5. run the first full `analyze` pass.

Preview what it will do without touching anything:

```bash
doubled-graph setup --dry-run
```

Pick the IDE explicitly if auto-detect misses:

```bash
doubled-graph setup --ide claude-code
```

---

## Day-to-day CLI

```bash
# Compute or refresh the graph (hooks call this automatically).
doubled-graph analyze --mode auto

# Blast radius for a symbol — run BEFORE editing.
doubled-graph impact validateUser
doubled-graph impact validateUser --direction both --depth 3

# 360° view — contract + module + callers + callees.
doubled-graph context validateUser

# Drift between code and declared artifacts — run BEFORE committing.
doubled-graph detect-changes --scope staged

# Current methodology phase (migration | post_migration).
doubled-graph phase get
doubled-graph phase set post_migration --reason "migration complete"

# Serve as an MCP server over stdio (IDE calls this).
doubled-graph serve
```

---

## MCP usage (Claude Code example)

`.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "doubled-graph": {
      "command": "doubled-graph",
      "args": ["serve"]
    }
  }
}
```

Then in your agent system prompt / `CLAUDE.md`:

> - **MUST run `impact` before editing any symbol.**
> - **MUST run `detect_changes` before committing.**

---

## The four core tools — input/output shape

Full schemas in [TOOLS.md](TOOLS.md). Summary:

```jsonc
// impact
{ "target": "validateUser", "direction": "upstream", "depth": 3 }
→ {
    "target_resolved": { "name": "...", "file": "...", "module_id": "M-AUTH-VALIDATE" },
    "direct": [ { "name": "...", "file": "...", "depth": 1 } ],
    "transitive": [ ... ],
    "affected_modules": [ ... ],
    "affected_verification": [ ... ],
    "risk": { "level": "HIGH", "reasons": [ ... ] },
    "meta": { "phase": "post_migration", ... }
  }
```

Risk levels: `NONE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Any `HIGH`/`CRITICAL` result means the methodology expects the agent to stop and surface the radius before editing.

---

## Layout

- [SPEC.md](SPEC.md) — architecture, storage layout (`.doubled-graph/`), wire format
- [TOOLS.md](TOOLS.md) — detailed tool spec (schemas, CGC mapping, use-cases)
- [HOOKS.md](HOOKS.md) — git + Claude Code hook contracts
- [CHANGELOG.md](CHANGELOG.md) — release notes

---

## Phase switch

The methodology has two modes — `migration` (code is ground-truth) and `post_migration` (artifacts are ground-truth). doubled-graph reads the phase from an HTML-comment block in `AGENTS.md`:

```markdown
<!-- doubled-graph:phase:start -->
## doubled-graph phase
phase: post_migration
<!-- doubled-graph:phase:end -->
```

Switch atomically:

```bash
doubled-graph phase set migration --reason "starting migration of legacy module"
```

`impact` risk rules and `detect_changes` resolution hints branch on this phase.

---

## Project status

- Smoke-tested (29/29 passing).
- Real CGC integration wired; stubs removed.
- Ships with bundled `prompts/` and `methodology/` assets (loaded via `importlib.resources`).

Upstream versions pinned: `codegraphcontext >= 0.1`, `mcp >= 0.9`.

---

## License

MIT — see [LICENSE](LICENSE).

Upstream components retain their own licenses (CodeGraphContext: MIT; grace-marketplace: MIT). GitNexus is **not** a dependency (PolyForm NC incompatibility).
