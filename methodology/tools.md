# Инструменты: gateway-архитектура

Методология **не работает** без обоих. Это — precondition, не рекомендация (см. `README.md`).

**Ключевой принцип: `doubled-graph` — единственный gateway.** Пользователь и ИИ-агент всегда взаимодействуют с методологией через команды `doubled-graph <…>`. Наш инструмент внутри себя обращается к CodeGraphContext (Python-библиотека, AST-анализ) и к upstream `grace` CLI / skills (артефакты и lint). Прямой вызов `grace <…>` в промптах методологии — анти-паттерн: пользователь должен видеть одно имя.

---

## 1. doubled-graph — gateway (наш инструмент)

- **Автор:** этот репозиторий. MIT.
- **Роль:** единственная точка входа в методологию. Тонкий MCP-facade + CLI. Оркеструет CGC и grace-marketplace.
- **Исходник:** `../docs/SPEC.md`, `../docs/TOOLS.md`, `../docs/HOOKS.md`.

### Публичный периметр (что методология разрешает вызывать)

**Операции над computed × declared графом** (родные, без upstream):

| Команда | MCP-tool | Назначение |
|---|---|---|
| `doubled-graph analyze [--mode ...]` | `analyze` | индексировать/обновить computed graph через CGC |
| `doubled-graph impact <target>` | `impact` | blast-radius перед правкой (mandatory-gate) |
| `doubled-graph context <name>` | `context` | 360-view на символ (stub в MVP) |
| `doubled-graph detect-changes` | `detect_changes` | drift computed×declared (stub в MVP) |

**Gateway-обёртки над upstream `grace` CLI** (прозрачно проксируют в subprocess):

| Команда | MCP-tool | Проксирует в |
|---|---|---|
| `doubled-graph lint` | `lint` | `grace lint` — валидация якорей и ссылок |
| `doubled-graph module show <id>` | `module_show` | `grace module show` |
| `doubled-graph module find <q>` | `module_find` | `grace module find` |
| `doubled-graph file show <path>` | `file_show` | `grace file show` — MODULE_CONTRACT/BLOCK_*/CHANGE_SUMMARY |

**Gateway для upstream-skills** (не CLI, директива агенту): skills grace-marketplace — это markdown-инструкции для агента в IDE, не subprocess. Каждая команда ниже логирует intent в `.doubled-graph/logs/` и возвращает JSON-директиву `delegated_to: upstream-skill:grace-X`, по которой агент триггерит skill через IDE skill system.

