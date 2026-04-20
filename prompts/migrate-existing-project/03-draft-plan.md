# 03 — Draft Development Plan

**Роль ИИ:** построить `development-plan.xml` поверх существующего кода.

---

## Externalize state

Плана на 10+ модулей + зависимости + criticality + фазы + data flows — легко 200+ решений. Локальная модель точно потеряет часть к концу. Веди:

- `.doubled-graph/drafts/plan-draft.md` — accumulate cluster→module mapping, criticality decisions, dependencies, phases.
- **Источник входных данных**: `.doubled-graph/drafts/discover.md` (из шага 01) — читай его, не память.
- После approval — финальный XML генерируется из scratchpad'а.

Формат:

```markdown
# Plan draft
Started: <ISO>
Status: in-progress | completed
Reads-from: .doubled-graph/drafts/discover.md

## Cluster → Module mapping (user-confirmed)
- cluster_1 (12 файлов: src/auth/*) → M-AUTH-CORE (criticality: critical, reason: PII+auth)
- cluster_2 → M-AUTH-VALIDATE (critical)
- ...

## Technology (from pyproject.toml/package.json/...)
- Runtime: ...
- Main libs: ...

## Dependencies between modules (from computed graph)
- M-AUTH-VALIDATE → M-AUTH-TOKENS
- ...

## Phases (markup order)
- Phase-1: M-AUTH-VALIDATE, M-PAYMENTS-CHARGE
- Phase-2: ...

## Data flows (for critical UCs)
- DF-LOGIN: M-ROUTES-LOGIN → M-AUTH-VALIDATE → M-SESSION-CREATE

## User approvals
- 2026-04-18T14:12: module list approved
- 2026-04-18T14:20: criticality assignments approved
```

---

## Шаги

**Шаг 1 — cluster-to-module mapping.**

`doubled-graph.analyze()` уже построил computed graph с кластерами (Leiden-like grouping). Для каждого кластера:

- имя → эвристическое `M-DOMAIN-PURPOSE` на основе имен файлов в кластере;
- `<Paths>` — все файлы кластера;
- `<Contract>` → **пустой** (заполняется на шаге 04 через markup).

Покажи пользователю маппинг:

```
Computed clusters → M-* candidates:

cluster_1 [12 файлов]: src/auth/* 
  → M-AUTH-CORE?

cluster_2 [4 файла]: src/auth/validate.py + 3 теста
  → M-AUTH-VALIDATE?

cluster_3 [18 файлов]: src/orders/*
  → M-ORDERS-CORE?

...
```

Пользователь подтверждает / переименовывает. Модульная декомпозиция — его решение, не твоё.

**Шаг 2 — technology.xml.**

Из computed graph извлеки импорты и зависимости. Сопоставь с `pyproject.toml` / `package.json` / `go.mod` / `Cargo.toml`. Заполни `docs/technology.xml`:

- `<Runtime>` — из lockfile.
- `<Libraries>` — только main deps (test/dev — отдельно).
- `<Testing>` — из findings на шаге 01.
- `<Deployment>` — из Dockerfile / k8s / Serverless-config, если есть.

**Шаг 3 — criticality для каждого M-*.**

Эвристика:
- hotspot (> 10 callers) → `critical`;
- touches PII / auth / payments / secrets → `critical`;
- остальные — `standard`;
- чистые helpers/formatters без вызывающих, кроме соседа в том же кластере → `helper`.

Покажи пользователю, он корректирует.

**Шаг 4 — зависимости между модулями.**

Из computed graph (CALLS, IMPORTS между кластерами) построй `<Dependencies>`. Эти данные уже в `doubled-graph` — просто отразите.

**Шаг 5 — фазы.**

Для миграции фазы соответствуют **порядку markup-а** (см. шаг 04), не генерации. Правило: критические модули в фазе 1, standard — фазы 2–3, helpers — последнее.

```xml
<Phase id="Phase-1">
  <Description>Критические модули: auth, payments</Description>
  <Step id="step-1" module="M-AUTH-VALIDATE" />
  <Step id="step-2" module="M-PAYMENTS-CHARGE" />
</Phase>
<Phase id="Phase-2">
  <Description>Стандартная бизнес-логика: orders, users</Description>
  <Step id="step-3" module="M-ORDERS-CREATE" />
  ...
</Phase>
```

**Шаг 6 — data flows.**

Для критических UC — `<DataFlow>` по computed graph. Инструмент уже знает процессы (execution flows).

**Шаг 7 — approval gate (upstream `doubled-graph plan` Step 2):**

Покажи пользователю в **таком порядке**:

1. **Компактный обзор плана**:
   - N модулей, разбивка по criticality (например: 5 critical / 12 standard / 8 helper);
   - граф зависимостей ASCII;
   - фазы разметки (какие модули — в первой волне markup, какие — дальше).
2. **⚠ Что требует особого внимания** (специфика миграции):
   - модули, чьи границы восстановлены по computed-graph, но **не подтверждены** пользователем в discover-шаге;
   - модули с неочевидным scope (несколько файлов, несколько кластеров);
   - любой `critical`-модуль, у которого нет сохранённой legacy-тестовой базы (markup без теста = risk);
   - orphan-кластеры в computed graph, не вошедшие ни в один M-*;
   - модули, у которых наш recovered contract расходится с docstring-ами/README legacy-проекта.
   Если ничего — «отклонений нет».
3. **Чек-лист одобрения** (режим `migration`, см. `methodology/drift-and-priority.md`):
   - [ ] план описывает **фактическое** состояние кода, не желаемое;
   - [ ] все bounded contexts покрыты модулями (нет orphan-кластеров);
   - [ ] `criticality` расставлен по реальной зоне ответственности, не по догадке;
   - [ ] порядок markup-фаз: critical → standard → helpers;
   - [ ] рефакторинг-идеи вынесены в отдельный список на **после** миграции, не в этот план.
4. **Вопрос**:

   > План миграции. Чтобы одобрить — подтвердите явно по чек-листу выше. Если какой-то модуль не соответствует реальному коду — назовите его и что нужно поправить.

**При revision**: показывай diff (добавлены/удалены/изменены модули и границы), не полный план заново.

---

## Критическое правило миграции

Этот план **не описывает желаемое будущее состояние**. Он отражает **текущее фактическое состояние**. В режиме `migration` артефакт догоняет код. Если пользователь хочет **изменить** архитектуру — это отдельный проект (рефакторинг), **после** миграции в `post_migration`.

---

## Переход

После approval → `04-markup-codebase.md`.
