# doubled-graph — FAQ

---

## Общее

### Q: Это сильно сложнее, чем просто писать код с copilot?
**A:** Да. Цена: 1–2 дня на освоение, 15–30 минут overhead в новом проекте (intent-interview + approval-gates), 5–10 минут overhead per feature (impact + detect_changes). Выигрыш — в предсказуемости и возможности поддерживать кодовую базу с ИИ длительное время без деградации. Если проект — single-file скрипт, методология overkill. Если проект доживёт до 6 месяцев и трёх контрибьютеров — окупается.

### Q: Я работаю один на pet-проекте. Мне это нужно?
**A:** Если проект — one-off скрипт, скорее всего нет. Если проект живёт дольше пары недель, имеет хотя бы 2–3 модуля, и ты планируешь возвращаться к нему — да, полная методология окупится.

**«Lite»-версии doubled-graph нет** (см. [auto-scaling.md](../methodology/auto-scaling.md) — решение 2026-04-18). Либо полная методология, либо не применяй doubled-graph. Частичное применение даёт меньше пользы, чем полный отказ. Если хочется «чего-то более лёгкого» — посмотри на BMAD-Method, Kiro-flow, GitHub Spec Kit.

### Q: Что если код уже разметан под GRACE, но по старой схеме?
**A:** Проверь якоря. GRACE v3.5+ использует ровно тот набор: `MODULE_CONTRACT`, `MODULE_MAP`, `CONTRACT:fn`, `BLOCK_*`, `CHANGE_SUMMARY`. Если твоя схема совпадает — ничего менять. Если нет (например, `BEGIN_FUNCTION`/`END_FUNCTION` старого образца) — одноразовый rename.

---

## Инструменты

### Q: doubled-graph не устанавливается (ошибка при `pip install doubled-graph`).
**A:** На apr 2026 пакет находится в этом репозитории как source, публичного PyPI-релиза пока не было. Пока устанавливай локально:
```bash
cd doubled-graph
pip install -e .
```
Следи за прогрессом — когда выпустим на PyPI, команда из getting-started заработает.

### Q: `grace` CLI не устанавливается (`bun add -g @osovv/grace-cli` не находит пакет).
**A:** Возможно, сменилось имя пакета или publisher. Проверь `https://github.com/osovv/grace-marketplace` — там в README актуальная install-команда. Исходник: `extra/research/grace-marketplace-main/` как источник истины.

### Q: FalkorDB Lite не работает (Python 3.11).
**A:** FalkorDB Lite требует Python 3.12+. Либо обнови Python, либо переключи CGC backend:
```bash
export CGC_RUNTIME_DB_TYPE=kuzu
```

### Q: Windows, Neo4j driver 6.x падает.
**A:** Известная проблема CGC. Workaround: `pip install "neo4j<6"`.

---

## Политика и процесс

### Q: Моя команда не успевает проходить approval-gates. Можно их отключить?
**A:** Нет. Отключение approval нарушает принцип 2. Если gate'ы тормозят — понижай профиль `doubled-graph multiagent-execute` (`safe` → `balanced` → `fast`) или уменьшай gran ular ность phases (больше фаз, каждая меньше).

### Q: Что делать, когда `detect_changes` постоянно возвращает drift?
**A:** Разбираться, не игнорировать. Если drift «нормален» на период (миграция, рефакторинг) — запиши в `docs/DRIFT.md` (формат описан в [drift-and-priority.md](../methodology/drift-and-priority.md)) с причиной и deadline. Без записи — gate блокирует merge.

### Q: Я случайно переключил `phase: migration` вместо `post_migration` в середине нормального workflow. Что делать?
**A:** Откати blok в `AGENTS.md` (или `doubled-graph phase set post_migration --reason "accidental switch"`). Проверь, что последний коммит не внёс семантические правки без approval (в `migration` они могли пройти свободнее). Если внёс — ревью + возможно revert.

