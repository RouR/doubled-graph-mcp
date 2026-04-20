# 02 — Reconstruct intent

**Роль ИИ:** восстановить `requirements.xml` по существующему коду и документации.

---

## Externalize state — важно для локальной модели

Восстановление замысла legacy-кода — многошаговый процесс с десятками уточнений у пользователя. Контекст локальной модели не выдержит. Поэтому:

- Все найденные actors / actions / goals — **append-only в `.doubled-graph/drafts/intent-recovery.md`** (отдельный файл от интервью в new-project).
- Каждый вопрос к пользователю и его ответ — в этот же файл.
- Финальное заполнение `docs/requirements.xml` — из файла, не из истории чата.

Формат scratchpad'а — свободный markdown, но с разделами:

```markdown
# Intent recovery — draft
Started: <ISO>
Status: in-progress | completed

## Actors discovered
- <actor>: <source, напр. "src/routes/login.ts: POST /login">

## Actions per actor
### <actor>
- <action>: <source>
  - goal (draft): <prose>
  - user-clarified: <yes/no> | <если да — дословная фраза пользователя>

## Open questions
- [UC-draft-N] <вопрос пользователю>

## User answers
- 2026-04-18T14:05: <вопрос> → <ответ>

## Legacy-to-deprecate candidates
- <function/module>: <почему кандидат>
```

---

## Шаги

**Шаг 1 — `doubled-graph init`.**

```
(в ИИ-клиенте вызови skill (доступен через `doubled-graph init`))
```

Создаст `docs/*.xml` шаблоны. Они пустые — заполним за этот и следующие шаги.

**Шаг 2 — actor discovery.**

Из computed graph найди точки входа (entry points):
- HTTP routes / handlers;
- CLI commands;
- cron jobs / scheduled tasks;
- message consumers;
- public SDK exports.

Каждая точка входа → один или несколько actor'ов.

Составь список actor'ов. Примеры: `Buyer`, `Admin`, `CronScheduler`, `PaymentWebhook`, `ExternalSDKUser`.

**Шаг 3 — action discovery.**

Для каждого actor'а: какие действия он совершает?

Смотри в:
- route paths / command names (читаемые имена);
- function names на entry-point уровне;
- названия message-topics / event types.

Группируй действия по акторам.

**Шаг 4 — goal recovery.**

Для каждого действия:
- посмотри код функции-обработчика;
- прочитай docstring / comments, если есть;
- прочитай тесты, покрывающие функцию (они часто описывают ожидаемое поведение);
- в коде найди log-сообщения «success» — часто описывают goal.

Сформулируй goal **прозой**. Не угадывай числа (latency/throughput) — они должны исходить от пользователя.

**Шаг 5 — спроси пользователя.**

Покажи черновик списка:

```
Восстановленные use-cases (черновик):

UC-001: Buyer → place_order → получает подтверждение
UC-002: Buyer → cancel_order → заказ отменён, refund инициирован
UC-003: Admin → revoke_user → пользователь больше не может logged in
UC-004: CronScheduler → cleanup_expired_sessions → сессии удалены из DB
...

Вопросы:
1. Это полный список или что-то пропустил?
2. Есть актор/действие, которое выглядит use-case'ом, но на самом деле внутренняя ассистенция (то есть не стоит в requirements)?
3. Есть latency/throughput/security требования, которые я должен зафиксировать?
4. Что-то из кода кажется legacy — больше не используется? (кандидаты на deprecation)
```

Дождись ответов. Скорректируй список.

**Шаг 6 — заполни `docs/requirements.xml`.**

Источник данных — **scratchpad `.doubled-graph/drafts/intent-recovery.md`**, не история чата. Читай его целиком перед генерацией XML.

Используй AAG-нотацию (см. `prompts/new-project/02-requirements.md` § «формат»).

Для каждого UC добавь атрибут `<Source kind="reconstructed" />`:

```xml
<UseCase id="UC-001">
  <Source kind="reconstructed" from="src/orders/place.py + tests/test_place_order.py + README" />
  <Actor>Buyer</Actor>
  <Action>place_order</Action>
  <Goal>получает подтверждение успешного заказа</Goal>
</UseCase>
```

Это помогает будущему reviewer'у видеть, откуда пошло требование.

**Шаг 7 — approval gate (doubled-graph-собственный, на требованиях):**

Покажи полный `requirements.xml`:

> «Восстановленные требования. Подтверждаешь?»

Если есть разногласия — фиксируй в `docs/DRIFT.md`:

```markdown
# DRIFT.md

## Reconstructed-requirements discrepancies (migration)

### D-REC-001 — UC-005 spurious
Пользователь утверждает, что функция `helper_utils.format_address` — случайный helper, не требование. Закомментирован в 2024-Q3, но не удалён. Помечаем для удаления на шаге 06-validation-gates.

### D-REC-002 — UC-007 goal неизвестен
ИИ не смог восстановить goal для `admin_panel.generate_report`. Пользователь обещает дополнить на следующей неделе.
```

---

## Переход

После approval → `03-draft-plan.md`.
