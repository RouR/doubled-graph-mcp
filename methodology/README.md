# doubled-graph — методология разработки с ИИ

> **Статус:** Phase 2 draft, 2026-04-18.
> Часть целого проекта; корневой плавающий вход — `../INDEX.md` (будет в Phase 4). Для людей-новичков см. `../for-humans/getting-started.md`.

## Что это

doubled-graph — методология разработки программного обеспечения с ИИ-ассистентом. Расширяет публичную методологию **GRACE** ([osovv/grace-marketplace](https://github.com/osovv/grace-marketplace), MIT) тремя добавками, которых в upstream нет:

1. **Сценарий миграции legacy-кода.** Upstream GRACE предполагает генерацию с нуля; doubled-graph даёт пошаговый процесс для кодовых баз, которые уже существуют.
2. **Политика дрейфа «код ↔ артефакты».** Два режима (`migration`, `post_migration`), чёткие правила разрешения конфликтов. См. `drift-and-priority.md`.
3. **Facade-слой `doubled-graph`.** Тонкая MIT-обёртка над CodeGraphContext и grace-marketplace, выставляет ИИ только 4 инструмента методологии. См. `../docs/SPEC.md`.

## Для кого

- **Инженеры-одиночки и команды**, которым нужна предсказуемая работа с ИИ-ассистентом — чтобы правки не ломали соседние модули и документация не отставала от кода.
- **Любой размер проекта.** Методика универсальна; объём артефактов **не масштабируется** — всегда максимальная глубина. См. `auto-scaling.md` (обоснование).
- **Любой язык**, у которого есть парсер в CodeGraphContext (19 языков на 2026-04). Специфика — в `language-adapters/`.
- **Любой IDE с поддержкой MCP + tools** (Claude Code, Cursor, Codex, Continue, Windsurf, Cline, aider, roo-code, …). Специфика запуска — в `runtime-adapters/`.

**Целевые модели — локальные среднего размера** (Qwen 3, DeepSeek V3, GLM-4.5, Llama 4). На frontier-моделях тоже работает, но методология под них не оптимизируется.

## Что в этой папке

| Файл | О чём |
|---|---|
| `principles.md` | 10 принципов doubled-graph (адаптированы из GRACE с обоснованиями) |
| `workflow.md` | Общий скелет процесса + 3 сценария (новый / миграция / поддержка) |
| `artifacts.md` | XML-артефакты (`docs/*.xml`), поля, примеры |
| `auto-scaling.md` | Почему не масштабируем под размер проекта — всегда максимальная глубина |
| `tools.md` | grace-marketplace + doubled-graph: когда и что использовать |
| `drift-and-priority.md` | Режимы `migration`/`post_migration`, политика конфликтов |
| `approval-checkpoints.md` | Реальные upstream-точки одобрения + 3 профиля multiagent |
| `roles.md` | Разделение работы человек/ИИ |
| `language-adapters/` | Специфика для Python, TypeScript, Java, Rust, Go, C#, Swift + шаблон |
| `runtime-adapters/` | Конкретные конфиги для Claude Code / Cursor / Codex / Continue / Windsurf / local-llm |
| `ci-templates/` | Готовые CI-workflow (в Phase 4) |

## Предусловия (precondition, не рекомендация)

Методология **не работает** без стека:

- `grace-marketplace` (skills + CLI `grace`, Bun) — `bun add -g @osovv/grace-cli`.
- `doubled-graph` (MCP facade, Python, этот репозиторий) — `pip install doubled-graph`.
- IDE с поддержкой **tools + MCP**. Без них промпты `../prompts/**` нельзя исполнить.

Это — осознанный компромисс (см. `tools.md §1`). Методология отказывается от tool-agnostic-риторики в пользу робастности: автоматизация через инструменты даёт одинаковый результат вне зависимости от опыта пользователя.

## 10-минутная ориентация

1. Прочитай `principles.md` (4 мин).
2. Прочитай соответствующий сценарий из `workflow.md` (новый / миграция / поддержка, 3 мин).
3. Открой `../prompts/<сценарий>/00-entry-prompt.md` и вставь в ИИ (3 мин).

Детали — по мере необходимости. Все ссылки на разделы — относительные, файл открывается как standalone.

## Лицензия и источники

- doubled-graph (эта методология и `doubled-graph`) — MIT.
- Использует GRACE (osovv, MIT) и CodeGraphContext (MIT) как внешние зависимости. Не форкает их.
