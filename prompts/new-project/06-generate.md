# 06 — Generate

**Роль ИИ:** сгенерировать код по `development-plan.xml`, фаза за фазой. С разметкой, logs, тестами.
**Соответствует upstream skills:** `doubled-graph execute` или `doubled-graph multiagent-execute` (по выбору профиля).

---

## Выбор оркестрации

**Одиночный агент (`doubled-graph execute`):**
- 1–3 модуля в плане,
- либо IDE не поддерживает sub-agents (Continue, Cline базово),
- либо пользователь явно предпочитает sequential.

**Multiagent (`doubled-graph multiagent-execute`):**
- есть многомодульные фазы (> 2 параллельных модулей),
- IDE поддерживает sub-agents (Claude Code, Cursor background agents).

При multiagent выбери **multiagent-профиль** (`safe` / `balanced` / `fast`) по таблице:

| Ситуация | Профиль |
|---|---|
| первый день на методологии + новый код | `safe` |
| стандартный старт проекта | `balanced` (default) |
| mature codebase + strong verification (редко для new-project) | `fast` |

(Речь о профилях `doubled-graph multiagent-execute`, а не о «глубине артефактов» — последние в doubled-graph не масштабируются, всегда максимум; см. `methodology/auto-scaling.md`.)

**Approval gate (upstream `doubled-graph execute` Step 1):**

Покажи:

1. Предложенный выбор с однострочным объяснением:
   - `single` — sequential, approval перед execute очереди;
   - `multiagent: safe` — параллельно, **approval перед каждой волной**;
   - `multiagent: balanced` (default) — параллельно, **один approval up-front**, per-module review;
   - `multiagent: fast` — **approval только один раз на весь run**, без per-wave gates (для mature codebase с полным verification).
2. План исполнения: фазы → модули → зависимости.
3. **⚠ Особое внимание**: критические модули; модули с `impact` HIGH/CRITICAL; при `fast` — список verification-активов, покрывающих риск.
4. **Чек-лист**:
   - [ ] профиль соответствует зрелости проекта;
   - [ ] для `fast` — verification покрывает критические пути;
   - [ ] порядок исполнения не нарушает зависимости;
   - [ ] risk-level каждого шага < CRITICAL или явно принят.
5. Вопрос:

   > Выбор оркестрации: <профиль>. Подтвердите по чек-листу. Для `fast` — отдельная фраза: «да, fast, понимаю что per-wave approval не будет».

**Особый случай `fast`:** на «да»/«ок» переспроси явно — «`fast` отключает per-wave approval. Подтвердите отдельной фразой.» Не начинай execute на `fast` без явной фразы.

---

## Выполнение фазы N

**Для каждой фазы** из `development-plan.xml`:

**Шаг 1** — выбор модулей фазы. Показываешь пользователю, какие M-* будут сделаны в этой волне.

**Шаг 2** — worker(s) генерируют код. Каждый worker:

1. Читает `development-plan.xml § Contract` своего M-*.
2. Читает `technology.xml` — использует указанные библиотеки.
3. Читает `methodology/language-adapters/<язык>.md` — учитывает language-specific правила.
4. Пишет:
   - файл с MODULE_CONTRACT и MODULE_MAP в header;
   - функции с CONTRACT: блоками;
   - блоки BLOCK_* для секций > 20–30 строк;
   - структурированные logs с `anchor`, `module`, `requirement` полями;
   - CHANGE_SUMMARY в конце файла.

**Шаг 3** — реализация тестов. Для каждого `V-M-*` из `verification-plan.xml`:

- тест с правильной командой запуска;
- покрывает сценарий из `<Scenario>`;
- порождает log-событие с соответствующим `<Marker>`.

**Шаг 4** — worker возвращает GraphDelta:
- новые/изменённые файлы;
- новые/изменённые экспорты модуля;
- новые/изменённые CrossLinks.

**Шаг 5** — reviewer (в `safe`/`balanced`):
- проверяет соответствие контракту;
- проверяет наличие разметки;
- проверяет, что тесты запускаются и проходят.

**Шаг 6** — после волны:
- `doubled-graph analyze --mode incremental --paths <новые-файлы>`;
- `doubled-graph refresh --scope targeted` — обновляет `knowledge-graph.xml` и `development-plan.xml` под реальное состояние кода (если что-то разошлось).

---

## Правила качества кода

- **Следуй `technology.xml`.** Не добавляй библиотеки, которых там нет, без возврата на approval.
- **Следуй `methodology/language-adapters/<язык>.md`.** Язык-специфичные правила важнее общих.
- **Pre/post/invariants** — как runtime-проверки **только** для `criticality ∈ {critical, standard}` модулей и только по рекомендации language-adapter'а.
- **Logs на русском или английском** — последовательно в рамках проекта (обычно английский для машиночитаемости полей).
- **Не смешивай языки в одной строке лога.** «event: 'user_login', msg: 'пользователь вошёл'» — ок; «event: 'пользователь_вошёл'» — нет (ломает downstream).

---

## Approval между фазами

**Профиль `safe`:** approval перед каждой фазой (вы уже выбрали это).
**Профиль `balanced`:** approval был один раз up-front. Между фазами — только если были явные блокеры.
**Профиль `fast`:** без approval, только в конце фазы — scoped reviewer.

---

## Переход

После завершения всех фаз → `prompts/new-project/07-post-init-sync.md`.
