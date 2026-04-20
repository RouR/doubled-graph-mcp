# Артефакты doubled-graph

Формат — **XML** (решение Q6, совместимость с `doubled-graph lint`). Шесть файлов в `docs/`, один в корне. Создаются `doubled-graph init`; эволюционируют через `doubled-graph plan`, `doubled-graph execute`, `doubled-graph refresh`.

**Источник истины для XML-схем** — templates в upstream grace-marketplace:
`extra/research/grace-marketplace-main/skills/grace/grace-init/assets/docs/*.xml.template`. Мы **не форкаем** их; описываем роль и связи между ними.

---

## Карта артефактов

```
docs/
├── requirements.xml           ← что делает продукт (бизнес-цели, AAG)
├── technology.xml             ← стек, версии, constraints
├── development-plan.xml       ← модули, контракты, фазы, flows
├── knowledge-graph.xml        ← declared graph: модули, экспорты, CrossLinks
├── verification-plan.xml      ← тесты, сценарии, markers, gates
└── operational-packets.xml    ← canonical ExecutionPacket/GraphDelta/FailurePacket shapes

AGENTS.md                      ← протокол агента + phase-блок (см. drift-and-priority.md)
```

Плюс код с якорями разметки (ниже § «Разметка кода»).

---

## 1. `docs/requirements.xml`

**Что содержит:** use-cases в нотации Actor–Action–Goal (AAG). Каждый use case — атомарен.

```xml
<Requirements>
  <UseCase id="UC-001">
    <Actor>Buyer</Actor>
    <Action>place_order</Action>
    <Goal>получить подтверждение в течение 3 секунд</Goal>
    <NonFunctional>
      <Latency>p95 &lt; 3s</Latency>
      <Security>JWT-auth required</Security>
    </NonFunctional>
  </UseCase>
  ...
</Requirements>
```

**Кто меняет:** человек — напрямую или через ИИ с явной формулировкой. Изменение требования = новая версия, старая помечается `deprecated`.

**Связи:** каждый `UC-xxx` реализуется одним или несколькими `M-xxx` в `development-plan.xml`; эта связь отражается в `knowledge-graph.xml` через элемент `Implements`.

---

## 2. `docs/technology.xml`

**Что содержит:** стек и constraints.

```xml
<Technology>
  <Runtime name="<язык>" minimum="<floor от зависимостей>" preferred="current-stable" />
  <Libraries>
    <Lib name="<framework>" version=">=X.Y" />
    <Lib name="<orm>" version="^X" />
  </Libraries>
  <Testing>
    <Framework>&lt;из language-adapter&gt;</Framework>
    <Coverage target="<80%|настраиваемо>" />
  </Testing>
  <Deployment>&lt;Docker | k8s | serverless | bare-metal&gt;</Deployment>
</Technology>
```

**Правила версий:**
- `minimum` — обоснованный floor (напр., `3.12` для Python если нужен FalkorDB Lite). Не завышай.
- `preferred` — обычно `current-stable` или `LTS`. Конкретный `X.Y.Z` **не указывай** — устаревает.
- В `<Lib version>` используй диапазоны (`>=X.Y`, `^X`, `~X.Y`), не exact pins. Exact pins — lockfile'у.

**Approval-gate:** `doubled-graph plan` Step 2 утверждает стек до того, как `development-plan.xml` начнёт ссылаться на конкретные библиотеки. На момент approval актуальные версии сверяются через WebFetch/WebSearch — не берутся из памяти ИИ.

---

## 3. `docs/development-plan.xml`

**Что содержит:** модули, контракты модулей, фазы, data-flows.

