# Runtime adapter: Claude Code

**Целевой клиент** методологии. Hooks + permissions UI + skills — все рычаги управляемой автономии доступны.

## 1. MCP

- Протокол: 2025-03-26 (на 2026-04).
- Транспорт: stdio JSON-RPC (локально).
- Где конфиг: `~/.claude/config.json` или `.mcp.json` в репо.

## 2. Регистрация `doubled-graph`

В `.mcp.json` на уровне репо (коммитится):

```json
{
  "mcpServers": {
    "doubled-graph": {
      "command": "python",
      "args": ["-m", "doubled_graph"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

Либо глобально (`~/.claude/config.json`), если хочешь один сервер на все проекты — тогда `cwd` должен быть передан явно.

Проверить подключение: в Claude Code выполни `/mcp` — doubled-graph должен появиться с 4 tool'ами.

## 3. Skills

Устанавливаются из `osovv/grace-marketplace`:

```bash
claude --skills github:osovv/grace-marketplace
```

Проверить: `/skills` должен показать `grace-*`-скиллы.

Установить **наши** промпты (Phase 3) как skills — вручную, копированием в `~/.claude/skills/doubled-graph/` или через `skill-creator`:

```
.claude/skills/doubled-graph/
├── new-project.md
├── migrate-existing.md
└── maintenance.md
```

## 4. Hooks

Claude Code поддерживает **PreToolUse**, **PostToolUse**, **OnSessionStart**, **OnUserPromptSubmit** и другие. Документировано в настройках.

Автоматическая установка через наш инструмент:

```bash
doubled-graph init-hooks --claude-code
```

Он добавляет блок в `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "doubled-graph analyze --mode incremental --paths \"$CLAUDE_FILE_PATH\" --silent"
          }
        ]
      }
    ]
  }
}
```

Дополнительно в том же `settings.json` — git `post-commit` для доналичия (если проект открывается впервые):

```json
{
  "hooks": {
    "OnSessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "doubled-graph init-hooks --post-commit --dry-run" }
        ]
      }
    ]
  }
}
```

`--dry-run` печатает, что поставил бы; сам `--post-commit` — установка.

## 5. Permissions UI

Claude Code показывает pre-tool-use approval для каждого Edit/Write/Bash. Это **уже** даёт остановку для HIGH/CRITICAL — человек видит diff перед правкой.

Дополнительно в `prompts/maintenance/on-before-edit.md` (Phase 3) ИИ обязан вызвать `doubled-graph impact` и при risk ≥ HIGH **явно** попросить подтверждение. Это дублирует UI, но даёт текстовое объяснение («вот что сломается»).

## 6. Sub-agents

Claude Code поддерживает sub-agents (`Agent` tool). Используется в `doubled-graph multiagent-execute` skill (workers + reviewers). Настройка — `~/.claude/agents/`.

## 7. Установка за 60 секунд

```bash
# 1. Инструменты
pip install doubled-graph
bun add -g @osovv/grace-cli

# 2. Hooks
cd /path/to/your/repo
doubled-graph init-hooks --all

# 3. MCP в Claude Code
# Создаём .mcp.json (см. §2) и перезапускаем Claude Code
```

Проверка: `/mcp` → `doubled-graph` present → `analyze`, `impact`, `context`, `detect_changes` доступны.

## 8. Известные issues

- **`$CLAUDE_FILE_PATH`** в PostToolUse-матчере работает для single-file tools (Edit, Write). Для MultiEdit — срабатывает N раз (по одному на файл). OK.
- **Settings merge.** При активной сессии изменения в `.claude/settings.json` требуют перезапуска Claude Code. `doubled-graph init-hooks --claude-code` поэтому рекомендует перезапустить.

## 9. Директивы skill-gateway

Когда агент вызывает `doubled-graph.refresh / init / plan / …` через MCP, tool **не делает работу сам** — возвращает JSON вида:

```json
{"delegated_to": "upstream-skill:grace-refresh", "args": {...}, "instructions": "Trigger the upstream `grace-refresh` skill..."}
```

**В Claude Code** это естественно: агент читает `delegated_to`, находит совпадающий skill в `/skills` listing (установленных через grace-marketplace), и триггерит его через встроенный **Skill tool**. Если skill отсутствует — агент сообщает пользователю `skill grace-refresh не установлен; установи через claude --skills github:osovv/grace-marketplace`.

## 10. Поддержка русского

Claude Code корректно работает с русскими промптами и файлами. `CLAUDE.md` в текущем репозитории — пример (написан на английском, но методологические файлы и skills могут быть на русском).
