# 04 — Markup codebase

**Роль ИИ:** добавить разметку якорями без изменения логики.

**КРИТИЧНО:** один коммит = один модуль. `git diff` должен содержать **только** якоря и комментарии, **никаких** изменений в коде.

---

## Externalize state

Разметка идёт по 10+ модулей, каждый — 9 под-шагов, user-clarifications для helper-функций, решения «пропустить / в DRIFT.md». Это самый длинный процесс миграции. Обязательный журнал:

- `.doubled-graph/drafts/markup-progress.md` — per-module статус, append-only.
- Возобновление прерванной миграции — открой файл, найди последний модуль со статусом `pending` или `in-progress`, продолжай оттуда.
- **Читает input**: `.doubled-graph/drafts/plan-draft.md` (список модулей + criticality + фазы из шага 03).

Формат:

```markdown
# Markup progress
Started: <ISO>
Status: in-progress | completed
Reads-from: .doubled-graph/drafts/plan-draft.md

## Modules (in phase order)

### M-AUTH-VALIDATE (Phase-1, criticality=critical)
- Status: committed
- Files: src/auth/validate.py
- MODULE_CONTRACT: done
- CONTRACTS (functions): validateUser (done), refreshToken (done)
- BLOCKS: DECODE_JWT, CHECK_CLOCK_SKEW
- User clarifications: none
- doubled-graph lint: ✓
- git diff review: semantic-change-free ✓
- Commit: abc1234
- refresh: ✓ (commit def5678)

### M-AUTH-TOKENS (Phase-1, critical)
- Status: in-progress
- ...

### M-BILLING-STRIPE (Phase-2, critical)
- Status: pending

### M-UTIL-FORMAT (Phase-3, helper)
- Status: pending
- Note: skip runtime-контракты, минимальный MODULE_CONTRACT

## Skipped modules
- M-WEIRD-GLUE — logic unclear, moved to DRIFT.md (D-MARKUP-001), will return after user input

## User clarifications log
- 2026-04-18T11:30: `format_address(addr)` helper → пользователь: «форматирует в canonical form per RFC 5321, используется в email sending»
```

---

## Порядок работы

Идём по фазам из `development-plan.xml`, внутри фазы — от **высокой** criticality к низкой.

Для каждого модуля из текущей фазы:

### Шаг 4.1 — Прочитай все файлы модуля.

```bash
doubled-graph file show <path> --contracts --blocks
```

В legacy-коде обычно вернёт **пусто** (нет ещё якорей) — ок.

### Шаг 4.2 — Составь MODULE_CONTRACT.

На основе:
- публичных экспортов (функции / классы, доступные извне);
- существующих docstring / comments;
- зависимостей (imports);
- тестов (они часто описывают то, что модуль делает).

Формат — см. `methodology/language-adapters/<язык>.md`.

### Шаг 4.3 — Для каждой публичной функции составь CONTRACT.

PURPOSE, INPUTS, OUTPUTS, SIDE_EFFECTS — из:
- текущей сигнатуры;
- тестов, покрывающих функцию;
- места вызова (callers).

Если функция — helper без документации и без очевидного назначения — спроси пользователя: «Эта функция называется `fn_X` и используется в Y местах. Назначение не очевидно. Можешь описать одним предложением?»

### Шаг 4.4 — Блоки для длинных функций.

Только если функция > 20 строк. Имена блоков — semantic, не scope-based.

### Шаг 4.5 — CHANGE_SUMMARY.

Добавь секцию в конец файла:

```
START_CHANGE_SUMMARY
<сегодня>: doubled-graph migration markup added (no behavior changes)
END_CHANGE_SUMMARY
```

### Шаг 4.6 — Проверка.

```bash
doubled-graph lint --path <file>
```

Должен пройти. Если нет — фикс якорей.

### Шаг 4.7 — git diff ревью.

Покажи пользователю **полный diff** файла. Правило:
- все plus-lines — только комментарии/якоря;
- если есть plus-lines в коде (не комментарий) — **откати**, это семантическая правка.

В UI ИИ-клиента это сложно без visual-инструментов; попроси пользователя: «Посмотри git diff, что-то семантическое изменилось?»

### Шаг 4.8 — Коммит.

```bash
git add <file>
git commit -m "chore(markup): <M-id> module contract + anchors"
```

### Шаг 4.9 — `doubled-graph refresh --scope targeted`.

После каждого модуля — подтянуть `docs/knowledge-graph.xml` и `docs/development-plan.xml`:

```bash
doubled-graph refresh --scope targeted --modules <M-id>
```

Ревью diff'а `docs/`, коммит отдельно:

```bash
git add docs/
git commit -m "chore(refresh): sync docs after <M-id> markup"
```

---

## Что делать при сопротивлении

**Файл большой, много функций.** Не пытайся разметить всё за один commit. Одна функция = один логический шаг; файл целиком = один коммит (но не 20 файлов в одном commit).

**Код «странный», неясно, что он делает.** Не пиши MODULE_CONTRACT guess. Отметь в `docs/DRIFT.md` как `D-MARKUP-XXX — M-* unclear, skipping markup`. Пропусти этот модуль; вернёшься позже.

**Тесты не запускаются.** Markup всё равно разрешён (не меняем код), но зафиксируй в DRIFT.md как блокер перед переключением в `post_migration`.

**Пользователь пишет новый код во время миграции.** Прямо запрещено. Skip-новый-код ветку до окончания миграции. Если уже произошло — новый код размечается отдельно, как fresh generation (не migration).

---

## Переход

Когда **все модули** из development-plan размечены и все `doubled-graph lint` проходят — → `05-verification-and-logs.md`.
