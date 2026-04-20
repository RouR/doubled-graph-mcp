# doubled-graph — deep dive

**Для:** разработчиков, которые уже прочитали getting-started и хотят понимать методологию глубже — не «как применить», а «почему так устроено».

---

## Почему GRACE и что мы к нему добавляем

### Исходная GRACE (osovv)

GRACE — *Graph-RAG Anchored Code Engineering*. Публичная методология на GitHub (`osovv/grace-marketplace`, MIT, v3.7.0 на apr 2026). Ключевые идеи:

1. **Три XML-артефакта до кода**: `requirements.xml`, `technology.xml`, `development-plan.xml`. Каждый — approval-gate человеком.
2. **Семантическая разметка кода**: `MODULE_CONTRACT`, `CONTRACT: fn`, `BLOCK_*`, `CHANGE_SUMMARY`. Три уровня парных якорей.
3. **Log-Driven Development (LDD)**: каждое log-событие привязано к якорю, поля `anchor`, `module`, `requirement`.
4. **Сквозная прослеживаемость**: `UC-* → M-* → V-M-* → якорь → log`.
5. **Операционные скиллы** для Claude Code: `doubled-graph init`, `doubled-graph plan`, `doubled-graph execute`, `doubled-graph verification`, `doubled-graph refresh`, `doubled-graph fix`, `doubled-graph ask`, `doubled-graph health`, `doubled-graph reviewer`, `doubled-graph multiagent-execute`, `doubled-graph refactor` + CLI `grace`.

**Что GRACE не решает:**

- Применение к **legacy-коду** (предполагается, что ИИ пишет с чистого листа).
- **Дрейф**: как жить, когда код и артефакты расходятся.
- **Tool-agnostic** за пределами Claude Code / Cursor.
- **Локальные модели** (Qwen, DeepSeek, …) — их ограничения upstream не учитывает.
- Граф-анализ кода: `knowledge-graph.xml` у GRACE — декларативный, не извлекается из AST.

### Что добавляет doubled-graph

Три pillar'а:

1. **Сценарий миграции legacy** — `prompts/migrate-existing-project/*` + политика, что в режиме `migration` код — ground-truth. См. [methodology/workflow.md § Сценарий 2](../methodology/workflow.md) и [drift-and-priority.md](../methodology/drift-and-priority.md).
2. **Два графа и `detect_changes`** — computed graph (CGC) + declared graph (xml), пересечение выявляет дрейф. Ядро — `doubled-graph` facade.
3. **Tool-agnostic runtime-слой** — адаптеры под Cursor / Codex / Continue / Windsurf / local-LLM клиенты, не только Claude Code.

Остальные дополнения — тонкие (phase-блок в `AGENTS.md`, `DRIFT.md`, `doubled-graph phase set`) — служат трём pillar'ам.

---

## Архитектурные решения и их обоснования

### Почему Python для doubled-graph, а не Bun

`grace-cli` — Bun/TypeScript. Логично было бы сделать и doubled-graph на Bun. Но:

- **CGC — Python-библиотека.** Через Bun — только через CGC MCP (stdio-in-stdio). Это добавляет сериализацию и лишний межпроцессный хоп на hot-path `analyze`/`impact`.
- Python MCP SDK (Anthropic `mcp` package) зрелее для server-side на apr 2026.
- Граница с `grace-cli` — subprocess, уже граница, ещё одна не усугубляет.

Trade-off: два runtime'а в стеке (Python + Bun). Принят осознанно.

### Почему 4 tool'а, а не 14

CGC MCP экспонирует 14+ tool'ов (`add_code_to_graph`, `watch_directory`, `find_code`, `analyze_code_relationships`, `execute_cypher_query`, …). Подключить напрямую — работает, но:

- **Когнитивная нагрузка на ИИ.** 14 tools + N skills grace — агент чаще ошибается в выборе. Особенно локальные модели.
- **Нет единой точки для phase-policy.** Правила `migration` vs `post_migration` пришлось бы зашивать в каждый промпт.
- **`detect_changes` не существует в CGC** — это cross-graph операция. Только doubled-graph может её сделать, потому что только он читает `docs/*.xml`.

