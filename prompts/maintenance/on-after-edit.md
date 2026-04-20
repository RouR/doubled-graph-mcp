# on-after-edit — после правки, до коммита

**Целевая аудитория:** ИИ-ассистент.
**Триггер:** только что сохранён изменённый файл.

---

## Инструкция

**Шаг 1 — обновить computed graph для тронутых файлов.**

В Claude Code с PostToolUse hook — пропусти (hook уже сделал).
В остальных IDE:

```
doubled-graph.analyze(mode="incremental", paths=["<тронутые-файлы>"])
```

---

**Шаг 2 — обновить declared (если правка семантическая).**

Если правка повлияла на:
- публичные экспорты модуля (добавил/удалил/переименовал функцию, изменил сигнатуру);
- зависимости модуля (новый import с другого M-*);
- поведение, затрагивающее `verification-plan.xml`-записи;

Запусти:

```bash
doubled-graph refresh --scope targeted --modules <M-id>
```

Если правка чисто внутренняя (логика внутри блока, не меняющая контракт) — пропусти.

---

**Шаг 3 — проверить дрейф перед коммитом.**

```
doubled-graph.detect_changes(scope="staged")
```

**Если drift пусто** — можно коммитить.

**Если drift непуст** — перейди на `on-drift-detected.md`.

---

**Шаг 4 — doubled-graph lint.**

```bash
doubled-graph lint --path .
```

Проверяет парность якорей. Fails-loud. Если упало — поправь синтаксис разметки, не игнорируй.

---

**Шаг 5 — прогнать релевантные тесты.**

Из `verification-plan.xml` найди `V-M-*` записи для тронутого модуля, выполни их `Command`.

**Если тесты упали** — останови, покажи ошибку пользователю. Не коммить сломанное.

---

**Шаг 6 — коммит.**

Перед коммитом проверь все четыре gate:
- `detect_changes` пусто,
- `doubled-graph lint` прошёл,
- тесты прошли,
- `impact` перед правкой был не CRITICAL (или был явно одобрен).

**Если в правке был contract-change** (сигнатура публичного экспорта, pre/post/invariant, `<PublicExports>`, CrossLinks, `criticality`) — **остановись и покажи пользователю отдельным блоком**:

```
⚠ CONTRACT CHANGE в <M-ID>:
  было: <old signature/pre/post/inv>
  стало: <new signature/pre/post/inv>
  причина: <из задачи / из diff>
  callers затронуты: <из impact depth=1>
```

Пользователь должен подтвердить отдельной фразой («contract change ок», «откати contract и оставь только реализацию» и т.п.). Без этого подтверждения — не коммить. Внутренние правки (без изменения экспортов и контракта) этого шага не требуют.

Только после подтверждения (или если contract-change нет) — коммить.

Commit-сообщение содержит минимум:
```
<краткое описание изменения>

Affected: <M-ids через запятую>
LINKS: <UC-ids через запятую>
```

Если был contract-change — добавь строку `Contract-change: <M-ID> <что>`.

Claude Code по умолчанию добавит `Co-Authored-By: Claude`. Если `prepare-commit-msg` hook установлен — добавится `DG-Authored: ai`.

---

## Шпаргалка (<1 KB)

```
AFTER-EDIT:
1. doubled-graph.analyze(mode=incremental, paths=[touched]) if no hook
2. if semantic change: doubled-graph refresh --scope targeted --modules <M-id>
3. doubled-graph.detect_changes(scope=staged)
   drift -> goto on-drift-detected
4. doubled-graph lint
5. run V-M-* tests for touched modules
6. if contract-change -> show diff block, require explicit user confirmation
7. commit with LINKS, Affected, and (if contract-change) Contract-change fields
```

---

## Что коммитить, что не коммитить

**Коммитим:**
- изменённый код,
- обновлённые `docs/*.xml` (если `doubled-graph refresh` изменил),
- обновлённый `CHANGE_SUMMARY` в файле кода.

**Не коммитим:**
- `.doubled-graph/cache/` (в .gitignore после `init-hooks`),
- `.doubled-graph/logs/` (в .gitignore),
- временные файлы тест-фреймворка.

**Коммитить отдельно, если много изменений:**
- chore-правки (переименование без логики) — отдельный commit.
- markup-правки (только якоря) — отдельный commit в режиме `migration`, чтобы diff контракта был читаемый.

---

## Anti-patterns

- Не коммить без `detect_changes`. Методология требует drift-check.
- Не коммить только `docs/*.xml` без кода, если это не `doubled-graph refresh` pass. Declared без computed — дрейф.
- Не коммить через `--no-verify`. Если hook упал — поправь проблему, не обходи.
- Не смешивай правку > 1 модуля в один коммит без обоснования. Мелкие атомарные коммиты упрощают revert.
