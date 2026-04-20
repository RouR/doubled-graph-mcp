# doubled-graph

**Методология разработки с ИИ-ассистентом.** Расширение публичной методологии GRACE ([osovv/grace-marketplace](https://github.com/osovv/grace-marketplace), MIT) тремя добавками: сценарий миграции legacy, политика дрейфа кода и артефактов, tool-agnostic runtime-слой.

Статус: **Phase 5 ready drafts** (apr 2026). Не финальный релиз. Ожидает ручное ревью пользователя + верификацию числовых фактов.

---

## TL;DR

- **Что даёт:** предсказуемость разработки с ИИ, автоматическая синхронизация кода и документации, обнаружение дрейфа.
- **Цена:** два внешних инструмента (grace-marketplace + doubled-graph) + разметка кода якорями + approval-gates.
- **Целевые модели:** локальные среднего размера (Qwen 3, DeepSeek V3, GLM-4.5, Llama 4). Frontier тоже работают.
- **Целевые IDE:** любой с MCP + tools (Claude Code, Cursor, Codex, Continue, Windsurf, Cline, aider, …).

---

## Первые 15 минут

```bash
# 1. Инструменты
bun add -g @osovv/grace-cli
pip install doubled-graph   # пока — `pip install -e ./doubled-graph`

# 2. Hooks в твоём репо
cd your-project
doubled-graph init-hooks --all

# 3. MCP-сервер в твоём IDE (пример для Claude Code — создать .mcp.json)
# Для других IDE: methodology/runtime-adapters/<твой>.md
```

Дальше — [for-humans/getting-started.md](for-humans/getting-started.md).

---

## Навигация

→ **[INDEX.md](INDEX.md)** — полная карта файлов.

Три быстрых входа:

| Кто ты | Куда идти |
|---|---|
| Человек, впервые слышу о GRACE | [for-humans/getting-started.md](for-humans/getting-started.md) |
| ИИ-ассистент, новый проект | [for-ai-new-project/](for-ai-new-project/) |
| ИИ-ассистент, мигрировать legacy | [for-ai-existing-project/](for-ai-existing-project/) |
| ИИ-ассистент, ежедневная поддержка | [for-ai-maintenance/](for-ai-maintenance/) |

---

## Философия — 1 экран

doubled-graph стоит на трёх идеях:

1. **Замысел первичен.** Любой код — следствие утверждённого `development-plan.xml`. Принципы: [methodology/principles.md](methodology/principles.md).
2. **Код — живой документ.** Семантическая разметка (якоря + контракты) делает код читаемым для ИИ, а hooks поддерживают синхронизацию код ↔ документация. Разметка: [methodology/artifacts.md § Разметка кода](methodology/artifacts.md).
3. **Два графа — declared и computed.** Первый пишется ИИ по замыслу (`docs/knowledge-graph.xml`), второй извлекается из AST (через [CodeGraphContext](https://github.com/Shashankss1205/CodeGraphContext)). Расхождение — автоматически detected (`doubled-graph detect_changes`). Политика: [methodology/drift-and-priority.md](methodology/drift-and-priority.md).

Всё остальное — как эти идеи применяются к новому проекту, миграции и ежедневной поддержке.

---

## Внешние зависимости

Методология **не tool-agnostic**. Требуется:

- **grace-marketplace** (Bun, MIT) — 14 skills + CLI `grace`. Источник: [osovv/grace-marketplace](https://github.com/osovv/grace-marketplace).
- **CodeGraphContext** (Python, MIT) — AST-парсинг для 19 языков. Подключается как зависимость через наш `doubled-graph`.
- **doubled-graph** (Python, MIT, **этот репозиторий**) — MCP-facade с 4 curated инструментами над CGC + grace CLI.

Источники задокументированы в [methodology/tools.md](methodology/tools.md).

**GitNexus не используется.** Лицензия PolyForm NC несовместима с публичной методологией — см. [methodology/tools.md § 5](methodology/tools.md).

---

## Лицензия

MIT. © 2026 doubled-graph methodology authors.

---

## Для рецензентов (Phase 5)

Читайте в порядке:

1. [extra/EXECUTION_PLAN.md](extra/EXECUTION_PLAN.md) — что было сделано автономно.
2. [extra/QUESTIONS_FOR_REVIEW.md](extra/QUESTIONS_FOR_REVIEW.md) — авто-решения, факты для веб-сверки, слабые места реализации.
3. [PLAN.md § Фаза 5](PLAN.md) — verify-pass чек-лист.
4. Выборочное чтение [methodology/](methodology/) + [prompts/](prompts/) + [docs/](docs/).

Критические места для глаз человека:
- интеграция doubled-graph с реальным CGC (не проверялась на живом вызове);
- числовые факты про модели/бенчмарки;
- подходящие ли fallback'ы в maintenance-промптах для MVP stubs.
