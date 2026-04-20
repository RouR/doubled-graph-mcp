# Runtime adapter: Cursor

## 1. MCP

- Поддерживает MCP (stdio) с 2025 года (подробности — в official docs).
- Конфиг: `.cursor/mcp.json` в репо (коммитится) или глобальный `~/Library/Application Support/Cursor/mcp.json`.

## 2. Регистрация `doubled-graph`

`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "doubled-graph": {
      "command": "python",
      "args": ["-m", "doubled_graph"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Перезапусти Cursor. Проверь: в Cursor Composer tool-calls теперь видят `doubled-graph.analyze`, `doubled-graph.impact` и т. д.

## 3. Skills / rules

Cursor использует `.cursor/rules/*.mdc` вместо skills. Чтобы подключить наши промпты doubled-graph, скопируй промпт в `.cursor/rules/`:

```
.cursor/rules/
├── doubled-graph-maintenance.mdc    ← frontmatter alwaysApply: true
└── doubled-graph-reference.mdc
```

Содержимое — markdown с frontmatter:

```markdown
---
description: doubled-graph maintenance workflow
alwaysApply: true
---

# doubled-graph — on-before-edit

Перед любой правкой функции/класса:
1. Вызови `doubled-graph.impact(target=<name>, direction="upstream")`.
2. Если `risk.level ∈ {HIGH, CRITICAL}` — остановись, покажи risk.reasons, жди подтверждения.
...
```

`grace-marketplace` skills **из Claude Code не переносятся напрямую**. Нужно либо переписать их как `.mdc` rules, либо обращаться к ним через `grace` CLI в Bash-tool.

## 4. Hooks

**Cursor НЕ поддерживает PostToolUse / PreToolUse hooks** (на апрель 2026). Это существенное ограничение: computed graph отстаёт от кода между коммитами.

**Митигация:**
- Baseline `post-commit` hook (устанавливается `doubled-graph init-hooks --post-commit`) работает: после `git commit` из терминала внутри Cursor или снаружи — analyze запустится.
- В промптах Cursor-агента явно рекомендуется: перед `impact` сначала дёрнуть `analyze --mode incremental --paths <touched>`, если ИИ недавно редактировал файлы. Это руководство — в `prompts/maintenance/on-before-edit.md`.

## 5. Permissions UI

Cursor имеет auto-accept settings (per-tool allow/deny). В команде doubled-graph рекомендуется:
- `Edit` — прompt (не auto-accept);
- `Write` — prompt;
- `Bash` — prompt (для `git` и shell-команд);
- `doubled-graph.impact` / `analyze` / `context` — auto-accept (read-only с точки зрения кода);
- `doubled-graph.detect_changes` — auto-accept.

## 6. Sub-agents

В Cursor есть background agents. Для `doubled-graph multiagent-execute` используй их как workers; coordination — через файлы в `docs/operational-packets.xml` (как у upstream).

## 7. Установка за 90 секунд

```bash
# 1. Инструменты
pip install doubled-graph
bun add -g @osovv/grace-cli

# 2. Baseline hook
doubled-graph init-hooks --post-commit

# 3. Cursor MCP — создать .cursor/mcp.json (§2) и перезапустить Cursor

# 4. Скопировать наши rules из prompts/ в .cursor/rules/ вручную (Phase 3)
```

## 8. Известные issues

- Нет PostToolUse hooks → см. §4.
- Cursor иногда кэширует MCP-tool list; при изменении `.mcp.json` — полный перезапуск приложения.
- Background agents могут использовать отличающуюся модель от интерактивной сессии — убедись, что у обоих есть доступ к doubled-graph.

## 9. Директивы skill-gateway

Когда `doubled-graph.refresh / init / plan / …` (MCP-tool) возвращает `{"delegated_to": "upstream-skill:grace-X", ...}`, Cursor **не триггерит skill автоматически** (skill-system как в Claude Code нет). В `.cursor/rules/doubled-graph.mdc` добавь инструкцию:

> Если MCP-tool вернул `delegated_to: upstream-skill:grace-X`, выполни шаги этого skill вручную, читая `extra/research/grace-marketplace-main/skills/grace/<X>/SKILL.md` как процедуру. Если skill отсутствует локально — сообщи пользователю и укажи установочную команду.

Альтернатива — переписать каждый нужный skill как `.cursor/rules/grace-X.mdc` (`alwaysApply: false`), и триггерить через `@grace-X` в промпте агента.

## 10. Разрыв с Claude Code

Что **теряется** при переходе с Claude Code на Cursor:
- Auto-refresh computed graph между tool-use (нужен ручной `analyze`).
- `grace-marketplace` skills не работают напрямую — rewrite в `.mdc`.
- Claude Opus-специфичные sub-agent-фичи доступны только если модель Cursor = Opus.

Что **сохраняется**:
- `doubled-graph` MCP работает идентично.
- `grace` CLI работает (Bash-tool).
- 10 принципов и workflow — identical.
