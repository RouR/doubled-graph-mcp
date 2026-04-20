# 05 — Verification Plan

**Роль ИИ:** досчитать `docs/verification-plan.xml`: командами запуска, markers, gates.
**Соответствует upstream skill:** `doubled-graph verification` draft mode.

---

## Externalize state

Продолжает `.doubled-graph/drafts/plan.md` (начат в шаге 04). Не создавай новый файл — обогащай существующий секции `V-M-* drafts`, `Gates`, `Eval gates`.

Финальный рендеринг `docs/verification-plan.xml` — **из scratchpad'а**, не из истории. Для каждого M-* читай из `plan.md § V-M-* drafts` и формируй запись.

---

## Инструкция

**Шаг 1 — добавь `<Command>` к каждому `V-M-*`.**

На основе `technology.xml` (testing framework) подставь команду:

| Framework | Command-формат |
|---|---|
| vitest | `pnpm test <module/path>` или `npx vitest run <pattern>` |
| jest | `pnpm test <module/path>` |
| pytest | `pytest tests/<path>.py -v` |
| JUnit 5 | `./gradlew test --tests <FQCN>` |
| cargo test | `cargo test <module::test>` |
| go test | `go test ./<package>/...` |
| xUnit | `dotnet test --filter <FQTM>` |
| XCTest | `swift test --filter <TestClass>` |

**Шаг 2 — добавь `<Markers>` для каждого `V-M-*`.**

Marker — имя structured log-события, которое **должно** появиться при прогоне теста. Это привязка кода ↔ verification.

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>pnpm test auth/validate</Command>
  <Scenario>valid JWT → returns User</Scenario>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
  </Markers>
</Verification>
```

В коде (на шаге 06) логика будет включать:

```ts
logger.info("validate_success", {
  anchor: "validateUser:BLOCK_DECODE_JWT",
  marker: "VALIDATE_SUCCESS",
  ...
});
```

**Шаг 3 — добавь gates.**

Обязательный baseline:

```xml
<Gate id="G-pre-commit" kind="recommended">
  <Check>doubled-graph lint</Check>
  <Check>doubled-graph detect_changes --scope staged</Check>
</Gate>

<Gate id="G-pre-merge" kind="required">
  <Check>doubled-graph lint</Check>
  <Check>doubled-graph detect_changes --scope compare --base-ref main</Check>
  <Check><!-- main test command из technology.xml --></Check>
</Gate>
```

Для модулей с `criticality="critical"` — дополнительно eval-gate:

```xml
<EvalGate id="E-critical-modules" kind="required-for-critical">
  <Dataset>datasets/golden/auth-validate.jsonl</Dataset>
  <Threshold metric="pass-rate" min="0.85" />
</EvalGate>
```

Eval-gate — обязателен, если в `development-plan.xml` есть хотя бы один M-* с `criticality="critical"`. Golden dataset можно начать с 3–5 кейсов; наращивается со временем.

**Шаг 4 — проверь полноту.**

Прогони чек-лист:
- [ ] каждый `M-*` с `criticality ∈ {critical, standard}` имеет ≥ 1 `V-M-*`;
- [ ] каждый `critical` имеет ≥ 1 integration-test;
- [ ] каждый `V-M-*` имеет `<Command>`;
- [ ] каждый критический `V-M-*` имеет хотя бы один `<Marker>`;
- [ ] описан `G-pre-merge` gate.

Если где-то нет — дополни.

**Шаг 5 — approval:**

Покажи пользователю:

1. **Саммари verification-plan**: сколько `V-M-*`, сколько eval-gates, какие gates (`G-pre-commit`, `G-pre-merge`).
2. **⚠ Что требует особого внимания**:
   - критические модули без integration-теста;
   - критические модули без `<Marker>` (значит связь код ↔ verification будет слабой);
   - eval-gate на ещё не существующем golden dataset (dataset нужно завести до первого run'а);
   - gates, `<Check>` которых ссылается на команды, ещё не определённые в `technology.xml`.
   Если ничего — «отклонений нет».
3. **Чек-лист одобрения** (echo из шага 4):
   - [ ] каждый `M-*` с `criticality ∈ {critical, standard}` имеет ≥ 1 `V-M-*`;
   - [ ] каждый `critical` имеет ≥ 1 integration-test;
   - [ ] каждый `V-M-*` имеет `<Command>`;
   - [ ] каждый критический `V-M-*` имеет хотя бы один `<Marker>`;
   - [ ] `G-pre-merge` gate определён;
   - [ ] если есть `critical`-модули — `EvalGate` определён с dataset-path.
4. **Вопрос**:

   > Verification plan готов. Чтобы одобрить — подтвердите явно по чек-листу выше. Если хотите добавить сценарий или marker — назовите модуль и что добавить.

Ответ «ок» без упоминания чек-листа — просьба пройти его явно.

---

## Переход

→ `prompts/new-project/06-generate.md`.
