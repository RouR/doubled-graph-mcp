# Changelog

All notable changes to doubled-graph. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [1.0.2] — 2026-04-20

Initial public release.

### Added
- `doubled-graph setup` — single-shot onboarding: installs `@osovv/grace-cli`,
  copies bundled prompts + methodology into the repo, registers MCP for the
  detected IDE (Claude Code / Cursor / Continue), installs the git post-commit
  hook, runs the first full analyze. Supports `--dry-run` and `--ide` override.
- Real CGC integration in `integrations/cgc.py`:
  - `analyze_full`, `analyze_incremental` wired to `GraphBuilder`
    (`add_repository_to_graph` / `delete_file_from_graph` / `parse_file` /
    `link_function_calls` / `link_inheritance`)
  - `find_callers`, `find_callees` wired to
    `CodeFinder.analyze_code_relationships(find_all_callers / find_all_callees)`
  - `find_symbol` wired to `CodeFinder.find_by_function_name`
  - `symbols_in_file` via Cypher fallback
- `impact` now returns populated `direct` / `transitive` / `affected_modules` /
  `affected_verification`. Risk classification uses real caller counts +
  phase + verification-touch.
- `context` fully implemented — joins CGC symbol, declared module, and
  extracts `MODULE_CONTRACT` / `CONTRACT:fn` blocks from source.
- `detect_changes` fully implemented — `code_without_module`,
  `module_without_code`, `stale_crosslinks`, `missing_verification`,
  `markup_missing`. Resolution hint branches on `migration` vs
  `post_migration`.
- `analyze` now persists `.doubled-graph/cache/code-fingerprint.json` on
  every successful run (enables `mode=auto` incremental detection).
- CLI subcommands `impact`, `context`, `detect-changes` are no longer stubs —
  they dispatch into the tools package.
- Bundled `prompts/` and `methodology/` shipped inside the wheel via
  `hatch force-include`; loaded with `importlib.resources` by `setup.py`.
- 29 smoke tests covering CGC stubs, impact risk escalation, context joins,
  drift detection, CLI wiring, setup dry-run + MCP registration.

### Changed
- Bumped version 0.1.0.dev0 → 0.1.0.
- pyproject: added classifiers, keywords, URLs, `anyio` runtime dep, sdist
  manifest.
- `README.md` replaces `SPEC.md` as the PyPI long description.

### Removed
- `NotImplementedError` stubs in `integrations/cgc.py`.
- `NOT_IMPLEMENTED_MVP` stub classes for `context` and `detect_changes`.
- CLI `NOT_IMPLEMENTED_MVP` fallback for `impact` / `context` /
  `detect-changes`.
