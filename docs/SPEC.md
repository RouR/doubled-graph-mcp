# doubled-graph — Technical Specification (v0.1 draft)

**Status:** Phase 1.5 draft (2026-04-18). Не релизный. Подлежит ревью пользователя.
**License:** MIT.
**Рабочее название:** `doubled-graph`. Финальное имя выберем перед публичным релизом.

---

## 1. Назначение

`doubled-graph` — тонкий **facade-MCP-сервер** методологии doubled-graph. Две публичные роли:

1. **Curated MCP-поверхность для ИИ-агента.** Вместо 14+ инструментов [CodeGraphContext MCP](../extra/extra/research/CodeGraphContext-main/) и N skills grace-marketplace — агент видит **4 доменных инструмента** (`analyze`, `impact`, `context`, `detect_changes`), описанных в терминах методологии, а не в терминах внутренней БД или AST.
2. **Мост между двумя графами.** Методология doubled-graph (§5.4 METHODOLOGY_DRAFT.md) различает:
   - **Declared graph** (декларативный, `docs/knowledge-graph.xml`, пишется ИИ по плану) — отражает замысел.
   - **Computed graph** (наблюдаемый, строится `codegraphcontext` из AST) — отражает фактическое состояние кода.

   Только `doubled-graph` пересекает оба: `detect_changes` и `impact` формулируются через это пересечение. CGC один этого не знает (не читает `docs/*.xml`), grace-marketplace один — не строит AST-граф.

`doubled-graph` **не заменяет** CGC и grace-marketplace. Он их **оркеструет**. Обе подсистемы подключаются как внешние зависимости, **не форкаются**. Обновления апстрима получаем автоматически через `pip`/`bun install`.

> **Альтернатива без `doubled-graph`** (см. `QUESTIONS_FOR_REVIEW.md Q-2`): команда может подключить CGC MCP напрямую + `grace` CLI и склеить их в промптах. Это работает, но:
> - агент видит 14+ инструментов и N skills — шире когнитивная нагрузка;
> - нет готового пересечения computed/declared → `detect_changes` приходится писать руками в промптах;
> - нет единой точки для политики режима `migration/post_migration` — она дублируется в каждом промпте.
>
> Методология doubled-graph **рекомендует** `doubled-graph`, но не запрещает альтернативу. Если альтернативу выбирают — это фиксируется в `AGENTS.md`, в блоке конфигурации.

---

## 2. Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│ IDE / Agent (Claude Code, Cursor, Codex, Continue, local-LLM)│
└──────────────┬──────────────────────────────────────────────┘
               │ MCP (stdio JSON-RPC, spec 2025-03-26)
               ▼
┌─────────────────────────────────────────────────────────────┐
│ doubled-graph MCP Server (Python)                           │
│ ─────────────────────────────────────                       │
│  Tools:  analyze │ impact │ context │ detect_changes        │
│  Policy: phase (migration/post_migration) из AGENTS.md      │
│  Storage: .doubled-graph/ (config, cache, logs)             │
└──────┬──────────────────────────┬────────────────┬──────────┘
       │                          │                │
       │ Python import            │ subprocess     │ filesystem read
       ▼                          ▼                ▼
