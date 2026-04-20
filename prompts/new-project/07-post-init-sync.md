# 07 — Post-init sync

**Роль ИИ:** финальная синхронизация — computed graph + hooks + первый коммит с отмеченным baseline.

---

## Шаги

**Шаг 1 — полный analyze.**

```
doubled-graph.analyze(mode="full", force=True)
```

Это создаёт baseline computed graph. Не инкремент, а `full`, чтобы `code-fingerprint.json` был свежим.

**Шаг 2 — refresh полный.**

```bash
doubled-graph refresh --scope full
```

`doubled-graph refresh` — gateway: возвращает директиву агенту триггернуть upstream-skill `grace-refresh` с указанным scope. Синхронизирует `docs/knowledge-graph.xml` с результатом `analyze`. Обычно изменений быть не должно (код только что сгенерирован по плану), но если есть — ревью diff и коммит.

**Шаг 3 — doubled-graph lint.**

```bash
doubled-graph lint --path .
```

Должен пройти. Если нет — фикс разметки.

**Шаг 4 — detect_changes.**

```
doubled-graph.detect_changes(scope="all")
```

Должен быть пустой drift. Если нет:
- модули без кода → что-то не было реализовано (вернуться на 06-generate для недостающих);
- код без модулей → что-то лишнее (дополнительные утилиты — решать с пользователем).

**Шаг 5 — установка hooks.**

```bash
doubled-graph init-hooks --all
```

Это:
- git `post-commit`,
- Claude Code PostToolUse (если `.claude/settings.json` существует),
- `.gitignore` для `.doubled-graph/logs/` и `.doubled-graph/cache/`.

**Шаг 6 — прогон тестов.**

Запусти все `V-M-*` командой, определённой в `verification-plan.xml § Gate G-pre-merge`.

Если что-то не проходит — фикс, возврат к 06-generate.

**Шаг 6b — scratchpads от шагов 01–05.**

Проверь `.doubled-graph/drafts/`:
- `interview.md` — `Status: completed`?
- `plan.md` — все `Approvals` проставлены?

Если да — опционально переместить в `.doubled-graph/drafts/_archive/<дата>/` (чистый drafts + сохранена история). Рекомендация: **переместить**, не удалять. Сохраняет audit-trail зарождения проекта для будущей отладки.

**Шаг 7 — первый коммит.**

```bash
git add -A
git commit -m "chore(init): doubled-graph baseline established

- requirements.xml, technology.xml, development-plan.xml, verification-plan.xml,
  knowledge-graph.xml, operational-packets.xml созданы;
- MVP кода по фазам <N>;
- hooks установлены;
- phase=post_migration.

LINKS: $(перечисли UC-*)"
```

**Шаг 8 — сводка пользователю.**

Выведи:

```
Baseline установлен.

Артефакты:
  - docs/requirements.xml — <N> use cases
  - docs/development-plan.xml — <N> modules across <M> phases
  - docs/verification-plan.xml — <K> verification entries

Код:
  - <N> файлов
  - <LOC> строк
  - computed graph: <X> symbols, <Y> relationships

Что дальше:
1. Проверь работу: <команда запуска из technology.xml>.
2. Для следующей фичи — добавь UseCase в requirements.xml, запусти `doubled-graph plan`.
3. Перед любой правкой — prompts/maintenance/on-before-edit.md.

Режим: post_migration. Переключать только если начнёте крупный рефакторинг (см. methodology/drift-and-priority.md).
```

---

## Что дальше

Новый проект завершён. Дальше живёшь по `prompts/maintenance/*`:
- `on-before-edit.md` перед правками;
- `on-after-edit.md` после;
- `on-drift-detected.md` если `detect_changes` обнаружил расхождение;
- `on-user-manual-edit.md` если код правил человек вручную.