| Команда | Проксирует в upstream-skill |
|---|---|
| `doubled-graph init` | `grace-init` — bootstrap docs/*.xml + AGENTS.md |
| `doubled-graph plan` | `grace-plan` — план + 2 approval-gates |
| `doubled-graph execute` | `grace-execute` — sequential с approval-gate на Step 1 |
| `doubled-graph multiagent-execute --profile` | `grace-multiagent-execute` — parallel waves |
| `doubled-graph verification` | `grace-verification` — тесты + markers |
| `doubled-graph reviewer` | `grace-reviewer` — scoped/wave/full-integrity review |
| `doubled-graph refresh --scope` | `grace-refresh` — sync docs/*.xml с кодом |
| `doubled-graph fix` | `grace-fix` — debug + CHANGE_SUMMARY |
| `doubled-graph ask` | `grace-ask` — grounded Q&A |
| `doubled-graph health` | `grace-status` — health overview |
| `doubled-graph refactor` | `grace-refactor` — rename/move/split/merge |

**Управление методологией:**

| Команда | Назначение |
|---|---|
| `doubled-graph phase get` | прочитать текущий phase из `AGENTS.md` |
| `doubled-graph phase set <val> [--reason "..."]` | переключить phase (atomic rewrite `AGENTS.md` phase-блока) |
| `doubled-graph init-hooks [--all]` | установить git/Claude Code hooks |
| `doubled-graph status` | диагностика: config + phase + freshness |

### Почему единый gateway

1. **Когнитивная нагрузка.** Агент видит один namespace (`doubled-graph.*`). Альтернатива — смесь `grace lint`, `grace-refresh` (skill), `doubled-graph analyze` (наш tool) — путает даже frontier-модели, локальные вообще ломаются.
2. **Policy enforcement.** `phase` (migration/post_migration) читается **один раз** в doubled-graph, влияет на risk-level в `impact`, правила в `detect_changes` и поведение `refresh`. Если прямые вызовы `grace-*` — policy обходит.
3. **Логирование.** Каждый вызов через gateway пишет event в `.doubled-graph/logs/`. Это — основа для audit trail, postmortems и `detect_changes` recall.
4. **Swap-ability.** Если upstream `grace` CLI поменяет флаги — меняем одну строку в `integrations/grace_cli.py`, не трогая 19 промптов.

---

## 2. grace-marketplace (upstream, не наш)

- **Автор:** osovv. GitHub: `osovv/grace-marketplace`. MIT.
- **Версия** на момент написания методологии: v3.7.0 (апрель 2026, сверять актуальность).
- **Что даёт:**
  - 14 **skills** для Claude Code (агентные процедуры, не CLI).
  - CLI `grace` на Bun — `lint`, `module show/find`, `file show`.

**Как мы к ним обращаемся — через gateway:**
- **Skills** (`grace-init`, `grace-plan`, `grace-execute`, `grace-multiagent-execute`, `grace-verification`, `grace-reviewer`, `grace-refresh`, `grace-fix`, `grace-ask`, `grace-status`, `grace-refactor`) — **агент НЕ триггерит их напрямую**. Вместо этого вызывает gateway: `doubled-graph init`, `doubled-graph plan`, … (маппинг — в §1). Gateway логирует intent и возвращает структурированную директиву, по которой агент активирует upstream-skill через IDE skill system. `grace-explainer`, `grace-cli`, `grace-setup-subagents` — вспомогательные upstream-skills, методология их не использует в основном workflow.
- **CLI `grace`** — **агент НЕ вызывает напрямую**. Все вызовы идут через `doubled-graph lint / module / file` gateway.

**Что это даёт:** один namespace `doubled-graph.*` в промптах, единая точка логирования (`.doubled-graph/logs/`), возможность enforcement'а policy (phase, risk-level) до фактического запуска upstream-skill или CLI.

**Подключение (для Claude Code):**
```bash
claude --skills github:osovv/grace-marketplace
```

Для Cursor / Codex / etc — skills копируются в runtime-специфичные места, детали в `runtime-adapters/*.md`.

---

## 3. CodeGraphContext — внешняя зависимость, не трогаем

- **Автор:** внешний, MIT.
- **Что используем:** Python-библиотека (`GraphBuilder`, `CodeFinder`, `DatabaseManager`). Импортируется в `src/doubled_graph/integrations/cgc.py`.
- **Что НЕ используем:** MCP-сервер CGC (`cgc mcp start`) — чтобы агент не видел 14 tool'ов.
- **Поддержка 19 языков** (Python, JS, TS, Go, Java, C/C++/C#, Rust, Ruby, PHP, Kotlin, Scala, Swift, Dart, Elixir, Perl, Haskell).
- **Backends:** FalkorDB Lite (Unix default), KùzuDB (Windows/fallback), Neo4j (remote). Выбор автоматический, переопределяется `CGC_RUNTIME_DB_TYPE`.

Известные ограничения CGC — см. `../QUESTIONS_FOR_REVIEW.md § B` (верификация на Фазе 5):
- Haskell-парсер помечен как unstable в исходнике.
- FalkorDB Lite требует Python 3.12+.
- Windows Neo4j driver 6.x имеет баги — workaround `pip install "neo4j<6"`.

---

## 4. BlackboxBook — источник обоснований, не процесс

Используется как **ссылочный материал**, не как source-of-truth:

- гл. 7 (семантическая разметка) — обоснование для принципа 3.
- гл. 9 (декомпозиция) — обоснование для принципа 1.
- гл. 13 (LDD + антигаллюцинационный контур) — обоснование для принципов 7 и 8.
- гл. 14 (eval-дисциплина) — `approval-checkpoints.md § 4`.
- гл. 17 (OTel GenAI) — **не** применяем как обязательное (см. memory `project_otel_dropped.md`).

Главы 5 и 24 — не используются (спекулятивные места).

---

## 5. GitNexus — почему не используется

GitNexus — граф-анализатор кода, функционально близкий к CGC. На вид — удобнее (больше tools, richer MCP surface). **Лицензия:** PolyForm Noncommercial.

**Решение 2026-04-17:** исключён. PolyForm NC запрещает коммерческое использование; методология, претендующая на публичную публикацию и применимость в enterprise, не может опираться на NC-лицензированные зависимости. Это не техническое решение, а лицензионное.

**Что заменяет:** CodeGraphContext (MIT) + наш `doubled-graph` (MIT). Не даёт всех фич GitNexus (например, embeddings и cluster detection по Leiden), но закрывает базовые потребности методологии.

`doubled-graph` не импортирует ни строки кода из GitNexus. Проверяется commit-time test: `grep -r "gitnexus" src/ | wc -l` == 0.

---

## 6. Взаимодействие инструментов — картина целиком

```
                   ┌─────────────┐
                   │ Пользователь│
                   └──────┬──────┘
                          │
                   IDE (с MCP+tools)
                          │
         ┌────────────────┴────────────────┐
         │                                 │
    [ via skills ]                  [ via MCP ]
         │                                 │
    grace skills                    doubled-graph MCP
    (inline в IDE)                  (4 tools: analyze,
         │                           impact, context,
         │                           detect_changes)
         │                                 │
         ▼                                 ▼
    CLI `grace`                    CGC (Python lib)
    (валидация,                    + grace CLI subprocess
    navigation)                           │
                                          ▼
                                  .doubled-graph/ logs
                                  CGC DB (FalkorDB/Kùzu/Neo4j)
```

- **grace skills** — agent-level расширения поведения в IDE.
- **doubled-graph MCP** — agent видит 4 tool'а.
- **grace CLI** — dialected text-UI, инструмент для человека и hook'ов; doubled-graph шеллит его для `module show` / `file show` / `lint`.
- **CGC backend** — хранилище computed graph; пользователь обычно не трогает.

---

## 7. Установка одной командой

`for-humans/getting-started.md` (Phase 4) будет содержать финальную команду. Ожидаемая форма (черновик):

```bash
# Python tooling
pip install doubled-graph

# Bun tooling
bun add -g @osovv/grace-cli

# hooks
doubled-graph init-hooks --all
```

Отдельно для Claude Code — настройка MCP-сервера в `~/.claude/config.json`. Пример — `runtime-adapters/claude-code.md`.