```xml
<DevelopmentPlan>
  <Module id="M-AUTH-VALIDATE" criticality="critical">
    <Purpose>Validate incoming JWT and resolve User.</Purpose>
    <Paths>
      <Path>src/auth/validate.ts</Path>
    </Paths>
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
    <Dependencies>
      <Dep module="M-AUTH-TOKENS" />
    </Dependencies>
  </Module>

  <Phase id="Phase-1">
    <Step id="step-1" module="M-AUTH-TOKENS" />
    <Step id="step-2" module="M-AUTH-VALIDATE" />
  </Phase>

  <DataFlow id="DF-LOGIN">
    <From module="M-ROUTES-LOGIN" />
    <Through module="M-AUTH-VALIDATE" />
    <To module="M-SESSION-CREATE" />
  </DataFlow>
</DevelopmentPlan>
```

**Приоритет полей:**
- `criticality` ∈ {critical, standard, helper} — вход для risk-level в `doubled-graph impact`.
- `Paths` — множество файлов, принадлежащих модулю. `doubled-graph detect_changes` по этому полю определяет `code_without_module`.
- `DataFlow` — используется для визуализации процессов и для `critical-path` классификации в `impact`.

---

## 4. `docs/knowledge-graph.xml` — declared graph

**Что содержит:** модули, экспорты, CrossLinks (ссылки между модулями), аннотации.

```xml
<KnowledgeGraph>
  <Module id="M-AUTH-VALIDATE">
    <Export name="validateUser" kind="function" />
    <Export name="validateToken" kind="function" />
    <CrossLink to="M-AUTH-TOKENS" kind="uses" />
    <Annotation kind="security">PII-touching</Annotation>
  </Module>
</KnowledgeGraph>
```

**Отличие от computed graph:** этот файл пишется ИИ по замыслу, а не извлекается из AST. Оба графа пересекаются в `doubled-graph detect_changes` — ядро ценности методологии, см. `tools.md`.

---

## 5. `docs/verification-plan.xml`

**Что содержит:** тесты, их команды, сценарии, markers (имена логов), gates.

```xml
<VerificationPlan>
  <Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
    <Command>pnpm test auth/validate</Command>
    <Scenario>valid JWT returns User</Scenario>
    <Markers>
      <Marker>VALIDATE_SUCCESS</Marker>
      <Marker>VALIDATE_FAIL</Marker>
    </Markers>
  </Verification>
  <Gate id="G-pre-merge" kind="required">
    <Check>doubled-graph lint</Check>
    <Check>doubled-graph detect_changes --scope compare --base-ref main</Check>
    <Check>pnpm test</Check>
  </Gate>
</VerificationPlan>
```

**Связь с кодом:** каждый `Marker` — имя, которое должно появиться в structured log, когда код проходит соответствующую точку. `doubled-graph detect_changes § missing_verification` проверяет, что для каждого критического `M-*` есть хотя бы один `V-M-*`.

---

## 6. `docs/operational-packets.xml`

**Что содержит:** canonical форматы пакетов, которыми агент обменивается между skills.

- **ExecutionPacket** — что `doubled-graph multiagent-execute` передаёт worker'у.
- **GraphDelta** — что worker возвращает (новые модули, изменённые экспорты).
- **VerificationDelta** — то же для verification.
- **FailurePacket** — для `doubled-graph fix` handoff.

Это — инфраструктурный артефакт; в маленьких проектах может быть пустым (только шаблоны без содержимого). Пользователю видеть редко.

---

## 7. `AGENTS.md`

Создаётся `doubled-graph init`. Содержит:

- Keywords и Annotation проекта.
- Копию 10 принципов doubled-graph.
- Справочник якорей (см. § «Разметка кода» ниже).
- Конвенцию логов и verification.
- **phase-блок** (наше [PROPOSED], см. `drift-and-priority.md`):

```markdown
<!-- doubled-graph:phase:start -->
## doubled-graph phase
phase: post_migration
updated: 2026-04-18
<!-- doubled-graph:phase:end -->
```

ИИ-ассистент читает `AGENTS.md` первым при входе в репозиторий.

---

## Разметка кода (якоря)

Синтаксис комментариев адаптируется под язык (см. `language-adapters/*.md`). Ниже — в TypeScript-варианте.

