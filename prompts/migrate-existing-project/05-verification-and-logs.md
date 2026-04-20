# 05 — Verification and logs

**Роль ИИ:** привязать существующие тесты к `V-M-*` записям, добавить structured logs (минимально).

---

## Externalize state

Продолжает `.doubled-graph/drafts/plan-draft.md` (из шага 03) и `markup-progress.md` (из шага 04). Добавь секции `V-M-* bindings` и `logs-upgrades-needed` в `plan-draft.md`:

```markdown
## V-M-* bindings (step 05)
- V-M-AUTH-VALIDATE-01 → tests/test_auth_validate.py::test_valid_jwt (existing, bound)
- V-M-AUTH-VALIDATE-02 → PENDING-TO-WRITE (no existing test; DRIFT.md D-TEST-003)
- V-M-PAYMENTS-CHARGE-01 → tests/integration/test_stripe.py (existing)

## Logs upgrades needed (critical modules only)
- M-AUTH-VALIDATE: add anchor, marker VALIDATE_SUCCESS in validate_user BLOCK_DECODE_JWT
- M-PAYMENTS-CHARGE: add PAYMENT_SUCCESS, PAYMENT_FAIL markers
- ...

## Privacy audit findings
- src/logging/formatter.py:42 — unmasked email in info log → FIX-NEEDED
- src/auth/jwt.py:78 — raw token in error log → FIX-NEEDED (severe)
```

Финальный рендеринг `docs/verification-plan.xml` — из этих секций. Это важнее, чем в new-project: в legacy-миграции ошибок маскирования PII в логах может быть десятки, легко потерять часть.

---

## Часть A — Verification

**Шаг A.1** — для каждого M-* из `development-plan.xml`:
- найди существующие тесты для этого модуля (эвристика: тесты, которые импортируют/вызывают функции модуля);
- заведи `V-M-*` запись в `verification-plan.xml`.

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Source kind="existing" file="tests/test_auth_validate.py::test_valid_jwt" />
  <Command>pytest tests/test_auth_validate.py::test_valid_jwt -v</Command>
  <Scenario>valid JWT returns User</Scenario>
  <Markers>
    <!-- пустой на момент привязки; заполнится после добавления structured logs -->
  </Markers>
</Verification>
```

**Шаг A.2** — для M-* **без тестов**:
- если critical → **не** запускай разработку тестов в режиме миграции. Запиши в `docs/DRIFT.md` как блокер для завершения миграции: `D-TEST-XXX: M-*** без verification, требует тест до переключения в post_migration`.
- если standard → рекомендуется добавить. Помечай как TODO в `verification-plan.xml`:
  ```xml
  <Verification id="V-M-FOO-01" module="M-FOO" kind="unit">
    <Status>pending-to-write</Status>
    <Command>TBD</Command>
  </Verification>
  ```
- если helper → пропускай.

**Шаг A.3 — gates.**

Если проект уже имеет CI (`.github/workflows/ci.yml`) — не переписывай его. Добавь в `verification-plan.xml § Gate G-pre-merge` ссылки на существующие commands:

```xml
<Gate id="G-pre-merge" kind="required">
  <Check>doubled-graph lint</Check>
  <Check>doubled-graph detect_changes --scope compare --base-ref main</Check>
  <Check>pytest</Check>  <!-- ← существующий тест-запуск -->
  <Check>ruff check .</Check>  <!-- ← существующий linter -->
</Gate>
```

---

## Часть B — Structured logs

В легаси проекта часто `print` / не-structured logging. **Миграция НЕ требует** переписывать все логи сразу.

**Минимум миграции** (обязательно):

1. Для **критических** модулей — обновить log-строки в точках, связанных с verification-markers. Один раз, аккуратно.

   Пример: функция `validateUser`, marker `VALIDATE_SUCCESS` должен порождаться.

   Было:
   ```python
   logger.info("user validated: %s", user.id)
   ```

   Стало:
   ```python
   logger.info(
       "validate_success",
       extra={
           "anchor": "validateUser:BLOCK_DECODE_JWT",
           "module": "M-AUTH-VALIDATE",
           "requirement": "UC-001",
           "marker": "VALIDATE_SUCCESS",
           "user_id": user.id,
       }
   )
   ```

   Это **семантическая правка** (меняет формат лога). Делается **осознанно**, с approval'ом пользователя, коммит отдельно:
   ```
   feat(M-AUTH-VALIDATE): structured log with marker
   ```

   В режиме миграции это НЕ запрещено, но должно идти **после** markup-коммита, не смешиваться.

2. Для **standard / helper** модулей — логи оставляем как есть. Пометь в DRIFT.md, что они не структурированные, — это нормально, миграция логов не блокирует переключение phase.

---

## Часть C — Privacy аудит

Прогони grep-поиск по critical-модулям на паттерны:
- hardcoded secrets;
- токены в логах;
- unmasked PII (email, phone, card numbers);
- raw SQL-строки с пользовательским input.

Каждое попадание:
- если маскировка отсутствует — добавь (отдельный commit, семантическая правка);
- если правка требует архитектурного решения — DRIFT.md.

---

## Переход

После:
- все M-* имеют `V-M-*` запись (или явный pending-status / DRIFT.md);
- критические модули имеют structured log с markers;
- privacy-аудит пройден.

→ `06-validation-gates.md`.
