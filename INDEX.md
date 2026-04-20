# doubled-graph — навигатор

**Что искать → куда идти.**

---

## Быстрый старт

| Цель | Файл |
|---|---|
| «За 15 минут понять и попробовать» | [for-humans/getting-started.md](for-humans/getting-started.md) |
| «Понимать, почему так устроено» | [for-humans/deep-dive.md](for-humans/deep-dive.md) |
| «FAQ и edge cases» | [for-humans/FAQ.md](for-humans/FAQ.md) |

---

## Для ИИ-ассистента (три пакета)

| Сценарий | Пакет |
|---|---|
| Создать новый проект | [for-ai-new-project/](for-ai-new-project/) |
| Мигрировать существующий | [for-ai-existing-project/](for-ai-existing-project/) |
| Поддерживать уже мигрированный | [for-ai-maintenance/](for-ai-maintenance/) |

---

## Методология

| Тема | Файл |
|---|---|
| Точка входа для человека | [methodology/README.md](methodology/README.md) |
| 10 принципов | [methodology/principles.md](methodology/principles.md) |
| Скелет workflow + 3 сценария | [methodology/workflow.md](methodology/workflow.md) |
| XML-артефакты | [methodology/artifacts.md](methodology/artifacts.md) |
| Почему не масштабируем под размер (всегда max) | [methodology/auto-scaling.md](methodology/auto-scaling.md) |
| grace-marketplace + doubled-graph | [methodology/tools.md](methodology/tools.md) |
| Политика дрейфа и приоритета | [methodology/drift-and-priority.md](methodology/drift-and-priority.md) |
| Approval-gates + профили multiagent | [methodology/approval-checkpoints.md](methodology/approval-checkpoints.md) |
| Роли человек/ИИ | [methodology/roles.md](methodology/roles.md) |
| Language-адаптеры | [methodology/language-adapters/](methodology/language-adapters/) |
| Runtime-адаптеры (IDE) | [methodology/runtime-adapters/](methodology/runtime-adapters/) |

---

## Промпты (для ИИ)

| Группа | Директория |
|---|---|
| Новый проект | [prompts/new-project/](prompts/new-project/) (8 файлов) |
| Миграция | [prompts/migrate-existing-project/](prompts/migrate-existing-project/) (7 файлов) |
| Поддержка | [prompts/maintenance/](prompts/maintenance/) (4 файла) |

---

## doubled-graph (наш facade-MCP)

| Тема | Файл |
|---|---|
| Архитектура | [docs/SPEC.md](docs/SPEC.md) |
| Контракт 4 публичных tool'ов | [docs/TOOLS.md](docs/TOOLS.md) |
| Hooks (git + Claude Code + optional) | [docs/HOOKS.md](docs/HOOKS.md) |
| Исходник MVP | [src/doubled_graph/](src/doubled_graph/) |
| Smoke-тесты | [tests/](tests/) |

---

## Внутреннее (проектная метаинформация)

| Тема | Файл |
|---|---|
| План исследования и фаз | [PLAN.md](PLAN.md) |
| Claude Code инструкции | [CLAUDE.md](CLAUDE.md) |
| AGENTS.md (phase-блок для doubled-graph) | [AGENTS.md](AGENTS.md) |

---

## Пути для частых задач

### «Я хочу настроить проект»
1. [for-humans/getting-started.md](for-humans/getting-started.md) — для общего понимания.
2. [for-ai-new-project/](for-ai-new-project/) или [for-ai-existing-project/](for-ai-existing-project/) — для ИИ.
3. [methodology/runtime-adapters/](methodology/runtime-adapters/) — конфиг для твоего IDE.

### «Код в продакшне сломался, нужно найти что и откуда»
1. `doubled-graph context <symbol>` — 360-view.
2. Log по `correlation_id` или `anchor` → находишь цепочку.
3. `doubled-graph module show <M-id>` — контракт модуля.
4. Если нужна история — `git log <file>` + `CHANGE_SUMMARY` в файле.

### «Хочу ретроактивно применить методологию к legacy»
→ [for-ai-existing-project/](for-ai-existing-project/) + [prompts/migrate-existing-project/00-entry-prompt.md](prompts/migrate-existing-project/00-entry-prompt.md).

### «Модели на локальном железе, что учесть»
→ [methodology/runtime-adapters/local-llm.md](methodology/runtime-adapters/local-llm.md).