┌──────────────┐  ┌────────────────────────┐  ┌────────────────┐
│ codegraph-   │  │ grace (Bun CLI)        │  │ docs/*.xml     │
│ context      │  │ - grace lint           │  │ knowledge-graph│
│ (pip)        │  │ - doubled-graph module show    │  │ development-   │
│ GraphBuilder │  │ - doubled-graph file show      │  │ plan, etc.     │
│ CodeFinder   │  │                        │  │                │
│ DBManager    │  │                        │  │ AGENTS.md      │
└──────┬───────┘  └────────────────────────┘  └────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ CGC backend DB: FalkorDB Lite (default Unix) | KùzuDB (Win)│
│ | Neo4j (remote) — выбор через CGC_RUNTIME_DB_TYPE          │
└─────────────────────────────────────────────────────────────┘
```

**Почему Python для facade:**
- CGC — Python-библиотека, самый прямой путь к `GraphBuilder` / `CodeFinder` — через import.
- Python MCP SDK (`mcp` package, Anthropic) зрелее, чем TS для server-стороны.
- `grace` CLI — отдельный Bun-бинарник, с ним общаемся через `subprocess` (стабильная граница).

**Почему не один бинарник Bun/TS:** тогда пришлось бы общаться с CGC по MCP-в-MCP, что добавляет сериализацию и лишнюю межпроцессную границу на hot-path `analyze` / `impact`.

---

## 3. Дерево репозитория

```
doubled-graph/  (корневая папка проекта)
├── docs/
│   ├── SPEC.md               ← этот файл
│   ├── TOOLS.md              ← спецификация 4 публичных MCP-tool'ов
│   └── HOOKS.md              ← git post-commit + Claude Code PostToolUse + prepare-commit-msg
├── LICENSE                   ← MIT
├── pyproject.toml            ← зависимости: mcp, codegraphcontext, pydantic
├── src/
│   └── doubled_graph/
│       ├── __init__.py
│       ├── __main__.py       ← `python -m doubled_graph` → MCP server
│       ├── server.py         ← MCPServer class, регистрация 4 tools
│       ├── config.py         ← чтение .doubled-graph/config.json + AGENTS.md phase
│       ├── tools/
│       │   ├── analyze.py
│       │   ├── impact.py
│       │   ├── context.py
│       │   └── detect_changes.py
│       ├── integrations/
│       │   ├── cgc.py        ← обёртка над codegraphcontext
│       │   └── grace_cli.py  ← subprocess-обёртка grace
│       ├── graphs/
│       │   ├── declared.py   ← парсер docs/knowledge-graph.xml
│       │   └── crossref.py   ← declared × computed (пересечение)
│       ├── policy/
│       │   └── phase.py      ← чтение `phase:` из AGENTS.md
│       └── storage/
│           └── paths.py      ← `.doubled-graph/` layout
└── tests/
    ├── fixtures/             ← мини-репо с docs/*.xml + code
    ├── test_analyze.py
    ├── test_impact.py
    └── test_detect_changes.py
```

---

## 4. Ответственность каждого слоя

### 4.1 `server.py` — MCP-endpoint
- Инициализирует транспорт stdio JSON-RPC (MCP spec).
- Регистрирует 4 tools (см. `TOOLS.md`).
- Каждый вызов:
  1. Читает `phase` из `AGENTS.md` (policy/phase.py).
  2. Диспетчеризует в соответствующий `tools/*.py`.
  3. Оборачивает результат в MCP response.
- **Не содержит бизнес-логики.** Всё в tools/.

### 4.2 `tools/*.py` — сами инструменты
- Каждый — single-responsibility модуль.
- Работают через `integrations/` (не дёргают CGC напрямую).
- Возвращают `pydantic`-модели (строго типизированные).

### 4.3 `integrations/cgc.py` — обёртка над CGC
```python
class CGC:
    def __init__(self, repo_path: Path, db_manager: DatabaseManager):
        self.builder = GraphBuilder(db_manager)
        self.finder = CodeFinder(db_manager)

    def analyze_full(self) -> AnalyzeResult: ...
    def analyze_incremental(self, changed_files: list[Path]) -> AnalyzeResult: ...
    def find_callers(self, target: str, depth: int) -> list[Callsite]: ...
    def find_callees(self, target: str, depth: int) -> list[Callsite]: ...
    def get_cypher(self, query: str) -> list[dict]: ...
```
- Вся CGC-специфика (выбор backend, Cypher-диалекты, FalkorDB vs Neo4j) — здесь.

### 4.4 `integrations/grace_cli.py` — обёртка над grace CLI
```python
class GraceCLI:
    def lint(self, root: Path) -> LintResult: ...
    def module_show(self, id_or_path: str, with_verification: bool = False) -> ModuleRecord: ...
    def file_show(self, path: Path, contracts: bool = False, blocks: bool = False) -> FileRecord: ...
```
- subprocess-вызов `grace <cmd>`, парсинг stdout/stderr.
- Если `grace` не установлен в $PATH — понятная ошибка: «Установите `@osovv/grace-cli` → `bun add -g @osovv/grace-cli`». **Не пытаться подменить вручную.**

### 4.5 `graphs/declared.py` — парсер declared-графа
- Читает `docs/knowledge-graph.xml`, `docs/development-plan.xml`, `docs/verification-plan.xml`.
- Строит in-memory-представление: `DeclaredGraph { modules: {M-id: Module}, cross_links: [CrossLink], verification: {V-M-id: VerificationEntry} }`.
- Не зависит от CGC. Чистый парсер XML.

### 4.6 `graphs/crossref.py` — пересечение
- Вход: `DeclaredGraph` + результаты CGC (список файлов, символов).
- Выход: `Crossref { matches: [...], declared_missing: [...], code_orphaned: [...], stale_links: [...] }`.
- Это **главная ценность** `doubled-graph`. Детали алгоритма — в `TOOLS.md § detect_changes`.

### 4.7 `policy/phase.py`
- Читает `AGENTS.md`, ищет блок `<!-- doubled-graph:phase:start --> ... <!-- doubled-graph:phase:end -->`.
- Возвращает `"migration" | "post_migration"`. Default: `"post_migration"`.
- Используется tools для выбора политики разрешения конфликтов.

### 4.8 `storage/paths.py` — layout `.doubled-graph/`
```
.doubled-graph/
├── config.json               ← backend, paths, repo-name
├── cache/
│   ├── declared.json         ← [planned] last parsed docs/*.xml — запишется при первом context/detect_changes
│   ├── crossref.json         ← [planned] last crossref snapshot — запишется при первом detect_changes
│   └── code-fingerprint.json ← file-path → last-commit-hash (для incremental analyze) — запишется при первом `analyze` с реальным CGC-вызовом
├── drafts/                   ← scratchpad'ы многошаговых промптов (interview, discover, plan, markup-progress, drift-session-*)
│   └── _archive/<дата>/      ← завершённые drafts переносятся сюда по завершении процесса (audit trail)
└── logs/
    └── 2026-04-18.jsonl      ← структурированные события (analyze/impact/skill-gateway) — **уже пишется в MVP**
```

В MVP каталог `cache/` создаётся, но заполнение `declared.json` / `crossref.json` откладывается до реализации `context` / `detect_changes`. `logs/` заполняется сразу после первого `analyze`.

**`drafts/`** — операционный паттерн «externalize state» (см. `methodology/principles.md § Операционный паттерн`). Промпты, которые собирают ответы интервью / результаты discovery / черновик плана / статус разметки — пишут append-only в файл в этой директории, а не держат контекст в chat history. Политика архивации: по завершении процесса переместить в `_archive/<ISO-дата>/`. В git по умолчанию `drafts/` коммитится (resume-ability), `_archive/` можно gitignore'ить по вкусу команды.

Сам CGC пишет в свой backend (FalkorDB Lite по пути `~/.codegraphcontext/` или где он решит). `.doubled-graph/` — **только** для наших кэшей и логов. Мы не дублируем CGC-граф.

---

## 5. Конфигурация

### 5.1 `.doubled-graph/config.json`

```json
{
  "version": "1",
  "repo_name": "grace",
  "repo_path": "/absolute/path/to/repo",
  "cgc": {
    "backend": "auto",
    "backend_overrides": {}
  },
  "grace_cli_command": "grace",
  "phase_source": "AGENTS.md",
  "phase_default": "post_migration"
}
```

- `cgc.backend`: `"auto"` (CGC сам выбирает), `"falkordb-lite"`, `"kuzu"`, `"neo4j"`.
- `grace_cli_command`: по умолчанию `grace`; можно переопределить (напр., для `bunx grace`).
- `phase_source`: пока единственное допустимое значение `"AGENTS.md"`. Заложено поле для будущей альтернативы.

### 5.2 `AGENTS.md` — phase-блок (см. METHODOLOGY_DRAFT § 9.3)

```markdown
<!-- doubled-graph:phase:start -->
## doubled-graph phase
phase: post_migration
updated: 2026-04-18
<!-- doubled-graph:phase:end -->
```

### 5.3 MCP-регистрация у клиента

**Claude Code** (`~/.claude/config.json` или `.mcp.json` в репо):
```json
{
  "mcpServers": {
    "doubled-graph": {
      "command": "python",
      "args": ["-m", "doubled_graph"],
      "cwd": "/absolute/path/to/repo"
    }
  }
}
```

**Cursor, Codex, Continue, Windsurf** — аналогично, детали в `methodology/runtime-adapters/*.md` (Фаза 2).

---

## 6. Жизненный цикл вызова

Пример: агент вызывает `impact(target="validateUser", direction="upstream")`.

```
1. MCP client → stdio → doubled-graph server
2. server.py: routes to tools/impact.py
3. policy/phase.py: читает AGENTS.md → phase="post_migration"
4. tools/impact.py:
   a. integrations/cgc.py: find_callers(validateUser, depth=3)
      → список callsites из computed graph
   b. integrations/grace_cli.py: doubled-graph module show (для каждого затронутого файла)
      → модули M-xxx, к которым относятся callsites
   c. graphs/declared.py: читает docs/knowledge-graph.xml
      → CrossLinks для затронутых модулей
   d. graphs/crossref.py: соединяет (a) ∪ (b) ∪ (c)
      → ImpactReport { direct_callers, affected_modules, affected_flows, risk }
5. Сериализация в pydantic → MCP response
6. Запись в logs/ как structured event (для LDD)
```

Политика phase влияет на интерпретацию риска:
- `migration`: risk понижается, если в declared-графе модуля ещё нет (код — ground-truth, артефакты догоняют).
- `post_migration`: risk повышается, если затронуты модули с V-M-* записями (ломает verification).

---

## 7. MVP-скоп (Фаза 1.5)

Легенда: `[x]` — готово и протестировано; `[~]` — каркас есть, реальный вызов стаббирован (см. QUESTIONS_FOR_REVIEW § C-1); `[ ]` — stub с `NOT_IMPLEMENTED_MVP`.

- [x] Scaffold пакета (pyproject, `__main__`, cli, server.py, storage, policy, graphs skeleton, hooks_installer).
- [x] 12 smoke-тестов (phase parsing, declared-graph tolerant parser, hooks installer dry-run + real, CGC-unavailable fallback path, CLI status).
- [~] `analyze` — типизированный contract + CGC lazy probe + git-diff + логирование. Реальный вызов `GraphBuilder.add_repository_to_graph` помечен TODO[integration], возвращается warning `MVP_STUB` пока не прогнан на живом CGC.
- [~] `impact` — типизированный contract + risk-классификатор (частичный: без чтения `critical-path` из XML, см. QUESTIONS_FOR_REVIEW § C-6) + CGC lazy probe. Реальные `find_callers/find_callees` — TODO[integration].
- [ ] `context` — **stub** (возвращает `NOT_IMPLEMENTED_MVP` с ссылкой на TOOLS § 3).
- [ ] `detect_changes` — **stub** (возвращает `NOT_IMPLEMENTED_MVP` с ссылкой на TOOLS § 4). `.doubled-graph/cache/crossref.json` из § 4.8 **не пишется** до появления реального `detect_changes` (cache path зарезервирован, но hook не срабатывает).

Тест — сам репозиторий Grace (есть `AGENTS.md`, есть сам код для CGC-анализа, нет полного набора `docs/*.xml` — значит часть детектов будет «declared empty»).

---

## 8. Границы ответственности

**doubled-graph делает:**
- MCP transport + 4 tool dispatch.
- Парсинг `docs/*.xml` declared-графа.
- Пересечение computed × declared.
- Чтение phase из `AGENTS.md`.
- Структурированные логи событий.

**doubled-graph НЕ делает:**
- AST-парсинг (это CGC).
- Построение/обновление графа в БД (это CGC).
- Правка кода (это skill `doubled-graph execute` и задача ИИ-агента).
- Правка `docs/*.xml` (это skills `doubled-graph plan` / `doubled-graph refresh`).
- git-операции (это hooks, см. `HOOKS.md`).

**Когда doubled-graph делегирует:**
- «Пересчитай граф» → `CGC.add_repository_to_graph` (full) или `CGC.watcher.handle_modification` (incremental).
- «Проверь целостность XML-якорей» → `doubled-graph lint`.
- «Покажи module record» → `doubled-graph module show`.
- «Покажи contracts в файле» → `doubled-graph file show --contracts --blocks`.

---

## 9. Риски и ограничения (знаемые)

1. **Зависимость от CGC API-стабильности.** Если CGC меняет сигнатуры `GraphBuilder`/`CodeFinder` — у нас ломается `integrations/cgc.py`. Митигация: pin версию в `pyproject.toml`, интеграционные тесты на фикстурах.
2. **Зависимость от grace CLI ABI.** `doubled-graph module show` stdout-формат не зафиксирован как публичный API в grace-marketplace. Риск: формат меняется → парсинг ломается. Митигация: тесты на фикстурах, pin версии grace-cli.
3. **Windows.** MCP-серверы на stdio работают, но CGC по умолчанию выбирает KùzuDB — он кроссплатформен, но имеет синтаксические отличия Cypher (см. сводку из Фазы 0.2). Влияет на `integrations/cgc.py` — потребуется либо абстракция, либо явный target-backend. MVP: поддерживаем только Unix (FalkorDB Lite), Windows — feature для Фазы 5.
4. **Нестабильный Haskell-парсер CGC.** Помечаем как known-issue в `detect_changes`: если в репо есть `.hs`-файлы — doubled-graph предупредит и сделает best-effort.
5. **Голубой шум:** наши кэши в `.doubled-graph/cache/` могут расходиться с реальным состоянием CGC-БД, если пользователь дёрнул `cgc clean` руками. Митигация: `doubled-graph analyze --force` — полный re-index + очистка кэшей.
6. **PolyForm NC-загрязнение.** `doubled-graph` **не импортирует** GitNexus и не копирует из него код. Проверяем это commit-time tests: `grep -r "gitnexus" src/` должен быть пуст.

---

## 10. Не-цели (out of scope)

- Semantic search по коду (нет embeddings на старте).
- Web-UI (CGC web-UI достаточен; пользователи, которым нужен визуал, идут через него или через `gitnexus://` ресурсы Claude Code).
- Замена `grace` CLI (мы надстройка, не замена).
- Поддержка бэкендов кроме CGC (SCIP / LSIF / tree-sitter напрямую) — возможно в v2.

---

## 11. Критерий готовности MVP (Фаза 1.5)

1. `pip install -e .` работает.
2. `python -m doubled_graph` запускается как MCP-сервер и отдаёт список tools.
3. `analyze` на репо Grace проходит без ошибок и пишет event в `.doubled-graph/logs/`.
4. `impact` на существующем символе (например, `MCPServer` из research/) возвращает непустой список callers.
5. `context` и `detect_changes` явно отвечают "not-implemented-in-mvp" — не падают.
6. Тесты фикстур `tests/` проходят.
7. В `QUESTIONS_FOR_REVIEW.md` перечислены все слабые места реализации, которые self-review не проверяет.

Что **не** входит в MVP (остаётся на вас в Фазе 5):
- Реальный запуск в Claude Code и проверка руками.
- Сравнение поведения с CGC MCP напрямую — subjective call.
- Проверка на разнообразных языках (кроме Python).
