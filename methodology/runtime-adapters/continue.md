# Runtime adapter: Continue

## 1. MCP

Continue (v1.0+, open source) поддерживает MCP с 2025. Транспорт stdio + SSE.

Конфиг: `.continue/config.json` в репо или `~/.continue/config.json`.

## 2. Регистрация `doubled-graph`

`.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "python",
          "args": ["-m", "doubled_graph"]
        }
      }
    ]
  }
}
```

> На 2026-04 конфиг-ключ всё ещё в `experimental` — сверь актуальное имя в docs.continue.dev.

## 3. Rules / prompts

Continue читает `rules.md` или `systemMessage` из `config.json`. Добавь общий prompt с обязательствами doubled-graph:

```json
{
  "systemMessage": "Ты работаешь по методологии doubled-graph. Перед любой правкой функции вызови doubled-graph.impact(target=<name>). Если risk.level >= HIGH — остановись и запроси подтверждение. Перед commit — вызови doubled-graph.detect_changes."
}
```

## 4. Hooks

Continue **не имеет** PreToolUse/PostToolUse хуков в обычном смысле. Есть `onBeforeMessage` и `onAfterMessage` расширения через custom slash commands, но они не про tool calls.

**Митигация** — baseline `post-commit` + ручной `analyze` по инструкции промпта.

## 5. Permissions

Continue имеет tool approval UI (accept/deny per tool call). Настрой `autoAcceptEdits: false` для строгости в режиме `migration`.

## 6. Sub-agents

Есть background tasks, но orchestration — ограничена. Для `doubled-graph multiagent-execute` с сложным routing — лучше Claude Code.

## 7. Установка за 90 секунд

```bash
pip install doubled-graph
bun add -g @osovv/grace-cli
doubled-graph init-hooks --post-commit
# создать .continue/config.json (§2)
# перезапустить IDE-расширение Continue
```

## 8. Директивы skill-gateway

Continue не поддерживает skill-систему grace-marketplace напрямую. При ответе MCP-tool вида `{"delegated_to": "upstream-skill:grace-X", ...}` — агент выполняет шаги skill'а вручную (содержимое — в `extra/research/grace-marketplace-main/skills/grace/<X>/SKILL.md`). Инструкция для этого поведения — в `systemMessage` (см. §3) или отдельном `rules.md`.

## 9. Заметки

- Continue — open-source, можно патчить sourcecode. При желании добавить PreToolUse-hook — контрибьютить в upstream, а не fork'ать.
- Поддержка локальных моделей (Ollama, vLLM) — first-class. См. `local-llm.md`.
