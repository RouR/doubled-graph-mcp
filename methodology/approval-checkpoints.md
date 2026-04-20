# Approval checkpoints

Ключевой принцип 2: **каждый артефакт утверждается человеком перед тем, как стать входом для следующего шага**. Ниже — какие точки **реально** существуют в upstream grace-marketplace и какие мы добавляем.

**Правило без исключений:** если gate не пройден, следующий шаг не начинается. Технически это обеспечивают skills upstream (остановка + ожидание), `doubled-graph lint` в CI и `doubled-graph detect_changes` как pre-commit/pre-merge gate.

---

## 1. Upstream gates (есть в grace-marketplace)

Проверено против исходников skill'ов (extra/research/grace-marketplace-main/skills/grace/*/SKILL.md).

### `doubled-graph init`
**Нет явного approval.** Создаёт шаблоны и возвращает управление. Дополнительный review можно сделать руками (посмотреть, что создано) — не обязательно.

### `doubled-graph plan` Step 2 — архитектура модулей
[SKILL.md:69](../extra/extra/research/grace-marketplace-main/skills/grace/grace-plan/SKILL.md) — «Present this to the user as a structured list and **wait for approval**».

**Что показывается:** список модулей с contract draft'ами. Пользователь либо апрувит, либо правит список → skill перезапускает Step 2.

**Критерий одобрения:**
- модули покрывают все `UC-*` из `requirements.xml`;
- `criticality` расставлен осознанно;
- нет модулей, у которых scope не ясен.

### `doubled-graph plan` Step 3 — черновик verification
[SKILL.md:79](../extra/extra/research/grace-marketplace-main/skills/grace/grace-plan/SKILL.md).

**Что показывается:** список `V-M-*` записей с `kind` и предварительными сценариями.

**Критерий:**
- каждый модуль с `criticality ∈ {critical, standard}` имеет ≥ 1 `V-M-*`;
- для критических модулей — минимум один `integration`-тест (не только unit).

### `doubled-graph execute` Step 1 — план перед исполнением
[SKILL.md:53](../extra/extra/research/grace-marketplace-main/skills/grace/grace-execute/SKILL.md) — «Wait for user approval before proceeding».

**Что показывается:** фазы → шаги → модули с порядком исполнения, estimated impact, зависимости.

**Критерий:**
- порядок исполнения не нарушает зависимости;
- разбивка на шаги адекватна (не слишком крупные шаги, которые могут сорвать);
- risk-level (через `doubled-graph impact`) для каждого шага < CRITICAL, либо явно принят.

### `doubled-graph multiagent-execute` Step 1 — волны
[SKILL.md:79](../extra/extra/research/grace-marketplace-main/skills/grace/grace-multiagent-execute/SKILL.md).

Зависит от **профиля**:

