# 04 — Development Plan

**Роль ИИ:** построить `docs/development-plan.xml` — модули, контракты, фазы, data flows.
**Соответствует upstream skill:** `doubled-graph plan` Step 2 + Step 3.

---

## Externalize state

Плановая стадия — итеративная: декомпозиция на модули → контракты → фазы → verification draft. Каждый шаг ревьюит пользователь, между итерациями легко набирается 30+ минут диалога. Веди:

- `.doubled-graph/drafts/plan.md` — append-only, собирается на шагах 1–6 **до** финального рендеринга `docs/development-plan.xml`.
- **Читает input**: `.doubled-graph/drafts/interview.md` (из шага 01) — UC и стек-предпочтения.
- **Продолжается на шаге 05** (verification-plan) — тот же файл обогащается `V-M-*` черновиками.
- Финальный рендеринг в `docs/*.xml` (шаг 7 ниже) — из scratchpad'а, не истории чата.

Формат:

```markdown
# Plan draft
Started: <ISO>
Status: in-progress | completed
Reads-from: .doubled-graph/drafts/interview.md

## Modules
- M-AUTH-VALIDATE (critical): covers UC-001, exports validateUser; pre/post/inv; deps: M-AUTH-TOKENS
- ...

## Phases
- Phase-1: [M-AUTH-TOKENS]
- Phase-2: [M-AUTH-VALIDATE, M-ROUTES-LOGIN]

## Data flows
- DF-LOGIN: ...

## Approvals
- <ISO>: architecture approved (Step 2)
- <ISO>: verification draft approved (Step 3)
- <ISO>: execution plan approved (`execute` Step 1)

## V-M-* drafts (step 05)
- V-M-AUTH-VALIDATE-01: unit, «valid JWT → User»
```

---

## Инструкция

**Шаг 1 — декомпозиция на модули.**

Для каждого UC спроси: какие модули нужны? Не пиши код, описывай **интерфейсы**.

Правила:
- Имя модуля: `M-DOMAIN-PURPOSE`, напр. `M-AUTH-VALIDATE`, `M-ORDERS-CREATE`.
- Один модуль = один смысловой компонент. Не «utils», не «helpers» в начальном плане (потом выделится).
- `criticality`:
  - `critical` — auth, payments, data-integrity, PII-flow.
  - `standard` — обычная бизнес-логика.
  - `helper` — форматтеры, парсеры, глупые обёртки.

**Шаг 2 — контракты модулей.**

Для каждого `M-*`:

```xml
<Contract>
  <PublicExports>
    <Export name="validateUser" />
  </PublicExports>
  <Preconditions>
    <Pre>JWT header present</Pre>
  </Preconditions>
  <Postconditions>
    <Post>returns User | null (never throws)</Post>
  </Postconditions>
  <Invariants>
    <Inv>clock-skew tolerance = 60s</Inv>
  </Invariants>
</Contract>
```

Pre/post/invariants — прозой, но точной. Это ground-truth для `doubled-graph fix` в будущем.

**Шаг 3 — фазы.**

Разбей модули на фазы исполнения. Правило: модули одной фазы могут выполняться **параллельно** (нет зависимостей между ними). Зависимости — между фазами.

```xml
<Phase id="Phase-1">
  <Step id="step-1" module="M-AUTH-TOKENS" />
</Phase>
<Phase id="Phase-2">
  <Step id="step-2" module="M-AUTH-VALIDATE" />
  <Step id="step-3" module="M-ROUTES-LOGIN" />
</Phase>
```

Для MVP обычно 2–4 фазы. Больше — скорее всего переусложнение.

**Шаг 4 — data flows для критических UC.**

```xml
<DataFlow id="DF-LOGIN">
  <From module="M-ROUTES-LOGIN" />
  <Through module="M-AUTH-VALIDATE" />
  <To module="M-SESSION-CREATE" />
</DataFlow>
```

Обязательно для критических UC (всегда максимальная глубина — см. `methodology/auto-scaling.md`).

**Шаг 5 — approval gate (upstream Step 2):**

Покажи пользователю в таком порядке:

1. Список модулей (id, purpose, criticality) таблицей + ASCII-граф фаз.
2. **⚠ Особое внимание** (если применимо, иначе «отклонений нет»): новые/удалённые модули при revision; смена `criticality`; модули с несколькими `UC-*`; `critical` без verification-стратегии; сложные/циклические зависимости.
3. **Чек-лист одобрения**:
   - [ ] все `UC-*` покрыты хотя бы одним модулем;
   - [ ] `criticality` расставлен осознанно (не всё `critical`);
   - [ ] scope каждого модуля ясен;
   - [ ] циклических зависимостей нет;
   - [ ] orphan-модулей нет (кроме typed-UTILITY с входящими CrossLinks).
4. Вопрос:

   > Архитектура модулей. Чтобы одобрить — подтвердите по чек-листу. Если есть правки — назовите модуль и что изменить.

**Не переходи** к Step 3 без явного подтверждения. Ответ «ок» без упоминания чек-листа — просьба пройти его явно.

**При revision**: покажи diff (`+ added`, `- removed`, `~ changed: old → new`), не полный план заново.

**Шаг 6 — черновик verification (upstream `doubled-graph plan` Step 3).**

Для каждого модуля предложи минимум 1 `V-M-*`. Критические — ≥ 2, хотя бы один integration.

Шаблон:

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Scenario>valid JWT with fresh iat → returns User</Scenario>
</Verification>
<Verification id="V-M-AUTH-VALIDATE-02" module="M-AUTH-VALIDATE" kind="unit">
  <Scenario>JWT with iat skew > 60s → returns null</Scenario>
</Verification>
```

Команды запуска (`<Command>`) — подставятся позже (на шаге 05).

**Шаг 7 — approval gate (upstream Step 3):**

Покажи:

1. Список `V-M-*` по модулям (id, kind, сценарий).
2. **⚠ Особое внимание**: `critical`-модули только с unit (без integration); `critical`/`standard` без единого `V-M-*`; сценарии покрывают только happy path. Иначе — «отклонений нет».
3. **Чек-лист**:
   - [ ] `critical`/`standard` имеют ≥ 1 `V-M-*`;
   - [ ] `critical` имеет ≥ 1 integration-тест;
   - [ ] каждый сценарий конкретен (не абстрактный);
   - [ ] failure-сценарии есть для критических.
4. Вопрос:

   > Verification draft. Подтвердите по чек-листу; если нужно добавить — назовите модуль и сценарий.

**Переходим** к `05-verification-plan.md` только после явного подтверждения. При revision — diff, не полный список.

---

## Правила

- **Каждый UC должен иметь** минимум один `M-*`, который его реализует. Проверь.
- **Каждый критический модуль** должен иметь минимум один `V-M-*` в draft.
- **Циклические зависимости недопустимы.** Если появились — декомпозируй дальше.
- **Не изобретай модули без UC.** Каждый `M-*` ↔ минимум один `UC-*`.

---

## Переход

После двух approval gates → `prompts/new-project/05-verification-plan.md`.
