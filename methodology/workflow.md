# Workflow doubled-graph

Три сценария, один скелет.

## Общий скелет

```
            ┌───────────────────────────────────────────────────┐
            │  docs/*.xml   ← doubled-graph plan ← requirements gather │
            │       ↓                                            │
            │  code + markup ← doubled-graph execute / multiagent-execute │
            │       ↓                                            │
            │  verification ← doubled-graph verification                 │
            │       ↓                                            │
            │  refresh ← doubled-graph refresh + analyze         │
            │       ↺ (loop on drift, see drift-and-priority.md) │
            └───────────────────────────────────────────────────┘
```

Все три сценария проходят эти стадии. Различается только **входная точка** и **что считается ground-truth** на первом шаге.

Ground-truth по режимам (см. `drift-and-priority.md`):

- **Новый проект** — с 1-го шага режим `post_migration`: артефакты = ground-truth.
- **Миграция** — режим `migration`: код = ground-truth, артефакты догоняют.
- **Поддержка** — режим тот, который установлен в `AGENTS.md` (обычно `post_migration` после завершения миграции).

---

## Сценарий 1. Новый проект

Entry-prompt: `prompts/new-project/00-entry-prompt.md`.

1. **Intent-интервью** (человек ↔ ИИ). ИИ задаёт ~10 вопросов: продукт, аудитория, нефункциональные ограничения, стек-предпочтения. Глубина заполнения артефактов — всегда максимальная (см. `auto-scaling.md`), объём зависит от реального количества UC/модулей.
2. **`doubled-graph init`** — ИИ создаёт `docs/*.xml` шаблоны + `AGENTS.md`. Режим в `AGENTS.md` сразу проставляется `post_migration` (проект рождается согласованным).
3. **`doubled-graph plan`** — архитектура модулей. **Approval-gate: Step 2** (человек утверждает модули).
4. **`doubled-graph plan` Step 3** — черновик verification. **Approval-gate**.
5. **`doubled-graph execute` Step 1** — план перед исполнением. **Approval-gate**.
6. **Генерация кода** — по фазам `development-plan.xml`. ИИ размечает файлы якорями (см. `artifacts.md § markup`).
7. **Первичный `doubled-graph analyze --mode full`** — создаёт computed graph поверх только что написанного кода.
8. **`doubled-graph verification`** — прогон тестов + добавление в `verification-plan.xml`.
9. **Установка hooks** — `doubled-graph init-hooks` ставит git post-commit и (если Claude Code) PostToolUse.

С этого момента переход в **Сценарий 3 — Поддержка**.

---

## Сценарий 2. Миграция существующего

Entry-prompt: `prompts/migrate-existing-project/00-entry-prompt.md`.

**Контекст:** upstream GRACE сценария миграции не даёт. doubled-graph это расширяет. Код существует, артефактов нет.

1. **Обнаружение** — `prompts/migrate-existing-project/01-discover.md`. ИИ запускает `doubled-graph analyze --mode full` на существующем коде. Получает computed-graph, считает метрики (модули по кластерам, LOC, языки), проверяет наличие legacy-документации (README, ARCHITECTURE.md, docs/).
2. **Восстановление замысла** — `02-reconstruct-intent.md`. ИИ по коду + README восстанавливает draft `requirements.xml` и задаёт пользователю 5–10 уточняющих вопросов (что намерение, что случайность). **Approval-gate: требования**.
3. **Черновик плана** — `03-draft-plan.md`. `development-plan.xml` собирается по кластерам computed-graph. **Approval-gate: архитектура**.
4. **Постепенная разметка** — `04-markup-codebase.md`. **Критичный нюанс:** в режиме `migration` не правим логику, только добавляем якоря и контракты, без семантических изменений. `doubled-graph refresh` после каждого файла — для синхронизации declared graph.
5. **Verification** — `05-verification-and-logs.md`. Если legacy-тестов нет — ИИ предлагает минимальный набор для критических модулей; если есть — привязывает существующие к `V-M-*` записям.
6. **Gates** — `06-validation-gates.md`. Критерии готовности миграции (`doubled-graph lint` чист, все модули имеют contract, computed ≈ declared, чек на `detect_changes` даёт `[]`).
7. **Переключение режима** — человек меняет `phase: migration` → `phase: post_migration` в `AGENTS.md`. С этого момента политика дрейфа разворачивается (артефакты = ground-truth).