```ts
// START_MODULE_CONTRACT
// Module: M-AUTH-VALIDATE
// Purpose: validate JWT and resolve User
// Scope: single file src/auth/validate.ts
// Dependencies: M-AUTH-TOKENS
// Criticality: critical
// LINKS: UC-001, V-M-AUTH-VALIDATE-01
// END_MODULE_CONTRACT

// START_MODULE_MAP
// exports:
//   - validateUser (function)
//   - validateToken (function)
// END_MODULE_MAP

// START_CONTRACT: validateUser
// PURPOSE: validate JWT, resolve user
// INPUTS: req: Request (with Authorization: Bearer header)
// OUTPUTS: User | null (null if invalid, never throws)
// SIDE_EFFECTS: none
// LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
// END_CONTRACT: validateUser
export function validateUser(req: Request): User | null {
  // START_BLOCK_DECODE_JWT
  const token = extractToken(req);
  const payload = decodeJwt(token);
  // END_BLOCK_DECODE_JWT

  // START_BLOCK_CHECK_CLOCK_SKEW
  if (Math.abs(Date.now() - payload.iat * 1000) > 60_000) return null;
  // END_BLOCK_CHECK_CLOCK_SKEW

  return payload.user;
}

// START_CHANGE_SUMMARY
// 2026-04-12: tightened JWT clock-skew tolerance to 60s (DG-Authored: ai)
// 2026-04-18: --
// END_CHANGE_SUMMARY
```

**Правила:**

- **Модуль-контракт** — на уровне файла (первый раз), не дублируется внутри файла.
- **Function-контракт** — перед определением функции (для TS/Java/Go); в Python — в docstring под `def` (см. `language-adapters/python.md`).
- **Блок** — ≤ 500 токенов, имена уникальны **в файле**, но могут совпадать между файлами.
- **CHANGE_SUMMARY** — в конце файла, хронологический порядок, последняя строка — дата-пустая-запись (для будущих правок).

`doubled-graph lint` проверяет парность открывающих/закрывающих, уникальность в файле, соответствие имени функции в `START_CONTRACT:`/`END_CONTRACT:`, наличие `M-*` в модуль-контракте, существующие `UC-*`/`V-M-*` в LINKS.

---

## Structured logs

Каждое лог-событие имеет минимум полей (см. § 13 методологии draft):

```json
{
  "ts": "2026-04-18T10:22:04.123Z",
  "level": "info",
  "anchor": "validateUser:BLOCK_DECODE_JWT",
  "module": "M-AUTH-VALIDATE",
  "requirement": "UC-001",
  "correlation_id": "req_abc123",
  "event": "jwt_decoded",
  "belief": "payload trusted, skew=0"
}
```

`anchor` имеет формат `<function>:<block>` (или просто `<function>` для function-level события) и **должен** совпадать с именем якоря в коде. `doubled-graph lint` проверяет, что каждый `anchor` ссылается на существующий якорь.

**Privacy-правила** — `drift-and-priority.md § Logs privacy` + `runtime-adapters/*.md`.

**OpenTelemetry GenAI — НЕ обязателен** (решение 2026-04-17). Команды могут использовать свой observability-стек; маркирование лог-полей выше — достаточный baseline. См. `memory/project_otel_dropped.md`.

---

## Что `doubled-graph init` создаёт и что остаётся пустым

| Файл | После `doubled-graph init` | После `doubled-graph plan` | После первого `doubled-graph execute` |
|---|---|---|---|
| requirements.xml | шаблон + intent-интервью ответы | + детальные UC | обычно не меняется |
| technology.xml | шаблон | стек утверждён | не меняется |
| development-plan.xml | шаблон | модули + фазы | обновление по `doubled-graph refresh` если что-то поменялось |
| knowledge-graph.xml | шаблон | модули + экспорты + CrossLinks | актуализируется `doubled-graph refresh` |
| verification-plan.xml | шаблон | V-M-* черновики | заполнено после прогонов |
| operational-packets.xml | шаблон | обычно не трогаем | обновляется при `doubled-graph multiagent-execute` |
| AGENTS.md | копия шаблона + phase-блок | не меняется | не меняется |