### Q: Что делать с «я поправил prod через SSH, теперь код в git отстаёт от prod»?
**A:** Методология сознательно не решает такие случаи — они об deployment-процессе, не о коде. Если произошло — синхронизируй git (pull actual prod into a branch, merge with tests), затем применяй `on-user-manual-edit.md`.

---

## Инциденты и edge cases

### Q: `doubled-graph lint` падает с парной ошибкой, не могу найти где.
**A:** Проверь:
1. Открывающий `START_` без закрывающего `END_` (most common).
2. Имя в `CONTRACT: foo` ≠ имя в `END_CONTRACT: foo`.
3. Один и тот же `BLOCK_NAME` дважды в одном файле.

Запусти `doubled-graph lint --verbose` — он укажет строку.

### Q: `impact` возвращает пустой список callers для функции, которая очевидно вызывается.
**A:** Возможно, computed graph устарел. Запусти `doubled-graph analyze --mode full --force` и повтори. Если всё равно пусто — функция вызывается **не** напрямую (через dispatch table / reflection / string lookup) — CGC не видит. Mитигация: отметь в `MODULE_CONTRACT` через `<DynamicCalls>` (extension — пока не автоматизирован).

### Q: ИИ упорно предлагает правку, которая нарушает контракт модуля.
**A:** Проверь, что `AGENTS.md` phase-блок читается ИИ-агентом (иногда он пропускается, если `AGENTS.md` > 50 KB). Если phase правильный — ревьюй промпт, не идеологию. В `post_migration` контракт — ground-truth; ИИ должен уважать.

### Q: `doubled-graph refresh` испортил `docs/knowledge-graph.xml` — удалил CrossLinks, которые были легитимны.
**A:** Проверь в git history последний «хороший» состояние, сравни. Часто причина — computed graph не видит динамические вызовы (см. два выше). Откатить `knowledge-graph.xml` и добавить в DRIFT.md запись «D-XXX: CrossLink M-A → M-B — dynamic call not in CGC, pinned manually».

---

## Модели

### Q: Какая модель лучше для doubled-graph?
**A:** Для оптимизации **мы не целимся** во frontier. Целевые — локальные среднего размера (Qwen3-Coder-Next, DeepSeek V3.2, GLM-4.5, Llama 4 Scout). Frontier (Claude Opus, GPT-5) тоже работают, просто не оптимизируем промпты под них. См. [local-llm.md](../methodology/runtime-adapters/local-llm.md).

### Q: Qwen/DeepSeek ломают XML-артефакты при генерации. Что делать?
**A:** Включай structured decoding (XGrammar / Outlines / llguidance). Без него частота поломок — десятки процентов. Инструкции — в `local-llm.md § 3`.

### Q: ИИ в локальном режиме иногда «забывает» методологию и начинает свободно писать код.
**A:** Это ограничение длинного контекста у локальных моделей. Разбивай промпты на короткие шаги, каждый < 8 KB. Каждый шаг начинается с reminder о принципах.

---

## Вопросы к текущей реализации

### Q: Я видел `NOT_IMPLEMENTED_MVP` в ответе `detect_changes`. Это баг?
**A:** Нет, фича. `context` и `detect_changes` — stubs в Phase 1.5 MVP (см. [QUESTIONS_FOR_REVIEW.md § C-3](../QUESTIONS_FOR_REVIEW.md)). Реализация — в ближайшем follow-up. В промптах (`on-drift-detected.md`, `on-before-edit.md`) заложен fallback через `doubled-graph module show` и bash-поиск.

### Q: Эта методология проверена на реальном проекте?
**A:** Phase 5 как раз про это. На момент релиза Phase 4 drafts (apr 2026) — обкатка на игрушечном проекте + 1 миграции запланирована, но не проведена. См. [PLAN.md § Фаза 5](../PLAN.md).

### Q: Есть issues/PR?
**A:** Пока репозиторий приватный (индивидуальная работа). После `v1.0` и Phase 5 ревью — открытие и public feedback loop.