Trade-off: ещё одна зависимость для поддержки. Mitigation — тонкий слой (4 tool'а, ~600 LOC без тестов).

### Почему `AGENTS.md` для phase-блока, а не git tag / docs/phase.xml

- `AGENTS.md` уже создаётся `doubled-graph init`, ИИ читает его первым → нулевая стоимость интеграции.
- Версионируется через git → PR-review видит смену режима в diff.
- Блок в HTML-комментариях → для человека это прозрачная часть файла; для инструмента — строгий синтаксис.
- Git tag — не на каждом коммите, ИИ их не видит при обычной работе.
- `docs/phase.xml` отдельным файлом — лишняя сущность для одного поля.

### Почему OpenTelemetry GenAI не обязателен

BlackboxBook гл. 17 продвигает OTel GenAI как обязательный стандарт. Мы решили (2026-04-17) не делать его mandatory:

- Сэкономленный бюджет сложности — наш структурированный JSON-log с обязательными полями `anchor`/`module`/`requirement` даёт ту же наблюдаемость без зависимости от специфичной vendor'ы.
- Privacy-риски OTel GenAI (промпты в spans по умолчанию) — требуют custom маскирования; простой JSON-лог контролируется полностью.
- OTel GenAI semantic conventions на apr 2026 всё ещё **mixed** (часть experimental). Привязываться к нестабильному стандарту — риск.

Рекомендация: OTel GenAI как layer over JSON-logs — легитимно для тех, кому нужен vendor-ekosystem observability.

### Почему отказались от профилей глубины (Lite/Standard/Full и M/S/L)

Ранние черновики doubled-graph имели три профиля с разным набором артефактов. Поздние — три профиля глубины в entry-промпте. **Решено отказаться от обоих** (2026-04-18):

- **Upstream grace-marketplace v3.3.0 сам убрал** Lite/Standard/Full. Maintainer: «опциональность плодит баги». Мы не идём против upstream.
- **Инструменты поддерживают одну форму.** `doubled-graph detect_changes` зависит от `critical-path` и `CrossLinks`. «Облегчённый» проект без них не даёт detect_changes работать — методология ломается тихо.
- **«Promp-обёртка» тоже плодит неявные варианты.** Разные пользователи понимают одну и ту же «M»-шкалу по-разному → команда получает несогласованные репозитории.
- **Экономия на малом проекте мизерная.** На 500 LOC полный набор артефактов занимает 15 мин, а не 5. В обмен — предсказуемость на дистанции.

Единая глубина = единая методология. См. [methodology/auto-scaling.md](../methodology/auto-scaling.md).

---

## Компоненты в деталях

### doubled-graph

Facade-MCP, 4 инструмента: `analyze`, `impact`, `context`, `detect_changes`. Детали:

- [doubled-graph/SPEC.md](../docs/SPEC.md) — архитектура.
- [doubled-graph/TOOLS.md](../docs/TOOLS.md) — contract каждого tool'а.
- [doubled-graph/HOOKS.md](../docs/HOOKS.md) — git + Claude Code PostToolUse + optional prepare-commit-msg.

### grace-marketplace

Внешняя зависимость. Используем без изменений:
- 14 skills для Claude Code;
- CLI `grace` (лint, module show, file show).

См. [methodology/tools.md § 1](../methodology/tools.md).

### CodeGraphContext (CGC)

Внешняя зависимость, MIT, AST-парсинг tree-sitter для 19 языков. Используем как Python-библиотеку, не через его MCP (см. «Почему 4 tool'а, а не 14»).

Известные ограничения:
- Haskell-парсер unstable (помечено в upstream source);
- FalkorDB Lite требует Python 3.12+;
- Windows Neo4j driver 6.x имеет известный баг.

---

## Политика дрейфа — ядро методологии

Самая ценная концепция doubled-graph. Подробно — в [drift-and-priority.md](../methodology/drift-and-priority.md). Краткая модель:

```
           ┌──────────────┐          ┌──────────────┐
           │ docs/*.xml   │          │ AST код      │
           │ (declared)   │          │ (computed)   │
           └──────┬───────┘          └──────┬───────┘
                  │                         │
                  │ doubled-graph.detect_changes()
                  │                         │
                  └───────┬─────────────────┘
                          │
                  ┌───────▼────────┐
                  │ drift report   │
                  └───────┬────────┘
                          │
                  ┌───────▼────────┐
                  │ AGENTS.md      │
                  │ phase field    │
                  └───────┬────────┘
                          │
                 phase?   │
                 ┌────────┴────────┐
                 │                 │
          migration          post_migration
                 │                 │
                 ▼                 ▼
          грейс-refresh      ask user:
          (артефакт под      new req? | bug?
           код)              | not-know?
```

Two modes — две политики. Переключение — явный шаг через `doubled-graph phase set ...`.

---

## Sub-agent orchestration

[grace-multiagent-execute](../extra/extra/research/grace-marketplace-main/skills/grace/grace-multiagent-execute/) даёт три профиля:
- `safe`: approval перед каждой волной;
- `balanced`: один approval up-front;
- `fast`: approval up-front + scoped reviewer only on blockers.

Правило doubled-graph: только **один** worker пишет в **один** модуль за раунд. Controller сериализует при пересечениях.

См. [approval-checkpoints.md § 2](../methodology/approval-checkpoints.md).

---

## Что НЕ покрыто методологией

- **Дизайн UI/UX.** Методология о коде, не о продукте.
- **Выбор бизнес-модели.** Принцип 1 говорит «замысел первичен», но замысел формулирует человек.
- **Security-аудит на уровне инфраструктуры.** Якоря и markers помогают ставить alerts, но не заменяют pentest.
- **Ручные правки в production.** Если кто-то SSH'нулся на prod и правит код — это вне методологии. Дисциплина — в процессе деплоя.
- **Zero-downtime refactoring на 10M LOC.** Методология работает на таком масштабе, но операционка refactor'а — это другой уровень процессов.

---

## История решений

Фиксируется в [PLAN.md § Фаза 1](../PLAN.md), [QUESTIONS.md](../QUESTIONS.md), [METHODOLOGY_DRAFT.md § 16 Changelog](../METHODOLOGY_DRAFT.md).

Важные повороты:
- 2026-04-17: отказ от GitNexus в пользу собственного `doubled-graph` (PolyForm NC licensing).
- 2026-04-17: local-first фокус вместо frontier-first.
- 2026-04-17: отказ от OpenTelemetry GenAI как обязательного.
- 2026-04-17: отказ от Lite/Standard/Full профилей (первая итерация).
- 2026-04-18: отказ также от промпт-профилей глубины M/S/L — единая максимальная глубина для всех проектов.
- 2026-04-18: финализирован phase-блок в `AGENTS.md` (было — вариант «выбирается в Фазе 2»).

---

## Что дальше

- [for-humans/FAQ.md](FAQ.md) — частые вопросы и edge cases.
- [for-humans/getting-started.md](getting-started.md) — если хочешь попробовать руками.
- [QUESTIONS_FOR_REVIEW.md](../QUESTIONS_FOR_REVIEW.md) — открытые вопросы к ревью (Phase 5).
