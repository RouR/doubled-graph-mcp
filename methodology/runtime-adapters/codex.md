# Runtime adapter: Codex (OpenAI)

## 1. MCP

OpenAI Codex CLI и Codex Web поддерживают MCP (spec-2025-03-26 на апрель 2026). Транспорт stdio.

Конфиг: `~/.codex/mcp.json` (глобально) или `.codex/mcp.json` в репо.

## 2. Регистрация `doubled-graph`

`.codex/mcp.json`:

```json
{
  "mcpServers": {
    "doubled-graph": {
      "command": "python",
      "args": ["-m", "doubled_graph"]
    }
  }
}
```

## 3. Rules / instructions

Codex читает `AGENTS.md` в корне репо (совпадает с grace-marketplace конвенцией — приятное совпадение). Содержимое `AGENTS.md`, сгенерированное `doubled-graph init`, Codex воспримет нативно.

Наш `phase`-блок `<!-- doubled-graph:phase:start -->` для Codex — прозрачный комментарий (не интерпретируется как инструкция). Парсит его только `doubled-graph`. ✓

Дополнительные промпты (наши из Phase 3) — через `~/.codex/prompts/` (custom slash-команды).

## 4. Hooks

**Codex hooks — ограниченные.** На 2026-04: только OnSessionStart и custom preprocessor на tool responses (не равно PostToolUse).

**Митигация** — та же, что в Cursor (см. `cursor.md §4`): полагаемся на `post-commit` baseline и на явный вызов `analyze` в промптах.

## 5. Permissions UI

Codex имеет approval mode (suggest / auto-edit / full-auto):
- **suggest**: каждая правка подтверждается — default, рекомендуется для режима `migration`.
- **auto-edit**: авто-применение mut-tools с approval только на shell.
- **full-auto**: минимум approval — **не рекомендуется** для doubled-graph без строгого gate в CI.

## 6. Установка за 60 секунд

```bash
pip install doubled-graph
bun add -g @osovv/grace-cli
doubled-graph init-hooks --post-commit
# создать .codex/mcp.json (§2)
codex  # или codex-web
```

## 7. Директивы skill-gateway

Codex не имеет native skill-системы. Когда MCP возвращает `{"delegated_to": "upstream-skill:grace-X", ...}`, агент должен **вручную выполнить шаги skill'а**, читая их из `extra/research/grace-marketplace-main/skills/grace/<X>/SKILL.md` (или от установленной локально копии). Пропиши это поведение в `AGENTS.md` репо — одного абзаца хватит.

## 8. Ограничения

- Codex из web-интерфейса работает в ephemeral sandbox — доступ к локальному MCP-серверу невозможен. Используй Codex CLI локально.
- Codex full-auto с OpenAI frontier моделями не всегда соблюдает 10 принципов — требуется explicit reminder в `AGENTS.md`.
