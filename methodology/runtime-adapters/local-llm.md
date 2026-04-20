# Runtime adapter: локальные модели (Qwen 3 / DeepSeek V3 / GLM-4.5 / Llama 4)

**Главная точка методологии.** doubled-graph оптимизирована под **локальные модели среднего размера**. Frontier-модели (Claude Opus 4.6, GPT-5, Gemini 3) — приятный бонус, не целевой режим.

---

## 1. Целевые модели (на апрель 2026)

<!-- NEEDS-VERIFY: актуальность версий моделей и их характеристик; knowledge cutoff limitation -->

| Модель | Параметры | Контекст | VRAM (Q4) | Сильные стороны |
|---|---|---|---|---|
| **Qwen3-Coder-Next** | MoE 80B/3B active | 256K | ~24 GB | code-first; structured output |
| **DeepSeek V3.2** | 671B MoE / 37B active | 128K | high-end (не для single GPU) | рассуждения; tool use |
| **GLM-4.5** | 355B / 32B active | 128K | high-end | agentic tasks, tool calls |
| **Llama 4 Scout** | 17B active / 109B | 10M (заявлено) | ~24 GB | long context; баланс |

**Выбор по VRAM:**
- 8–16 GB: Qwen3-Coder 14B (меньшая вариация), DeepSeek-Coder V2 16B.
- 24 GB: Qwen3-Coder-Next Q4, Llama 4 Scout Q4.
- 40 GB+: DeepSeek V3.2 через vLLM multi-GPU.

**Что НЕ целевое:** Llama 2 family, первое поколение Qwen, CodeLlama — устарели на методологию apr 2026.

---

## 2. Движки запуска

| Движок | Плюсы | Минусы | Tool use |
|---|---|---|---|
| **Ollama** | простой setup, model catalog | слабый structured output | partial (function calling через adapter) |
| **vLLM** | production-grade, быстро | сложнее setup | full (OpenAI-compatible) |
| **LM Studio** | GUI, хорошо для dev-time | не для production | partial |
| **llama.cpp** | низкий уровень, контроль | руками собирать | базовое |
| **SGLang** | structured generation из коробки | молодой | full + grammars |

**Рекомендация doubled-graph для dev-time:** Ollama или LM Studio.
**Для production:** vLLM или SGLang с `--enable-auto-tool-choice` + guided decoding.

---

## 3. Structured decoding — обязательно

Для всех **финальных XML-артефактов** (`requirements.xml`, `development-plan.xml`, …) локальная модель **обязана** генерировать с structured decoding. Без него частота поломанного XML — десятки процентов, что убивает экономию от локального inference через retry-циклы.

| Инструмент | Движки |
|---|---|
| **XGrammar** | vLLM, SGLang |
| **Outlines** | vLLM, transformers |
| **llguidance** | vLLM |
| **Jsonformer** | transformers (устаревает) |

Методология ставит hard requirement: XML-артефакты в pipeline генерируются через guided decoding по XSD-схеме из `extra/research/grace-marketplace-main/.../*.template`.

<!-- NEEDS-VERIFY: актуальность XSD-файлов в grace-marketplace; существуют ли официальные XSD, или шаблоны .xml.template единственный источник схемы -->

---

## 4. Tool use — что локальные модели тянут плохо

Известные слабости (R11):

1. **Многошаговый tool loop.** Цепочка «impact → analyze → fix → verify» в одном turn — часто срывается. Митигация: orchestrator (промпт-сценарий) разбивает на явные короткие шаги, модель дергает один tool за раз.
2. **Self-verification.** Слабее frontier. Митигация: обязательный внешний gate (`doubled-graph reviewer` + `doubled-graph lint` + `detect_changes`).
3. **Structured reasoning в длинном контексте.** Теряется середина контекста. Митигация: компактные промпты < 8 KB, разметка как якоря RAG.
4. **JSON с глубокой вложенностью.** Ломается чаще плоских схем. Митигация: schema design с уплощением.

---

