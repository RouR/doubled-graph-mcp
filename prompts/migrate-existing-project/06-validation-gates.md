# 06 — Validation gates

**Роль ИИ:** прогнать финальные проверки, помочь пользователю переключиться в `post_migration`.

---

## Чек-лист завершения миграции

Миграция считается **завершённой**, когда **все пункты** ниже — зелёные:

### Чек 1. `doubled-graph lint` полностью проходит.

```bash
doubled-graph lint --path .
```

Exit code = 0. Если нет — вернись на 04-markup-codebase, найди файл с ошибкой, почини якоря.

### Чек 2. `doubled-graph detect_changes --scope all` → пусто.

```
doubled-graph.detect_changes(scope="all")
```

drift должен быть `{ code_without_module: [], module_without_code: [], contract_mismatch: [], stale_crosslinks: [], missing_verification: [], markup_missing: [] }`.

**Исключения, разрешённые для завершения миграции:**
- `missing_verification` для модулей с `criticality=helper` — допустимо;
- `missing_verification` для модулей, явно помеченных `pending-to-write` в `verification-plan.xml` — допустимо с записью в DRIFT.md.

Всё остальное — **не** допустимо. Вернись на соответствующий шаг.

### Чек 3. Все критические V-M-* имеют Markers и прогоняются.

```bash
# для каждого V-M-*:
<command из verification-plan.xml>
```

Должны проходить.

### Чек 4. CHANGE_SUMMARY в каждом размечённом файле.

Есть хотя бы одна запись «doubled-graph migration markup added».

### Чек 5. `docs/DRIFT.md` пересмотрен.

Все записи либо:
- resolved (закрыты с датой и причиной),
- явно принятые как known limitation с owner / deadline.

Не осталось `status: unknown` записей.

### Чек 6. Hooks установлены.

```bash
doubled-graph init-hooks --all
```

### Чек 6b. Scratchpads из шагов 01–05 проверены.

Все файлы в `.doubled-graph/drafts/`:
- `discover.md` — `Status: completed`?
- `intent-recovery.md` — `Status: completed`?
- `plan-draft.md` — все модули в `Status: committed`?
- `markup-progress.md` — все модули `committed` или явно `skipped → DRIFT.md`?

Если статусы in-progress или pending — миграция не закончена, возврат на соответствующий шаг.

**Cleanup после успешного переключения phase** (опционально): переместить завершённые scratchpads в `.doubled-graph/drafts/_archive/<дата>/` либо удалить. Решение — пользователь (audit trail vs чистый drafts-каталог). Рекомендация: **переместить**, не удалять — scratchpads фиксируют историю миграции и полезны для постмортем-анализа.

### Чек 7. CI обновлён (если был).

Добавлены в CI:
- `doubled-graph lint`;
- `doubled-graph analyze --mode full` + `detect_changes --scope compare`.

Если их нет — добавь. Готовых шаблонов в `methodology/ci-templates/` пока нет (директория зарезервирована под будущий релиз); собери по инструкции из `doubled-graph/HOOKS.md § 4 CI-шаблон` — там описан baseline-flow для GitHub Actions / GitLab CI.

---

## Переключение phase

Когда все 7 чеков зелёные:

```bash
doubled-graph phase set post_migration \
  --reason "migration complete: all modules markup'd, V-M-* attached, detect_changes empty"
```

Инструмент правит блок в `AGENTS.md` и создаёт коммит:

```
chore(phase): migration → post_migration

reason: migration complete: all modules markup'd, V-M-* attached, detect_changes empty
scope-all-detect_changes: clean
grace-lint: clean
critical-V-M-*-pass: <N>/<N>
```

**Approval pользователя — обязательный** перед переключением. Покажи ему чек-лист с галочками, явно запроси «переключаем?»

---

## Что дальше

После переключения:
- режим `post_migration` — артефакты теперь ground-truth;
- любая правка идёт через `prompts/maintenance/on-before-edit.md`;
- если `detect_changes` находит расхождение — `on-drift-detected.md § B` (с пользователем решают);
- если что-то срочно и код надо обновить быстрее артефактов — временно переключись в `migration` с записью в DRIFT.md (см. `methodology/drift-and-priority.md § Переключение режима`).

---

## Известные паттерны «почти готово, но нет»

- **«ещё одну фичу доделаю, потом закрою миграцию».** Анти-паттерн. Закрой миграцию, потом добавляй фичу по обычному post_migration-циклу. Иначе миграция станет бесконечной.
- **«тесты пишу завтра».** `pending-to-write` с deadline > 7 дней — блокер. Либо пиши тесты, либо соглашайся с deadline и пиши в DRIFT.md.
- **«эти deprecated-модули я скоро удалю».** В режиме `post_migration` удаление — это новое требование; планируется `doubled-graph plan`. В миграции удалять можно, **после** того как убедишься, что не нужны (callers=0).

---

## Переход

Миграция завершена. Дальше — `prompts/maintenance/*`.
