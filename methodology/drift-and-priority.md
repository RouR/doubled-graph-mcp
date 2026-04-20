# Политика дрейфа и приоритета

**Дрейф** — расхождение между **declared graph** (`docs/knowledge-graph.xml` + `docs/development-plan.xml`) и **computed graph** (строится `codegraphcontext` из AST).

В upstream grace-marketplace такого разделения нет — только declared, проверяется через `doubled-graph lint` (синтаксическая целостность). **Политика ниже — расширение doubled-graph.**

---

## Два режима

Хранятся в `AGENTS.md` в блоке между `<!-- doubled-graph:phase:start -->` и `<!-- doubled-graph:phase:end -->`:

```markdown
<!-- doubled-graph:phase:start -->
## doubled-graph phase
phase: post_migration
updated: 2026-04-18
<!-- doubled-graph:phase:end -->
```

Парсер — `src/doubled_graph/policy/phase.py`. Default при отсутствии блока: `post_migration`.

### Режим `migration`

**Ground-truth = код.** Артефакты догоняют.

**Когда используется:**
- Сценарий 2 (миграция legacy) — полностью;
- Крупные рефакторинги, где сначала переписываем код, потом актуализируем `docs/*.xml`.

**Политика разрешения дрейфа:** `doubled-graph refresh` обновляет `docs/*.xml` под код **без вопросов**. Пользователь ревьюит diff артефактов, а не код.

**Approval-gates остаются** (принцип 2): решение «что стало частью продукта» подписывает человек, просто оно теперь формулируется как «одобряю обновлённый development-plan.xml» вместо «одобряю новую функцию».

### Режим `post_migration` (default)

**Ground-truth = артефакты.** Расхождение — подозрение на баг или новое неодобренное требование.

**Когда используется:**
- Сценарий 1 (новый проект) — с первого шага.
- Сценарий 3 (поддержка) — после завершения миграции.

**Политика разрешения дрейфа:**

1. `doubled-graph detect_changes` нашёл расхождение.
2. `doubled-graph` / промпт `on-drift-detected.md` смотрит `git log -1 --name-only`: был ли код в этом файле изменён в последнем коммите?
3. **Да:** спрашивает пользователя — «Новое требование или баг?»
   - **«Новое требование»** → полный цикл: `doubled-graph plan` → approval → `doubled-graph execute` → код/артефакты обновляются вместе.
   - **«Баг»** → `doubled-graph fix` приводит код обратно под контракт.
   - **«Не знаю»** → запись в `docs/DRIFT.md`, модуль блокируется для правок ИИ до разрешения.
4. **Нет (код не менялся, но drift есть)** → audit-запись в `DRIFT.md`, это tooling-проблема или внешний процесс (автогенератор, миграция библиотеки).

---

## Переключение режима

**Миграция завершена → переход в `post_migration`.** Критерии:

- `doubled-graph lint` проходит;
- `doubled-graph detect_changes --scope all` возвращает пустой drift;
- все критические модули имеют MODULE_CONTRACT и минимум один `V-M-*`.

**Процедура:**

```bash
# Через инструмент (рекомендовано):
doubled-graph phase set post_migration --reason "migration complete after M42"

# Или руками: правка блока в AGENTS.md + commit.
```

Инструмент меняет блок и создаёт commit с сообщением, содержащим causes («reason»). Ревью PR — обычный git-review.

**Откат `post_migration` → `migration`** возможен, но **обязывает** сопроводить запись в `docs/DRIFT.md`:

```markdown
# docs/DRIFT.md

## 2026-04-18 — откат в режим migration
**Причина:** внедряем новую библиотеку Y, которая затрагивает 17 модулей;
артефакты будут отставать от кода 2–3 дня до стабилизации.
**Ожидаемое окончание:** 2026-04-21.
**Ответственный:** <имя>.
```

**Почему** откат не бесплатен: в `migration` политика молчаливо подписывает любые code-changes в артефакты. Если включать её без необходимости — теряем гарантию согласованности.

---

## Источники дрейфа