## 5. Промпт-паттерны для локальных моделей

- **Короткие структурированные промпты** (< 8 KB). Все промпты Phase 3 будут писаться под это ограничение.
- **System vs user разделение.** System — контракт и роль; user — одна задача. Длинные «все инструкции в user» — хуже работают.
- **Chain-of-thought явный.** Для agentic задач — добавляй `<think>...</think>` блок (если модель поддерживает thinking).
- **Структурированные ответы через XML-теги** вместо JSON — локальные модели генерят XML стабильнее.
- **Avoid refusal-heavy templates.** Qwen / DeepSeek реагируют хуже frontier на «не можешь сделать X».

---

## 6. IDE-хосты для локальных моделей

- **Continue** — first-class для Ollama/vLLM. `.continue/config.json` с model provider.
- **Cline** — похоже, via OpenAI-compatible endpoint.
- **aider** — CLI, поддерживает Ollama напрямую.
- **Claude Code** — **не** работает с локальными моделями; это клиент Anthropic API.
- **Cursor** — поддержка custom models через OpenAI-compatible прокси.

Методология совместима со всеми, где есть **MCP + tools**. Если local-LLM клиент без MCP — используй **CGC MCP напрямую** (теряем facade-ценность, но 80% методологии работает).

---

## 7. Что локальные модели не тянут — делегируем

**Reviewer** (в `doubled-graph multiagent-execute --profile safe`) — запустить на frontier-модели, если доступна; локальные — на worker-роли.

Причина: reviewer даёт go/no-go, ошибка review дорогая. Worker ошибка — ловится reviewer'ом.

---

## 8. Установка минимальная (на 24 GB GPU)

```bash
# 1. Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3-coder:30b-q4

# 2. doubled-graph tooling
pip install doubled-graph
bun add -g @osovv/grace-cli
doubled-graph init-hooks --post-commit

# 3. IDE (Continue)
# через VSCode extension → config.json с provider=ollama, model=qwen3-coder:30b-q4

# 4. MCP для локальной модели через Continue — см. continue.md
```

<!-- NEEDS-VERIFY: реальные имена моделей в ollama library (qwen3-coder:30b-q4) на apr 2026 -->

---

## 9. Eval для локальных моделей

См. `approval-checkpoints.md § 4`. Дополнительно:

- Measurement: SWE-bench Pro (SEAL), SWE-Rebench, LiveCodeBench.
- SWE-bench Verified **не использовать как приёмку** (контаминация, см. memory `project_otel_dropped.md` — аналогичный disclaimer про bench).
- Для своей методологии — golden dataset из собственной базы fix-коммитов (10–50 кейсов).

---

## 10. Externalize state — критично для длинных диалогов

Промпты с многошаговым пользовательским диалогом (`01-intent-interview`, `02-reconstruct-intent`) обязаны писать накопленный state в `.doubled-graph/drafts/<name>.md` после каждой батчи ответов. Финальный синтез `docs/*.xml` читает оттуда, а не из истории чата.

**Почему:** на Qwen 3 / DeepSeek V3 / Llama 4 с 32K контекстом — к 10-му вопросу интервью модель начинает галлюцинировать ответы из Блока A. Externalize-паттерн фиксирует данные на диске, синтез становится детерминистичным.

Детали — `methodology/principles.md § Операционный паттерн — externalize state`.

---

## 11. Известные ловушки

- **Context window врёт.** Модель заявляет 256K, но quality проседает после ~32K. Тестируй с реальным контекстом.
- **Q4 vs FP16.** Quantization даёт 4x VRAM savings, но на code и structured output — заметная просадка. Q8 — разумный компромисс если позволяет память.
- **Tool-choice auto.** Некоторые локальные модели с `tool_choice=auto` зацикливаются на одном tool. Force `required` или explicit name.
- **Memory management.** Ollama по умолчанию выгружает модель из VRAM через 5 минут idle. Для IDE-use — `OLLAMA_KEEP_ALIVE=-1`.