**Persistence режима между волнами миграции:** `phase: migration` сохраняется **на весь период миграции**, через все волны и коммиты. Не сбрасывается per wave. Каждая волна заканчивается `doubled-graph refresh`, но режим остаётся `migration` до финального `06-validation-gates.md`. Это важно: если режим случайно переключился на `post_migration` посреди миграции, следующая волна будет блокировать правки, которые легитимны для миграционного контекста. Если это произошло — откат через `DRIFT.md` запись (см. `drift-and-priority.md § Переключение режима`).

**Типичные провалы миграции** (учтено в промптах):

- Попытка разметить весь репозиторий сразу. *Митигация:* идём по кластерам computed-graph, начинаем с критичных.
- «ИИ понял замысел неправильно» — человек спорит с восстановленными требованиями. *Митигация:* Approval-gate на требованиях; фиксация разногласий в `docs/DRIFT.md`.
- Случайные семантические правки во время разметки. *Митигация:* `04-markup-codebase.md` явно запрещает менять логику; `git diff` ревью каждого файла.

---

## Сценарий 3. Поддержка (день-в-день)

Entry-prompts: `prompts/maintenance/*.md`.

Предполагается: режим `post_migration`, hooks установлены, computed/declared graphs согласованы.

### Поток «новая фича»

1. Человек/ИИ формулирует изменение в `requirements.xml` (новый UC-xxx).
2. `doubled-graph plan` — обновление `development-plan.xml` (новые/изменённые M-xxx). **Approval-gate**.
3. `doubled-graph execute` (или `doubled-graph multiagent-execute` для нескольких модулей). **Approval-gate**.
4. Код + разметка + logs + verification — автоматически.
5. Коммит → `post-commit` hook → `doubled-graph analyze --mode incremental`.
6. Pre-commit (опц., рекомендовано в CI): `doubled-graph detect_changes --scope staged` + `doubled-graph lint`.

### Поток «обнаружен дрейф»

Триггер: `doubled-graph detect_changes` вернул непустой drift ИЛИ пользователь поправил код вручную и hook зарегистрировал это в логах.

Процесс — `prompts/maintenance/on-drift-detected.md`:

1. ИИ смотрит тип дрейфа (`code_without_module` / `module_without_code` / `contract_mismatch` / `stale_crosslinks` / `missing_verification` / `markup_missing`).
2. Применяет политику §9:
   - В `post_migration`: спрашивает пользователя «новое требование или баг?».
   - «Новое требование» → возврат в поток «новая фича», шаг 2.
   - «Баг» → `doubled-graph fix` приводит код под контракт.
   - «Не знаю» → запись в `docs/DRIFT.md`, модуль блокируется для правок ИИ до разрешения.
3. В `migration` — `doubled-graph refresh` обновляет артефакты под код без вопросов.

### Поток «ручная правка человека»

Триггер: `prepare-commit-msg` hook (если включён) распознал trailer `DG-Authored: human` или `mixed`.

Процесс — `prompts/maintenance/on-user-manual-edit.md`:

1. `doubled-graph analyze --mode incremental` (автоматически, через post-commit).
2. `doubled-graph detect_changes --scope staged` — если drift ∅, ничего не делаем.
3. Если drift есть — см. «обнаружен дрейф» выше.

### Перед любой правкой кода ИИ

Промпт `prompts/maintenance/on-before-edit.md` (enforced в CLAUDE.md текущего проекта через аналог):

1. `doubled-graph impact(target=<символ>, direction=upstream)`.
2. Если `risk.level ∈ {HIGH, CRITICAL}` — остановка, показываем пользователю, ждём подтверждения.
3. Иначе — продолжаем правку.

### После правки (до коммита)

Промпт `prompts/maintenance/on-after-edit.md`:

1. `doubled-graph analyze --mode incremental --paths <touched>` (PostToolUse в Claude Code сделает это автоматически; в других IDE — ручной вызов).
2. `doubled-graph refresh --scope targeted` — обновить declared для затронутых модулей.
3. `doubled-graph detect_changes --scope staged` — проверка дрейфа перед коммитом.

---

## Приёмные критерии каждого шага

Формализованы в `approval-checkpoints.md`. Правило без исключений: **если gate не пройден, следующий шаг не начинается**. Технически это обеспечивают skills upstream (явная остановка и ожидание) + `doubled-graph lint` в CI.
