# 01 — Discover

**Роль ИИ:** понять, что за проект, без догадок. Только факты.

---

## Externalize state

Discover накапливает метрики, список файлов, hotspots, найденные docs, тесты, infra — легко 8+ секций. К финальному саммари на шаге 8 локальная модель забудет половину фактов. Веди файл:

- `.doubled-graph/drafts/discover.md` — append-only по ходу шагов 2–7.
- Шаг 8 (саммари пользователю) **читает** из этого файла, не восстанавливает по памяти.
- Файл **не удаляется** после discover — его читают шаги 02–03 (reconstruct-intent и draft-plan), чтобы не запрашивать метрики заново.

Формат:

```markdown
# Discovery — draft
Started: <ISO>
Status: in-progress | completed

## 1. AGENTS.md status
- <существует / создан / phase-блок добавлен>

## 2. Analyze (doubled-graph)
- Mode: full
- Duration: <ms>
- Symbols: <N>, Edges: <M>, Clusters: <K>

## 3. Metrics
- LOC: ...
- Languages: ...
- Top-10 hotspots (by find_all_callers):
  - ...

## 4. Docs found
- README.md (size, last modified)
- ARCHITECTURE.md (...)
- Claims extracted: ...

## 5. Tests
- Directory: ...
- Count: ..., Coverage (if available): ...
- Areas covered / uncovered: ...

## 6. Logs & observability
- Framework: ...
- Format: structured | ad-hoc
- Example log lines: ...

## 7. Infrastructure
- CI: ...
- Hooks: ...
- Docker / k8s: ...

## 8. Summary (user-shown)
- <финальный блок из шага 8>

## Risks flagged
- ...
```

---

## Шаги

**Шаг 1 — AGENTS.md phase.**

Добавь (или создай) `AGENTS.md` с phase-блоком в режиме `migration`:

```markdown
<!-- doubled-graph:phase:start -->
## doubled-graph phase
phase: migration
updated: <сегодня>
<!-- doubled-graph:phase:end -->
```

Если `AGENTS.md` уже есть — добавь блок, не затирай остальное.

**Шаг 2 — первичный analyze.**

```
doubled-graph.analyze(mode="full")
```

Это может занять минуты на больших репо. Подожди.

**Шаг 3 — собери метрики:**

- LOC по языкам (`tokei` / `cloc` / язык-встроенные tools);
- количество файлов, модулей;
- из computed graph — количество символов, связей, кластеров;
- список топ-10 функций с наибольшим `find_all_callers` (= hotspots).

**Шаг 4 — прочитай README и любые ARCHITECTURE.md / docs/.**

Извлеки:
- **заявленное назначение** продукта;
- упомянутые акторы (users, admins, workers, external systems);
- упомянутые интеграции (external APIs, DBs);
- если есть — архитектурные диаграммы или описания.

Не верь слепо — документация могла устареть. Отметь как «claim», проверь коррелирует ли с computed graph.

**Шаг 5 — найди существующие тесты.**

- директория `tests/`, `__tests__/`, `spec/`, файлы `*_test.go`, `*.test.ts`, etc.
- посчитай coverage если доступно (инструмент есть в технологии).
- отметь, какие области кода покрыты, какие — нет.

**Шаг 6 — логи и observability.**

- есть ли structured logs?
- используется ли OpenTelemetry / structured logging framework?
- найди примеры log-строк, определи формат.

**Шаг 7 — инфраструктура.**

- есть ли CI (`.github/workflows/`, `.gitlab-ci.yml`, …)?
- есть ли hooks (`.git/hooks/`, `.husky/`, `lefthook.yml`)?
- есть ли Dockerfile / compose / k8s манифесты?

**Шаг 8 — саммари пользователю.**

Источник данных для саммари — **`.doubled-graph/drafts/discover.md`** (читай секции 2–7), не память. Покажи:

```
Discovery saммари:

LANGUAGES:    <Python: 82%, TypeScript: 15%, Shell: 3%>
LOC:          <12 340>
MODULES:      <computed: 37 clusters by Leiden-like>
HOTSPOTS:     <топ-5 функций, где много callers — кандидаты на critical>
DOCS FOUND:   <README.md (2.1 KB), docs/API.md (4 KB)>
TESTS:        <pytest tests/: 42 файла, coverage ~45%>
LOGS:         <Python stdlib logging, ad-hoc format, NOT structured>
CI:           <.github/workflows/ci.yml с 3 jobs>
HOOKS:        <нет>

Наиболее вероятный замысел проекта (из README):
  <1–2 предложения>

Главные риски миграции:
  - <1–3 пункта: например, "тесты покрывают только 45% — восстановленная verification будет неполной">
```

**Approval gate:**

> «Это твой проект, как я его вижу? Что нужно уточнить или добавить перед следующим шагом?»

Жди ответа. Переход на `02-reconstruct-intent.md` — только после подтверждения.

---

## Анти-паттерны

- Не угадывай business intent из кода одного. Только из кода + README + ответов пользователя.
- Не делай рекомендаций по улучшению кода на этом шаге. Только факты.
- Не запускай `doubled-graph init` пока — он создаст пустые шаблоны, потом проще.
