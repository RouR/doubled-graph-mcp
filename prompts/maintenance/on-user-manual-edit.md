# on-user-manual-edit — после ручной правки человеком

**Целевая аудитория:** ИИ-ассистент.
**Триггер:** пользователь сделал правку в коде без участия ИИ. Возможные сигналы:
- в logs `post-commit` появилось событие с `affected files`, которых ИИ в последний час не трогал;
- `prepare-commit-msg` hook добавил `DG-Authored: human` или `DG-Authored: mixed`;
- пользователь явно говорит «я поправил X сам, посмотри».

---

## Инструкция

**Шаг 1 — пересчитай computed graph.**

Если `post-commit` hook ещё не запустился (пользователь не коммитил, просто правил файлы):

```
doubled-graph.analyze(mode="incremental", paths=["<список-изменённых-файлов>"])
```

---

**Шаг 2 — прочитай `AGENTS.md` phase.**

- `migration` → следуй `on-drift-detected.md § A`.
- `post_migration` → продолжай ниже.

---

**Шаг 3 — проверь дрейф.**

```
doubled-graph.detect_changes(scope="branch", base_ref="main")
```

(`scope="branch"` вместо `staged`, потому что пользователь мог править за пределами единичного коммита.)

**Если drift пусто** — всё в порядке, ручные правки прошли по контрактам. Ничего дополнительно не делаем.

**Если drift непуст** — переходи на `on-drift-detected.md § B` (post_migration branch).

---

**Шаг 4 — проверь якоря.**

Ручные правки часто **ломают** разметку:
- забыли `END_BLOCK_*`;
- переименовали функцию, но старое `START_CONTRACT: old_name` осталось;
- добавили новый метод без `MODULE_MAP` обновления.

```bash
doubled-graph lint --path .
```

Если упало — предложи пользователю: «Ручная правка нарушила разметку в N файлах: <список>. Могу починить автоматически (только якоря, без правки логики). Разрешить?»

Если да — правь только якоря (**не** меняй логику кода), запусти `doubled-graph lint` снова.

---

**Шаг 5 — проверь `CHANGE_SUMMARY`.**

Добавь запись в каждый изменённый файл:

```
// START_CHANGE_SUMMARY
// ...
// 2026-04-18: <краткое описание человеческой правки> (DG-Authored: human)
// END_CHANGE_SUMMARY
```

Это важно для:
- провенанса при будущих drift-investigations;
- формальной фиксации, что правка прошла с пониманием контекста (даже если не через ИИ).

---

**Шаг 6 — опционально: `doubled-graph refresh` если семантика изменилась.**

Если ручная правка изменила публичные экспорты или зависимости — запусти `doubled-graph refresh --scope targeted`, как в `on-after-edit.md § 2`.

---

## Что НЕ делать

- **Не удаляй ручные правки «потому что они не соответствуют плану».** В `migration` они — источник истины. В `post_migration` — возможное новое требование, решает пользователь.
- **Не меняй поведение кода при фиксе разметки.** Только якоря.
- **Не пиши в `docs/DRIFT.md` сам.** Это для нерешённых случаев — пользователь должен подписать.

---

## Шпаргалка

```
MANUAL-EDIT:
1. analyze(mode=incremental, paths=[touched])
2. read AGENTS.md phase
   migration -> on-drift-detected § A
3. detect_changes(scope=branch, base_ref=main)
   drift -> on-drift-detected § B
4. doubled-graph lint; if broken anchors -> offer to fix anchors only
5. update CHANGE_SUMMARY with (DG-Authored: human) entry
6. if public semantics changed -> doubled-graph refresh --scope targeted
```
