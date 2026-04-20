# for-ai-existing-project — пакет для сценария «миграция»

**Этот каталог — точка входа для ИИ-ассистента**, который будет мигрировать существующий проект на методологию doubled-graph.

---

## Критически важное правило миграции

**В режиме `migration` код = ground-truth, артефакты догоняют.** Никаких семантических правок под видом разметки. Один markup-commit = только якоря и комментарии, `git diff` должен быть **чисто декларативным**.

---

## Чтение (в порядке)

1. **Энтри-промпт** — [../prompts/migrate-existing-project/00-entry-prompt.md](../prompts/migrate-existing-project/00-entry-prompt.md).
2. **Принципы** — [../methodology/principles.md](../methodology/principles.md).
3. **Workflow scenario 2** — [../methodology/workflow.md#сценарий-2-миграция-существующего](../methodology/workflow.md#сценарий-2-миграция-существующего).
4. **Drift-политика** — [../methodology/drift-and-priority.md](../methodology/drift-and-priority.md). **Читать внимательно** — в миграции политика особая.
5. **По шагам:**
   - [../prompts/migrate-existing-project/01-discover.md](../prompts/migrate-existing-project/01-discover.md)
   - [../prompts/migrate-existing-project/02-reconstruct-intent.md](../prompts/migrate-existing-project/02-reconstruct-intent.md)
   - [../prompts/migrate-existing-project/03-draft-plan.md](../prompts/migrate-existing-project/03-draft-plan.md)
   - [../prompts/migrate-existing-project/04-markup-codebase.md](../prompts/migrate-existing-project/04-markup-codebase.md) — **критичный шаг, не торопись**.
   - [../prompts/migrate-existing-project/05-verification-and-logs.md](../prompts/migrate-existing-project/05-verification-and-logs.md)
   - [../prompts/migrate-existing-project/06-validation-gates.md](../prompts/migrate-existing-project/06-validation-gates.md)

---

## Справочник

- **Язык проекта** → [../methodology/language-adapters/](../methodology/language-adapters/).
- **IDE** → [../methodology/runtime-adapters/](../methodology/runtime-adapters/).
- **Артефакты** → [../methodology/artifacts.md](../methodology/artifacts.md).
- **DRIFT.md шаблон** → секция в [drift-and-priority.md § Что `DRIFT.md` должен содержать](../methodology/drift-and-priority.md).

---

## Правила, которые ИИ часто нарушает (следи за собой)

1. **Не меняй логику кода во время разметки.** Если соблазняет «заодно починить этот bug» — **не делай**. Фикс — после миграции, отдельным коммитом, по полному циклу.
2. **Не додумывай намерение.** Если по коду+тестам+README не ясно, что делает модуль — **спроси пользователя**, не пиши guess в `requirements.xml`.
3. **Не пропускай `doubled-graph refresh` после разметки модуля.** Declared должен синхронизироваться с фактом разметки.
4. **Не переключай phase самостоятельно.** Только человек. Даже если все gate'ы зелёные, предложи переключение, жди подтверждения.
5. **Не игнорируй `DRIFT.md`.** Если там открытые записи — блок для финального `06-validation-gates`.

---

## Ожидаемый выход после завершения

- `AGENTS.md` с phase-блоком `post_migration` (переключили в финале).
- `docs/*.xml` — все 6 файлов, **consistent** с кодом.
- Весь код размечен (`doubled-graph lint` ✓).
- `doubled-graph detect_changes --scope all` → пусто (или только допустимые исключения в DRIFT.md).
- Hooks установлены.
- Все критические `V-M-*` прогоняются.
- `docs/DRIFT.md` — либо пустой, либо с явно принятыми limitations с owner/deadline.
