# doubled-graph — TOOLS (v0.1 draft)

**Scope:** формальная спецификация 4 публичных MCP-инструментов. Каждый включает: назначение, входы (JSON schema), выходы (pydantic-like), маппинг на внутренние вызовы CGC и grace-cli, примеры use-case'ов из grace-marketplace skills.

**Общие правила всех tools:**
- Имена полей — `snake_case`.
- Каждый ответ содержит `meta: { phase, tool_version, timestamp_iso, trace_id }`.
- Ошибки возвращаются как MCP error с кодами: `INDEX_STALE`, `CGC_BACKEND_FAIL`, `GRACE_CLI_MISSING`, `DECLARED_MALFORMED`, `NOT_IMPLEMENTED_MVP`, `INVALID_INPUT`.
- Все символьные имена (`target`, `name`) интерпретируются с учётом scope: файл → путь от корня репо; функция → `module.function` или просто `function`; класс → `module.Class`. При неоднозначности — возвращается `INVALID_INPUT` со списком кандидатов.

---

## 1. `analyze`

**Назначение:** построить/обновить computed graph (CGC) по репозиторию. Аналог `cgc index` + `cgc watch` с методологической семантикой.

**Когда вызывает агент:**
- После `doubled-graph init` — первичное индексирование.
- После коммита с кодовыми изменениями — инкремент (если hook не сработал).
- Перед `impact`/`context`, если `meta.index_freshness_s` > configured threshold.

### 1.1 Input

