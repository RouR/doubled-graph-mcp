# 03 — Technology

**Роль ИИ:** заполнить `docs/technology.xml`. Источник — `.doubled-graph/drafts/interview.md § Блок B` (стек проговорен в интервью). Читай scratchpad, не chat history.

---

## Инструкция

**Шаг 1.** На основе ответов интервью + UC (особенно NonFunctional) предложи стек:

- Runtime (язык + current-stable / LTS на момент сессии; конкретный minor **не пинь**).
- Key libraries (framework, DB driver, auth, validation).
- Testing framework (см. language-adapter из `methodology/language-adapters/`).
- Deployment target (Docker / k8s / serverless / …).

Stack заполняется **полностью**: все позиции, диапазоны версий, compatibility matrix. Для крошечных проектов список будет короче естественно (меньше библиотек), но формат полный.

**Правило выбора версий.** Методология **не диктует конкретные версии** — они устаревают за недели.
- **Нижний floor** — только там, где его навязывает зависимость (напр., «Python 3.12+» потому что FalkorDB Lite требует). Обосновывай, если floor появляется.
- **Верх** — не фиксируй «ровно X.Y.Z». Используй диапазоны (`^`, `~`, `>=`) или формулировку «current stable на момент setup». Exact pins — задача lockfile, не `technology.xml`.
- На момент сессии ИИ **сверяет актуальные версии** через WebFetch/WebSearch на официальных registry/docs, не полагается на знания из претрейна.

**Шаг 2.** Покажи предложение пользователю **как саммари**, не сразу как XML:

```
Предлагаю стек (current stable на момент выбора, конкретные версии — из registry):
- Runtime: <язык> <LTS или current stable>
- Framework: <web-фреймворк>, последняя major
- DB: <СУБД> через <ORM/driver>, последняя major
- Auth: <решение> (custom JWT | external IdP)
- Validation: <runtime-schema-lib из language-adapter>
- Testing: <framework из language-adapter>
- Deployment: <Docker | k8s | serverless | bare-metal>
Принимаешь? Хочешь заменить что-то?
```

ИИ подставляет конкретные имена и диапазоны версий из актуальных источников, **не** копирует из этого шаблона как есть.

**Шаг 3.** После согласования — заполни `docs/technology.xml`. Формат — `methodology/artifacts.md § 2`.

**Шаг 4 — Approval gate (upstream `doubled-graph plan` Step 2 частично):**

> «Technology зафиксирован. Можем ли переходить к Development Plan?»

Ждёшь подтверждения, переходишь к `04-development-plan.md`.

---

## Анти-паттерны

- Не предлагай стек, который **ты** считаешь «модным», если он не соответствует опыту пользователя. Лучше boring stack, который команда знает.
- Не вноси exact pin'ы версий (`X.Y.Z` ровно) в `technology.xml` — это задача lockfile. В артефакте — только диапазоны.
- Не копируй устаревшие версии из своего претрейна — **проверь** актуальный релиз через WebFetch/WebSearch на официальном источнике в момент сессии.
- Не добавляй observability-стек, если не было явного запроса (OTel GenAI не обязателен — см. `memory/project_otel_dropped.md`).
