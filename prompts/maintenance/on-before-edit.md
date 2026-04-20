# on-before-edit — перед любой правкой функции/класса/модуля

**Целевая аудитория:** ИИ-ассистент в IDE (Claude Code / Cursor / Codex / Continue / Windsurf / local-LLM).
**Триггер:** намерение изменить существующий код.
**Время на исполнение:** ≤ 2 секунды если index свежий, ≤ 10 секунд если требуется инкремент.

---

## Инструкция

**Шаг 1 — проверить свежесть индекса.**

Если с момента последнего `doubled-graph analyze` были правки файлов и ты **не в Claude Code с активным PostToolUse hook**, сначала:

```
doubled-graph.analyze(mode="incremental", paths=["<список только-что-тронутых-файлов>"])
```

В Claude Code с hook'ом — пропусти этот шаг (hook сделал).

---

**Шаг 2 — обязательный impact.**

```
doubled-graph.impact(
  target="<имя-функции-или-класса-или-путь-к-файлу>",
  direction="upstream",
  depth=3
)
```

Если символ неоднозначен — MCP вернёт `INVALID_INPUT` со списком кандидатов. Показываешь их пользователю, просишь уточнить.

---

**Шаг 3 — интерпретация risk.level.**

| risk.level | Действие |
|---|---|
| `NONE` / `LOW` | Продолжай правку без дополнительного подтверждения. |
| `MEDIUM` | Упомяни в ответе пользователю: «правлю X, затрагивает N прямых потребителей: [...]». Продолжай. |
| `HIGH` | **Останови исполнение.** Покажи `risk.reasons` пользователю. Жди явного «продолжай». |
| `CRITICAL` | **Останови исполнение.** Покажи `risk.reasons` + `affected_modules` + `affected_verification`. Жди явного «продолжай». Предложи альтернативу: «могу ли я вместо этого …». |

---

**Шаг 4 — проверить режим и контракт.**

Прочитай `AGENTS.md`, ищи блок `<!-- doubled-graph:phase:start -->`.

**В `post_migration`:**
- Найди module_id символа через `doubled-graph.impact().target_resolved.module_id`.
- Прочитай контракт модуля: `doubled-graph file show <file> --contracts`.
- Правка не должна нарушить контракт. Если нарушает — это новое требование, **останови** и запроси `doubled-graph plan` цикл.

**В `migration`:**
- Правки разрешены свободнее (код — ground-truth).
- После правки — обязательно `doubled-graph refresh` для синхронизации артефактов.

---

**Шаг 5 — провести правку.**

- Используй Edit / Write / MultiEdit (название инструмента зависит от IDE).
- Сохрани якоря (`START_CONTRACT`, `BLOCK_*`).
- Если затронут `CHANGE_SUMMARY` — добавь запись с датой и кратким why.

---

**Шаг 6 — переход на on-after-edit.md.**

---

## Быстрая шпаргалка (для locally hosted модели — ≤ 1 KB)

```
BEFORE-EDIT:
1. doubled-graph.analyze(mode=incremental, paths=[touched]) if no PostToolUse hook
2. doubled-graph.impact(target=X, direction=upstream, depth=3)
3. risk HIGH/CRITICAL -> STOP, ask user
4. read AGENTS.md phase:
   - post_migration: doubled-graph file show --contracts -> do not break
   - migration: free edit, must `doubled-graph refresh` after
5. edit (keep anchors intact, update CHANGE_SUMMARY)
6. goto on-after-edit
```

---

## Что делать, если инструменты недоступны

- **doubled-graph.impact вернул NOT_IMPLEMENTED_MVP**: обратись к `cgc analyze_code_relationships query_type=find_all_callers target=<X>` через MCP CGC напрямую, или `grep`-поиск вызовов + ручной risk-assessment. Предупреди пользователя: «impact-анализ в текущей MVP-версии частичен, risk оценен приближённо».
- **doubled-graph file show недоступен** (grace CLI не установлен): прочитай файл напрямую через Read, найди MODULE_CONTRACT и CONTRACT:fn секции руками.
- **AGENTS.md нет:** default `post_migration`, предупреди пользователя, что phase-блок не найден.

---

## Anti-patterns — чего НЕ делать

- Не правь без `impact`. Это нарушает принцип 10 и risk-gate.
- Не игнорируй HIGH/CRITICAL risk «молча» — пользователь должен видеть объяснение.
- Не меняй `phase:` в `AGENTS.md` без явного запроса пользователя.
- Не удаляй якоря при правке (`doubled-graph lint` упадёт).
- Не добавляй «я исправил все ссылки» без явного подтверждения через `detect_changes`.