```json
{
  "mode": "auto" | "full" | "incremental",
  "since_ref": "HEAD~1" | "main" | null,
  "paths": ["src/"] | null,
  "force": false
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `mode` | enum | `auto` — doubled-graph решает сам (default); `full` — полный reindex; `incremental` — только изменённое |
| `since_ref` | git ref | база для incremental (default: последний commit, где `.doubled-graph/cache/code-fingerprint.json` был актуален) |
| `paths` | list | ограничить анализ подпутями (default: весь репо) |
| `force` | bool | очистить кэши и CGC-БД перед анализом |

### 1.2 Output

```json
{
  "mode_used": "incremental",
  "duration_ms": 4321,
  "stats": {
    "files_processed": 17,
    "symbols_added": 42,
    "symbols_removed": 3,
    "symbols_updated": 11,
    "edges_added": 88,
    "edges_removed": 5
  },
  "warnings": [
    {"code": "HASKELL_PARSER_UNSTABLE", "file": "src/foo.hs", "detail": "…"}
  ],
  "meta": {"phase": "post_migration", "tool_version": "0.1.0-mvp", "timestamp_iso": "2026-04-18T10:22:04Z", "trace_id": "…"}
}
```

### 1.3 Mapping на CGC/grace-cli

| Шаг | Внутренний вызов |
|-----|-------------------|
| Валидация входов | Pydantic |
| Выбор mode=auto | если `.doubled-graph/cache/code-fingerprint.json` существует и git HEAD изменился — `incremental`, иначе `full` |
| `full` | `CGC.builder.add_repository_to_graph(repo_path, is_dependency=False)` |
| `incremental` | `git diff --name-status <since_ref> HEAD` → список файлов → `CGC.builder.delete_file_from_graph` + `CGC.builder.parse_file` + `CGC.builder.link_function_calls` / `link_inheritance` для каждого |
| Warnings (Haskell) | смотрим расширения в списке файлов, если есть `.hs` — добавляем warning |
| Финал | обновляем `.doubled-graph/cache/code-fingerprint.json` (git HEAD hash + file-list), пишем event в `logs/` |

### 1.4 Пример use-case из grace-marketplace

`doubled-graph init` ([SKILL.md](../extra/extra/research/grace-marketplace-main/skills/grace/grace-init/SKILL.md)) создаёт `docs/*.xml`. Сразу после этого методология требует `doubled-graph analyze --mode full`, чтобы computed graph стартовал с baseline.

---

## 2. `impact`

**Назначение:** blast-radius анализ символа. Для данного `target` (функция / класс / модуль / файл) — кто будет затронут, на каком уровне, какой risk level.

**Когда вызывает агент (methodology rule, см. CLAUDE.md):** **перед** правкой любого символа.

### 2.1 Input

```json
{
  "target": "validateUser",
  "direction": "upstream" | "downstream" | "both",
  "depth": 3,
  "include_tests": true,
  "scope": "full" | "module" | "file"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `target` | string | имя функции/класса или путь к файлу; если неоднозначно — ошибка `INVALID_INPUT` со списком кандидатов |
| `direction` | enum | `upstream` = кто вызывает; `downstream` = что вызывает; `both` |
| `depth` | int (1–10) | глубина обхода; default 3 |
| `include_tests` | bool | включать ли файлы в `tests/` / `__tests__/` / по паттерну verification |
| `scope` | enum | `full` (весь репо), `module` (только затронутые модули), `file` (только вызовы из того же файла) |

### 2.2 Output

```json
{
  "target_resolved": {
    "name": "validateUser",
    "file": "src/auth/validate.ts",
    "line": 42,
    "kind": "function",
    "module_id": "M-AUTH-VALIDATE"
  },
  "direct": [
    {"name": "loginHandler", "file": "src/routes/login.ts", "line": 17, "module_id": "M-ROUTES-LOGIN", "depth": 1}
  ],
  "transitive": [
    {"name": "App.handleRequest", "file": "src/app.ts", "line": 89, "module_id": "M-APP-CORE", "depth": 2}
  ],
  "affected_modules": [
    {"id": "M-ROUTES-LOGIN", "exports_changed": false, "crosslinks_to": ["M-AUTH-VALIDATE"]},
    {"id": "M-APP-CORE", "exports_changed": false, "crosslinks_to": ["M-ROUTES-LOGIN"]}
  ],
  "affected_verification": [
    {"id": "V-M-AUTH-VALIDATE-01", "kind": "unit-test"},
    {"id": "V-M-ROUTES-LOGIN-03", "kind": "integration-test"}
  ],
  "risk": {
    "level": "HIGH",
    "reasons": [
      "direct callers count = 4",
      "touches verification V-M-AUTH-VALIDATE-01 (unit-test)",
      "phase=post_migration — contract drift check required"
    ]
  },
  "meta": {"phase": "post_migration", "tool_version": "0.1.0-mvp", "timestamp_iso": "...", "trace_id": "..."}
}
```

**Risk-level правило (MVP):**
- `CRITICAL`: >10 direct callers ИЛИ target участвует в процессе, помеченном как `critical-path` в `docs/development-plan.xml`.
- `HIGH`: 4–10 direct callers ИЛИ затронута любая `V-M-*` запись.
- `MEDIUM`: 1–3 direct callers.
- `LOW`: нет direct callers (но есть transitive).
- `NONE`: символ изолирован.

### 2.3 Mapping

| Шаг | Внутренний вызов |
|-----|-------------------|
| Разрешить target | `CGC.finder.find_by_function_name(target, fuzzy_search=False)` → если > 1 match и `scope != file` — ошибка INVALID_INPUT с кандидатами |
| direct/transitive upstream | `CGC.finder.analyze_code_relationships(query_type="find_all_callers", target=target, repo_path=repo_path)` |
| direct/transitive downstream | `find_all_callees` |
| Модули для каждого файла | `doubled-graph module find --path <repo> "<file>"` + парсинг stdout |
| CrossLinks затронутых модулей | из `graphs/declared.py` (кэш `docs/knowledge-graph.xml`) |
| V-M-* записи | `doubled-graph module show <M-id> --with verification` для каждого затронутого модуля |
| Risk | чистая функция от counts + phase |

### 2.4 Пример use-case

Из CLAUDE.md текущего репо: «**MUST run impact analysis before editing any symbol.**» — это и есть applied-case `impact` в методологии doubled-graph.

---

## 3. `context`

**Назначение:** 360-view на символ. Объединяет computed (CGC) + declared (grace artifacts) + source-reading (doubled-graph file show).

**Когда вызывает агент:**
- Перед написанием нетривиального кода в функцию — понять, что он обязан соблюсти (контракт + вызовы + прошлые CHANGE_SUMMARY).
- `doubled-graph ask`, `doubled-graph fix` — когда нужно ответить на вопрос про конкретный символ.

### 3.1 Input

```json
{
  "name": "validateUser",
  "depth_callers": 2,
  "depth_callees": 2,
  "include_blocks": true,
  "include_history": false
}
```

### 3.2 Output

```json
{
  "symbol": {
    "name": "validateUser",
    "file": "src/auth/validate.ts",
    "line": 42,
    "kind": "function",
    "source": "export function validateUser(req: Request): User | null { … }",
    "docstring": "…"
  },
  "contract": {
    "source": "grace-file-show",
    "purpose": "…",
    "inputs": "…",
    "outputs": "…",
    "side_effects": "…",
    "links": ["M-AUTH-VALIDATE", "V-M-AUTH-VALIDATE-01"]
  },
  "module": {
    "id": "M-AUTH-VALIDATE",
    "purpose": "…",
    "exports": ["validateUser", "validateToken"],
    "crosslinks": ["M-AUTH-TOKENS", "M-ROUTES-LOGIN"]
  },
  "callers": [ /* как в impact.direct */ ],
  "callees": [ /* аналогично */ ],
  "blocks": [
    {"name": "DECODE_JWT", "line_start": 45, "line_end": 58, "source": "…"}
  ],
  "verification": [
    {"id": "V-M-AUTH-VALIDATE-01", "kind": "unit", "command": "pnpm test auth/validate", "markers": ["VALIDATE_SUCCESS", "VALIDATE_FAIL"]}
  ],
  "change_summary_last": {
    "date": "2026-04-12",
    "reason": "tightened JWT clock-skew tolerance",
    "author_kind": "ai"
  },
  "meta": {"phase": "...", "tool_version": "0.1.0-mvp", "...": "..."}
}
```

### 3.3 Mapping

| Шаг | Внутренний вызов |
|-----|-------------------|
| Symbol, source, docstring | `CGC.finder.find_by_function_name(name)` → берём свойства узла |
| Contract | `doubled-graph file show <file> --contracts --blocks` → извлекаем `START_CONTRACT: name` блок |
| Module | `doubled-graph module show <M-id>` |
| Callers/callees | как в `impact` |
| Blocks | те же, что из `doubled-graph file show --blocks`, но фильтр по line-range функции |
| Verification | `doubled-graph module show <M-id> --with verification` |
| change_summary_last | `doubled-graph file show <file>` (CHANGE_SUMMARY секция) + `git log -1 --format=%an%n%ae%n%s` для `author_kind` — если trailer `Co-Authored-By: Claude …` → `"ai"`, иначе `"human"` |

### 3.4 Статус в MVP

**Stub.** Возвращает `NOT_IMPLEMENTED_MVP` с детальным контрактом выше — чтобы агент и пользователь видели планируемую форму.

---

## 4. `detect_changes`

**Назначение:** центральная операция моста. Сравнить computed graph с declared graph и вернуть дрейф по типам.

**Когда вызывает агент (methodology rule):** **перед** коммитом, а также по `doubled-graph refresh` workflow.

### 4.1 Input

```json
{
  "scope": "staged" | "branch" | "all" | "compare",
  "base_ref": "main",
  "since_ref": "HEAD~1",
  "include_unchanged": false
}
```

| Поле | Описание |
|------|----------|
| `scope=staged` | только файлы в git staging area |
| `scope=branch` | изменения текущей ветки относительно `base_ref` |
| `scope=all` | полное сравнение computed vs declared (дорого) |
| `scope=compare` | между двумя ref'ами (`since_ref` → HEAD) |
| `include_unchanged` | возвращать ли модули без дрейфа (обычно нет) |

### 4.2 Output

```json
{
  "scope_used": "staged",
  "files_examined": ["src/auth/validate.ts"],
  "drift": {
    "code_without_module": [
      {"file": "src/new/feature.ts", "functions": ["newThing", "helper"], "reason": "no M-* in development-plan.xml matches this path"}
    ],
    "module_without_code": [
      {"module_id": "M-DEPRECATED-BILLING", "reason": "listed in development-plan.xml but no matching files in src/"}
    ],
    "contract_mismatch": [
      {
        "function": "validateUser",
        "file": "src/auth/validate.ts",
        "module_id": "M-AUTH-VALIDATE",
        "declared_inputs": "Request",
        "observed_signature": "(req: Request, opts?: Options) => User | null",
        "kind": "extra_param"
      }
    ],
    "stale_crosslinks": [
      {"from_module": "M-AUTH-VALIDATE", "to_module": "M-AUTH-TOKENS", "reason": "no CGC edge found between corresponding files"}
    ],
    "missing_verification": [
      {"module_id": "M-AUTH-VALIDATE", "reason": "code exists, module exists, но V-M-AUTH-VALIDATE-* записей нет"}
    ],
    "markup_missing": [
      {"file": "src/new/feature.ts", "missing": ["MODULE_CONTRACT", "MODULE_MAP"]}
    ]
  },
  "resolution_hint_by_phase": {
    "phase": "post_migration",
    "action": "artifacts = ground-truth. Для каждого дрейфа — спросить пользователя: new requirement | bug | not-know. Для scope=staged — блокировать commit до разрешения."
  },
  "meta": {"...": "..."}
}
```

### 4.3 Mapping

| Шаг | Внутренний вызов |
|-----|-------------------|
| `files_examined` | для `staged`: `git diff --name-only --cached`; для `branch`: `git diff --name-only <base_ref>...HEAD` |
| Computed side | выборка из CGC для этих файлов: функции/классы/экспорты |
| Declared side | `graphs/declared.py` парсит `docs/development-plan.xml` + `docs/knowledge-graph.xml` |
| `code_without_module` | функции в computed, у которых файл не покрыт ни одним M-* |
| `module_without_code` | M-* в declared, у которых нет ни одного живого файла |
| `contract_mismatch` | сравнение `declared_inputs/outputs` из `MODULE_CONTRACT` (через `doubled-graph file show --contracts`) с AST-сигнатурой (CGC свойства узла) |
| `stale_crosslinks` | CrossLink между M-A и M-B, но в CGC нет ни одного CALLS/IMPORTS между соответствующими файлами |
| `missing_verification` | M-* без V-M-* в `docs/verification-plan.xml` |
| `markup_missing` | `doubled-graph lint` на файле; извлекаем секцию «missing markers» |

### 4.4 Статус в MVP

**Stub.** Причина: пересечение — самая сложная часть facade, требует осторожной реализации и тестов на реальных фикстурах. В MVP оставляем контракт, но возвращаем `NOT_IMPLEMENTED_MVP`. Детальная реализация — отдельная задача после ревью Фазы 1.5 (возможно, Фаза 5).

### 4.5 Пример use-case

`doubled-graph refresh` ([SKILL.md](../extra/extra/research/grace-marketplace-main/skills/grace/grace-refresh/SKILL.md)) шаг 3 «Compare with shared artifacts» — ровно тот workflow, который `detect_changes` замещает одним вызовом.

---

## 5. Что НЕ входит в публичный набор

Не экспонируем как MCP-tool'ы (агент обращается к ним через grace CLI напрямую или через Bash):
- `doubled-graph lint` — сугубо валидатор разметки, не graph-операция.
- `doubled-graph module show` / `doubled-graph file show` — доступны через `context` опосредованно.
- `cgc cypher` raw — слишком низкоуровнево; если нужен — пользователь идёт в CGC MCP напрямую.

Потенциально добавить в v2:
- `rename(old, new, dry_run)` — по аналогии с GitNexus; требует glue CGC rename + `doubled-graph refactor` skill.
- `search(concept)` — semantic поиск по процессам; требует embedding layer.

Эти имена **зарезервированы**, чтобы не путаться при расширении.

---

## 6. Соответствие методологии

| Правило методологии | Какой tool реализует |
|---|---|
| «Perform impact analysis before editing» (CLAUDE.md) | `impact` |
| «Detect drift before commit» (§ 9) | `detect_changes` |
| «360-view symbol context» (`doubled-graph ask`, `doubled-graph fix`) | `context` |
| «Fresh index after commit» (hooks) | `analyze` |
| Режим `migration` vs `post_migration` | все 4 — через `meta.phase` + policy в risk/resolution |
