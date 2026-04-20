# Runtime adapter template — `<IDE / клиент>`

**Структура адаптера** (копируй, заполняй).

## 1. Статус поддержки MCP

- Версия протокола MCP: … (spec-2025-03-26 на апрель 2026).
- Транспорт: stdio / SSE / HTTP.
- Ограничения: …

## 2. Как регистрировать `doubled-graph`

Путь конфига: …

```json
{
  "mcpServers": {
    "doubled-graph": {
      "command": "python",
      "args": ["-m", "doubled_graph"],
      "cwd": "/absolute/path/to/repo"
    }
  }
}
```

## 3. Skills / rules / instructions

Как подключается набор agentic-скиллов и инструкций:
- `.claude/skills/` — Claude Code;
- `.cursor/rules/*.mdc` — Cursor;
- `.continue/config.json` — Continue;
- …

## 4. Hooks

Поддерживаются ли PreToolUse / PostToolUse / OnSessionStart? Если да — пример конфига. Если нет — явно указать «нет; используем только `post-commit` baseline».

## 5. Permissions / approvals UI

Есть ли UI одобрения каждого tool call? Как настроить, чтобы HIGH/CRITICAL risk от `impact` блокировал выполнение?

## 6. Ограничения локальных моделей в этом IDE

Что работает, что нет (tool-use, structured output, memory). Отсылка на `local-llm.md`.

## 7. Установка одной командой (cheat-sheet)

```bash
...
```

## 8. Известные issues

- GitHub issue / ...
- workaround: ...

---

## Чек-лист

- [ ] MCP подключён, `doubled-graph` виден как инструмент.
- [ ] skill'ы grace-marketplace подключены.
- [ ] hooks настроены по возможностям IDE.
- [ ] approval UI даёт остановить правку при HIGH/CRITICAL.
