# for-ai-maintenance — пакет для ежедневной поддержки

**Этот каталог — для ИИ-агента, который работает в проекте, уже прошедшем сценарий «новый проект» или «миграцию» (см. `methodology/workflow.md`).**

Режим `AGENTS.md` — обычно `post_migration` (если иначе — см. [drift-and-priority.md](../methodology/drift-and-priority.md)).

---

## Чтение (ссылки, активируются по триггерам)

### Перед правкой любого кода
→ [../prompts/maintenance/on-before-edit.md](../prompts/maintenance/on-before-edit.md).

**Триггер:** намерение изменить существующую функцию/класс/модуль.
**Обязательная операция:** `doubled-graph.impact(target, direction="upstream")`.
**Если `risk.level ∈ {HIGH, CRITICAL}`** — остановись, покажи, жди подтверждения.

### После правки, до коммита
→ [../prompts/maintenance/on-after-edit.md](../prompts/maintenance/on-after-edit.md).

**Последовательность:** `analyze` → `doubled-graph refresh --scope targeted` (если семантика) → `detect_changes --scope staged` → `doubled-graph lint` → тесты → commit.

### Обнаружен дрейф
→ [../prompts/maintenance/on-drift-detected.md](../prompts/maintenance/on-drift-detected.md).

**Триггер:** `detect_changes` вернул непустой drift.
**В `migration`:** `doubled-graph refresh`, diff ревью, commit.
**В `post_migration`:** ask user per drift type (new req / bug / drift unknown).

### После ручной правки человеком
→ [../prompts/maintenance/on-user-manual-edit.md](../prompts/maintenance/on-user-manual-edit.md).

**Триггер:** файлы изменены без участия ИИ (коммит от человека, DG-Authored: human/mixed).

---

## Hooks (автоматика)

Установлены (или должны быть — `doubled-graph init-hooks --all`):

1. **`git post-commit`** — `doubled-graph analyze --mode incremental` автоматически после каждого коммита.
2. **Claude Code `PostToolUse`** (если IDE — Claude Code) — `doubled-graph analyze` после каждой Edit/Write tool-use.
3. **`prepare-commit-msg`** (опц.) — добавляет `DG-Authored: ai | human | mixed` trailer.

См. [../docs/HOOKS.md](../docs/HOOKS.md) для деталей.

---

## Что ИИ **не делает** в maintenance-режиме

- Не создаёт новые `M-*` модули без полного цикла `doubled-graph plan` → approval.
- Не меняет контракты существующих модулей без подтверждения — это новое требование.
- Не переключает phase в `AGENTS.md`.
- Не удаляет записи из `DRIFT.md` без resolution.
- Не пушит / не мёрджит — пользователь.

---

## Fallback'и (важно)

Если инструменты недоступны:

- **`doubled-graph.context` вернул NOT_IMPLEMENTED_MVP** → `doubled-graph file show <path> --contracts --blocks` + `doubled-graph module show <M-id>`.
- **`doubled-graph.detect_changes` вернул NOT_IMPLEMENTED_MVP** → `doubled-graph refresh --dry-run` + ручной `git diff docs/` для declared-side; `doubled-graph analyze --force` для computed-side; сравнение руками. Явно предупреди пользователя: «в MVP detect_changes не реализован полностью, сверка упрощена».
- **`doubled-graph.impact` вернул partial** → прочти `development-plan.xml` напрямую, найди `critical-path` атрибут на затронутых DataFlow — если targeted module в них, помечай risk как CRITICAL независимо от count.
- **`grace` CLI недоступен** → `AGENTS.md`, `docs/*.xml` парсим руками через Read.

См. [QUESTIONS_FOR_REVIEW.md § C](../QUESTIONS_FOR_REVIEW.md) для known limitations MVP.
