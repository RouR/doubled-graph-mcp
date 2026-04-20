# on-drift-detected — обнаружен дрейф

**Целевая аудитория:** ИИ-ассистент.
**Триггер:** `doubled-graph.detect_changes()` вернул непустой drift.

См. также: `methodology/drift-and-priority.md`, `methodology/principles.md § Операционный паттерн — externalize state`.

---

## Externalize state

Drift из 5+ items, каждый — решение пользователя. К 7-му item локалка забудет первые. Журнал обязателен.

- Файл: `.doubled-graph/drafts/drift-session-<ISO>.md` — append-only.
- Поля per item: тип, target, время, user-decision (new-req / bug / defer), next action, status.
- Конец сессии — `Status: completed`, не удалять (audit trail). Детали формата — `methodology/principles.md § Операционный паттерн — externalize state`.

---

## Шаг 0 — определи режим

Читай `AGENTS.md` phase-блок.

- **`migration`** → иди в § A.
- **`post_migration`** → иди в § B.

---

## § A. Режим `migration`

Код — ground-truth. Артефакты догоняют. Всё просто:

**Шаг A.1 — `doubled-graph refresh`.**

```bash
doubled-graph refresh --scope targeted
```

Этот skill:
- обновит `docs/development-plan.xml` под реальные модули (добавит `code_without_module`, удалит `module_without_code`);
- обновит `docs/knowledge-graph.xml` (экспорты, CrossLinks);
- предложит создать новые `V-M-*` где `missing_verification`.

**Шаг A.2 — ревью diff артефактов.**

Покажи пользователю `git diff docs/`. Пользователь подтверждает одним из:
- «ок, коммить» → коммит `chore(refresh): sync docs after code changes`;
- «стоп, откати вот это» → правишь по инструкции.

**Шаг A.3 — возврат в `on-after-edit.md` шаг 4** (doubled-graph lint + тесты).

---

## § B. Режим `post_migration`

Артефакты — ground-truth. Дрейф — подозрение на баг или неодобренное требование.

Обрабатывай каждый тип drift отдельно.

### B.1 — `code_without_module`

Функция/класс в коде, не покрыт ни одним `M-*`.

**Действие:** спроси пользователя:

> Обнаружен код без модуля:
> - `<file>:<line> — <function/class>`
>
> Варианты:
>  (a) это новое требование — запускаю `doubled-graph plan` цикл для нового M-xxx;
>  (b) это баг (код не должен был попасть) — удаляю;
>  (c) вспомогательный dev/test код — выношу в `tests/` или `dev/` и помечаю исключением в `.grace-lint.json`;
>  (d) не знаю — пишу в `docs/DRIFT.md`, модуль-кандидат блокируется для дальнейших правок до решения.

Выполни выбор.

### B.2 — `module_without_code`

`M-*` есть в `development-plan.xml`, файлов нет.

**Действие:**
- Если модуль помечен `in-progress` в `DRIFT.md` с не истекшим deadline → молча пропусти (ожидаем реализации).
- Иначе спроси: `(a)` модуль устарел, помечаем `deprecated`; `(b)` забыли реализовать, создаём issue/задачу.

### B.3 — `contract_mismatch`

Реальная сигнатура ≠ декларированному контракту.

**Действие:** спроси:

> Контракт M-AUTH-VALIDATE.validateUser заявляет `(req: Request) -> User | null`.
> Фактическая сигнатура: `(req: Request, opts?: Options) -> User | null`.
>
> Варианты:
>  (a) новое требование (opts важен) — обновляю `development-plan.xml` через `doubled-graph plan` + `doubled-graph execute`;
>  (b) баг (opts случайно добавлен) — откатываю добавление opts через `doubled-graph fix`;
>  (c) не знаю — `DRIFT.md`.

### B.4 — `stale_crosslinks`

CrossLink `M-A → M-B` есть, но в computed нет вызовов между файлами.

**Действие:**
- Если это намеренный рефакторинг → удали CrossLink через `doubled-graph refresh --scope targeted --modules M-A` после подтверждения пользователя.
- Если подозрительно (неожиданная потеря связи) → `DRIFT.md`, спроси пользователя, не потерялась ли функциональность.

### B.5 — `missing_verification`

`M-*` есть код, нет `V-M-*`.

**Действие:**
- Критический модуль → предложи написать `V-M-*` сейчас; если пользователь отложит — блокируй `Gate G-pre-merge` в `verification-plan.xml` для этого модуля.
- Standard → создай черновик `V-M-*` через `doubled-graph verification`, пользователь ревьюит.
- Helper → запись в `DRIFT.md` как «verification pending» с low priority.

### B.6 — `markup_missing`

В файле нет MODULE_CONTRACT / MODULE_MAP.

**Действие:**
- Добавь разметку **руками**, следуя шаблону из `methodology/language-adapters/<lang>.md`. (Upstream `doubled-graph fix` skill может помочь с окружающим контекстом, но flag для автоматической вставки якорей — не часть его контракта.)
- Запусти `doubled-graph lint` для проверки.

---

## Шаг B.N — после обработки всех типов drift

1. Повтори `doubled-graph.detect_changes(scope="staged")`. Если всё ещё непусто — вернись к соответствующему §.
2. Если пусто → `on-after-edit.md` шаг 4.

---

## Записи в `docs/DRIFT.md`

Любой пункт с ответом «не знаю» создаёт/обновляет запись:

```markdown
## D-042 — M-AUTH-VALIDATE contract_mismatch (2026-04-18)

**Тип:** contract_mismatch.
**Обнаружено:** `doubled-graph detect_changes` в коммите `abc1234`.
**Суть:** контракт заявляет 1 аргумент, реальная сигнатура — 2.
**Решение откладывается пользователем. До решения — модуль M-AUTH-VALIDATE заблокирован для ИИ-правок.**
**Deadline:** 2026-04-22 (assumed).
**Owner:** <никто пока>.
```

Коммит отдельным коммитом: `docs(drift): register D-042 on M-AUTH-VALIDATE contract mismatch`.

---

## Шпаргалка (<1 KB)

```
ON-DRIFT:
read AGENTS.md phase
migration -> doubled-graph refresh --scope targeted; git diff docs/; user confirm; commit chore(refresh)
post_migration -> per drift type:
  code_without_module -> user: new req | bug | dev | drift
  module_without_code -> deprecated | create-issue
  contract_mismatch -> new req (`doubled-graph plan`) | bug (`doubled-graph fix`) | drift
  stale_crosslinks -> delete | drift (functionality-loss check)
  missing_verification -> write V-M-* | gate block
  markup_missing -> руками по language-adapter; doubled-graph lint
unknown -> DRIFT.md, block module for AI edits
re-run detect_changes until empty
goto on-after-edit step 4
```