| Профиль | Approval |
|---|---|
| `safe` | перед каждой волной (много gate'ов) |
| `balanced` (default) | один up-front на весь план |
| `fast` | один up-front, без per-wave gates (только scoped reviewer блокирует отдельные модули при явных проблемах) |

---

## 2. Профили `doubled-graph multiagent-execute`

Из [SKILL.md:28–51](../extra/extra/research/grace-marketplace-main/skills/grace/grace-multiagent-execute/SKILL.md) upstream.

| Профиль | Approval | Review | Refresh | Когда |
|---|---|---|---|---|
| **safe** | перед каждой волной | full review per module | targeted + full at phase boundaries | новые / рискованные модули; critical проекты |
| **balanced** (default) | один up-front | scoped gate per module; batched checks per wave | targeted after wave; full at phase boundary | обычный режим |
| **fast** | один на весь run | scoped только для blockers; глубокий аудит в конце фазы | targeted during wave; full at phase end + end-of-run | mature codebase + сильная verification |

**Как выбирать multiagent-профиль:**

- **Default — `balanced`.**
- Режим `migration`: всегда `safe` (много рисков непреднамеренного семантического изменения).
- Режим `post_migration` + первые недели после переключения: `safe` → потом `balanced`.
- Critical-модули (`criticality="critical"` в `development-plan.xml`): `safe` на этих модулях, даже если остальные — `balanced`. `doubled-graph multiagent-execute` поддерживает per-module override.
- `fast` — только для mature codebase с сильной verification (много прогоняемых `V-M-*` и eval-gates).

(Это multiagent-профили upstream, не «глубина артефактов». Глубина в doubled-graph всегда максимальная — см. `auto-scaling.md`.)

**Пресетов minimal/standard/strict в методологии НЕТ.** Ранние версии черновика обсуждали их ввести — отказались, т. к. в upstream их нет и плодить параллельные конфигурации опасно.

---

## 3. doubled-graph-собственные gates (не upstream)

### Phase-switch gate
Переключение `migration` → `post_migration` и обратно. Всегда требует человеческого подтверждения. Параметры:

- переход в `post_migration` — проверяется, что `doubled-graph lint` + `detect_changes --scope all` оба возвращают чистый результат;
- откат → `migration` — обязательна запись в `docs/DRIFT.md` с причиной и ожидаемым окончанием.

### Pre-commit gate (рекомендован, опционален локально, обязателен в CI)

```bash
doubled-graph lint \
  && doubled-graph detect_changes --scope staged \
  && доступные unit-тесты
```

Если `detect_changes` непуст и drift не задокументирован в `DRIFT.md` — merge блокируется.

### Pre-merge gate (обязателен)

Определяется в `docs/verification-plan.xml`:

```xml
<Gate id="G-pre-merge" kind="required">
  <Check>doubled-graph lint</Check>
  <Check>doubled-graph detect_changes --scope compare --base-ref main</Check>
  <Check>pnpm test</Check>
</Gate>
```

---

## 4. Eval gates (обязательны при наличии critical-модулей)

В `verification-plan.xml` добавляется секция eval, если в `development-plan.xml` есть хотя бы один модуль с `criticality="critical"`:

```xml
<EvalGate id="E-prompt-quality" kind="required-for-critical-modules">
  <Dataset>datasets/golden-cases.jsonl</Dataset>
  <Judge kind="structured-rubric" model="<независимая-от-генератора>" />
  <Threshold metric="pass-rate" min="0.85" />
</EvalGate>
```

**Что проверяется:**
- `prompt-quality` — соответствие сгенерированного кода контракту на golden-датасете.
- `ai-regression` — прогон сохранённых сценариев, сравнение с baseline.

**LLM-as-Judge bias**: см. memory и `../METHODOLOGY_DRAFT.md §12.3`. Используем swap-and-compare + diverse judge.

**Важно:** eval-gates **не заменяют** unit/integration тесты (принцип 9). Это дополнительный слой для агентного поведения.

---

## 5. Таблица gates vs сценарии

| Сценарий / шаг | gate |
|---|---|
| Новый проект, intent-интервью | — (сбор данных, не gate) |
| Новый проект, `doubled-graph init` | — |
| Новый проект, `doubled-graph plan` Step 2 | **upstream approval** |
| Новый проект, `doubled-graph plan` Step 3 | **upstream approval** |
| Новый проект, `doubled-graph execute` Step 1 | **upstream approval** |
| Миграция, requirements recovery | **phase-specific approval** (утверждаем восстановленные требования) |
| Миграция, план | **upstream approval** (`doubled-graph plan` Step 2) |
| Миграция, переход в `post_migration` | **phase-switch gate** |
| Поддержка, любая правка | `impact` HIGH/CRITICAL → **approval перед правкой** |
| Поддержка, перед коммитом | **pre-commit gate** (рекомендован) |
| Перед merge в main | **pre-merge gate** (обязателен) |

---

## 6. Что делать при провале gate'а

Зависит от типа провала:

- **approval отказан** → вернуться на один шаг назад, переделать артефакт.
- **`doubled-graph lint` не проходит** → фикс разметки, чаще всего простой.
- **`detect_changes` показывает drift** → применить `on-drift-detected.md` (см. `prompts/maintenance/`).
- **тесты не проходят** → стандартный debug-флоу; `doubled-graph fix` как помощник, но не обязательно.
- **eval-gate показывает регрессию** → скорее всего изменился промпт или модель; откатываем промпт/модель или добавляем новые golden cases.

**Что не делаем:** никогда не обходим gate через `--no-verify` или эквивалент. Если gate мешает — чиним его, а не отключаем.
