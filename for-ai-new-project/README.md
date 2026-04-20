# for-ai-new-project — пакет для сценария «новый проект»

**Этот каталог — точка входа для ИИ-ассистента**, который будет создавать новый проект по методологии doubled-graph.

Всё, что ИИ нужно прочитать, — указано ниже по порядку. Не пропускай шаги.

---

## Чтение (в порядке)

1. **Энтри-промпт** — [../prompts/new-project/00-entry-prompt.md](../prompts/new-project/00-entry-prompt.md). Вставь пользователю, жди его старта.
2. **Принципы** (для справки, чтобы не нарушать) — [../methodology/principles.md](../methodology/principles.md).
3. **Workflow scenario 1** — [../methodology/workflow.md#сценарий-1-новый-проект](../methodology/workflow.md#сценарий-1-новый-проект).
4. **По шагам:**
   - [../prompts/new-project/01-intent-interview.md](../prompts/new-project/01-intent-interview.md)
   - [../prompts/new-project/02-requirements.md](../prompts/new-project/02-requirements.md)
   - [../prompts/new-project/03-technology.md](../prompts/new-project/03-technology.md)
   - [../prompts/new-project/04-development-plan.md](../prompts/new-project/04-development-plan.md)
   - [../prompts/new-project/05-verification-plan.md](../prompts/new-project/05-verification-plan.md)
   - [../prompts/new-project/06-generate.md](../prompts/new-project/06-generate.md)
   - [../prompts/new-project/07-post-init-sync.md](../prompts/new-project/07-post-init-sync.md)

---

## По ходу работы — справочник

- **Язык проекта** → [../methodology/language-adapters/](../methodology/language-adapters/) (выбери свой).
- **IDE** → [../methodology/runtime-adapters/](../methodology/runtime-adapters/) (выбери свой).
- **Формат артефактов** → [../methodology/artifacts.md](../methodology/artifacts.md).
- **Approval-точки** → [../methodology/approval-checkpoints.md](../methodology/approval-checkpoints.md).
- **Роли (кто что одобряет)** → [../methodology/roles.md](../methodology/roles.md).

---

## Критические правила (не нарушать)

1. **Phase в `AGENTS.md` ставь `post_migration` сразу после `doubled-graph init`.** Новый проект рождается согласованным, нет миграции.
2. **Не пропускай approval-gates.** Даже если кажется, что «всё ясно».
3. **Перед любой правкой уже созданного файла** — [../prompts/maintenance/on-before-edit.md](../prompts/maintenance/on-before-edit.md).
4. **После завершения генерации** — переходи в поток maintenance, не продолжай «создавать» в режиме new-project.

---

## Ожидаемый выход после завершения

- `docs/*.xml` — все 6 файлов заполнены.
- `AGENTS.md` с phase-блоком `post_migration`.
- Код в `src/` с разметкой (MODULE_CONTRACT, CONTRACT:fn, BLOCK_*, CHANGE_SUMMARY).
- Тесты запускаются (минимум — `V-M-*` для critical модулей).
- `.doubled-graph/` с кэшами и логами.
- `.git/hooks/post-commit` установлен.
- Первый `git commit` с baseline-сообщением.