| Источник | Типичный случай | Кто инициирует обнаружение |
|---|---|---|
| Ручная правка человеком | фикс bug на production, сделанный без ИИ | `post-commit` hook → `analyze` → следующий `detect_changes` |
| ИИ сгенерировал код, но не обновил артефакт | баг промпта или skill'а (слишком короткий контекст) | `doubled-graph reviewer` в профиле `safe` должен ловить; иначе всплывает в CI gate |
| Внешний процесс (codegen, migration) | `prisma migrate`, `grpc-gen` создают код | `post-commit` hook фиксирует файлы, `detect_changes` показывает `code_without_module` |
| Одобренное новое требование, частично реализованное | середина работы над фичей | ожидаемо; `DRIFT.md` помечает «in progress: UC-042» |

---

## Типы дрейфа и разрешение

(Выход `doubled-graph detect_changes` — см. `../docs/TOOLS.md § 4.2`.)

### `code_without_module`
Функция/класс существует в коде, не покрыт ни одним `M-*`.

**Миграция:** `doubled-graph refresh` создаёт новый `M-*` или добавляет файл в существующий, по эвристике кластеров.
**Post_migration:** спросить — новое требование? Если да → `doubled-graph plan`. Если баг (код попал случайно) → удалить код или явно отнести к dev/test.

### `module_without_code`
`M-*` в `development-plan.xml` есть, файлов нет.

**Миграция:** отметить `M-*` как `deprecated`, по согласованию удалить.
**Post_migration:** ожидаемо в начале работы над фичей. Если осталось «долго» (настраиваемо, например > 7 дней) — пингуем.

### `contract_mismatch`
Декларированная сигнатура `validateUser(req: Request): User | null`, реальная `validateUser(req: Request, opts?: Options)`.

**Миграция:** обновить контракт под код.
**Post_migration:** спросить — обновляем артефакт (новое требование) или откатываем код (баг)?

### `stale_crosslinks`
CrossLink `M-A → M-B`, но в CGC нет вызовов между их файлами.

**Миграция:** удалить CrossLink.
**Post_migration:** скорее всего рефакторинг разорвал связь случайно — задокументировать и удалить CrossLink, проверить что это не потерянная функциональность.

### `missing_verification`
`M-*` имеет код, но нет `V-M-*`.

**Обоих режимов одинаково:** добавить `V-M-*`; на критических модулях — блокирующий gate.

### `markup_missing`
В файле нет MODULE_CONTRACT / MODULE_MAP.

**Миграция:** добавить; это основная активность `04-markup-codebase.md`.
**Post_migration:** обычно ошибка генерации — добавить разметку вручную (по шаблону `language-adapters/<язык>.md`) и проверить `doubled-graph lint`.

---

## Grace lint, CI и gates

`doubled-graph detect_changes` — **не** блокирует коммит сам по себе (соображения UX, см. `../docs/HOOKS.md §1.2`). Блокировкой занимается:

- **pre-commit (опциональный) + CI**: `doubled-graph lint` + `doubled-graph detect_changes --scope staged`. Если drift > 0 и **не записан** в `DRIFT.md` — merge блокируется.
- **pre-merge gate** (определяется в `verification-plan.xml`): полный `detect_changes --scope compare --base-ref main` + прогон тестов.

Эти gate-ы **обязательны** для всех проектов (профилей глубины в doubled-graph нет — см. `auto-scaling.md`).

---

## Logs privacy

Привязано сюда, потому что phase-решение влияет на privacy:

- В `migration` лог-события с `belief` могут содержать «что ИИ думал про этот legacy-код» — включая PII, прочитанный ИИ из legacy. **Маскировать агрессивнее.**
- В `post_migration` код уже ревьюирован, меньше шансов, что ИИ «запомнил» чужой PII в своём belief. **Стандартный режим маскирования.**

Правила маскирования — в `runtime-adapters/*.md` (privacy-секции).

---

## Что `DRIFT.md` должен содержать

```markdown
# DRIFT.md

## Текущие открытые дрейфы

### D-001 — M-AUTH-VALIDATE: contract_mismatch (2026-04-17)
- **Что:** реальная сигнатура `validateUser(req, opts?)` расходится с контрактом (1 аргумент).
- **Причина:** добавление opcional opts без прохождения через `doubled-graph plan`.
- **Статус:** пользователь не решил — новое требование или откат.
- **Owner:** @alice.
- **Deadline:** 2026-04-20.

## История закрытых

### D-000 — M-BILLING-STRIPE: stale_crosslinks (2026-04-10 → closed 2026-04-12)
- Решение: рефакторинг разорвал связь преднамеренно, CrossLink удалён.
```

Формат — произвольный markdown; шаблон выше — рекомендация, не требование.
