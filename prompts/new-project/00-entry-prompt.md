# Новый проект — вход

**Скопируй этот текст в свой ИИ-ассистент** (Claude Code, Cursor, Continue, …) как первое сообщение после открытия пустого репозитория.

---

```
Я начинаю новый проект по методологии doubled-graph.

Твоя задача — провести меня через полный цикл от бизнес-идеи до работающего MVP с артефактами, разметкой, тестами, hooks.

Последовательность шагов — ровно такая:
1. Intent-интервью (prompts/new-project/01-intent-interview.md).
2. `doubled-graph init` — создание docs/*.xml и AGENTS.md. Phase сразу ставь `post_migration`.
   Глубина артефактов — всегда максимальная, никаких lite-вариантов (methodology/auto-scaling.md).
3. Requirements (prompts/new-project/02-requirements.md).
4. Technology (03-technology.md) — ДО написания development-plan.
5. Development plan (04-development-plan.md) — approval gate обязателен.
6. Verification plan (05-verification-plan.md).
7. Генерация кода по фазам (06-generate.md). Каждую фазу подтверждаем отдельно.
8. Первый `doubled-graph analyze --mode full`.
9. Установка hooks (07-post-init-sync.md).

Правила:
- Все approval-gates — явные. Не иди дальше без моего подтверждения.
- Перед любой правкой уже созданного файла — prompts/maintenance/on-before-edit.md.
- В конце каждой фазы кодогенерации — prompts/maintenance/on-after-edit.md.
- Используй инструменты: doubled-graph (MCP), grace-marketplace skills (`doubled-graph init`, `doubled-graph plan`, `doubled-graph execute`, `doubled-graph verification`).

Если что-то из этого неясно или отсутствует — скажи сейчас, прежде чем начать.

Начнём с шага 1 — Intent-интервью. Задай мне вопросы по файлу 01-intent-interview.md.
```

---

## Что произойдёт дальше

ИИ должен прочитать `prompts/new-project/01-intent-interview.md` и задать вопросы. Если ИИ **не** инициировал интервью — перезапусти с явной инструкцией: «Прочитай prompts/new-project/01-intent-interview.md и задавай вопросы по этому файлу».

## Если у тебя нет пустого репозитория

Используй `prompts/migrate-existing-project/00-entry-prompt.md` вместо этого.

## Если ИИ в IDE без tools+MCP

Методология не работает без MCP и tools — см. `methodology/README.md § Предусловия`. Подключи MCP (в IDE-adapter из `methodology/runtime-adapters/`) или смени IDE.
