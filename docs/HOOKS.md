# doubled-graph — HOOKS (v0.1 draft)

**Цель:** автоматически поддерживать computed graph в свежем состоянии и фиксировать provenance AI-правок, не требуя ручных вызовов `analyze`. Делаем **трёхуровневый** набор: обязательный baseline — git hook; ускоритель для Claude Code — PostToolUse; опциональный — prepare-commit-msg.

**Принцип:** baseline должен работать **без** специфичного IDE. Ускоритель сокращает окно stale-index между правками, но не требуется для корректности.

---

## 1. Baseline: git `post-commit` hook

### 1.1 Что делает

После каждого `git commit` (локального) запускает `doubled-graph analyze --mode incremental --since-ref HEAD~1`. Инкрементальный, потому что уже знаем какие файлы тронуты коммитом.

### 1.2 Почему именно `post-commit`, а не `pre-commit`

- `pre-commit` блокирует коммит на время анализа — плохо для UX (даже 2-секундный delay раздражает).
- Корректность: если анализ в `pre-commit` упал → коммит заблокирован → пользователь скорее всего поставит `--no-verify` → hook вообще перестаёт помогать.
- `post-commit` асинхронен по смыслу: коммит состоялся, индекс догоняет.
- Для **pre-commit** проверок (lint, detect_changes) у нас отдельная рекомендация — CI, см. §4.

### 1.3 Shell-скрипт (устанавливается `doubled-graph init-hooks`)

`.git/hooks/post-commit`:

```bash
#!/usr/bin/env bash
# Installed by doubled-graph init-hooks (v0.1.0)
# Purpose: refresh computed graph after commit.
# To disable: chmod -x .git/hooks/post-commit

set -u

if ! command -v doubled-graph >/dev/null 2>&1; then
  exit 0
fi

# Пропускаем, если коммит от hook'а самого doubled-graph (петля)
if [[ "${DOUBLED_GRAPH_INHIBIT_HOOK:-0}" = "1" ]]; then
  exit 0
fi

# Фоновый запуск — не блокируем терминал
(
  doubled-graph analyze --mode incremental --since-ref HEAD~1 \
    >> .doubled-graph/logs/post-commit.log 2>&1
) &

exit 0
```

**Ключевые решения:**
- `set -u`, не `set -e`: ошибка анализа **не** должна ломать git. Логируем и идём дальше.
- Фоновый запуск (`&`) — коммит завершается мгновенно. Цена: возможен rare race, если следующий коммит идёт до окончания анализа предыдущего. Митигация — advisory-lock в `doubled-graph` (`.doubled-graph/.lock`, при занятости пропускаем новый инкремент — будет подхвачен следующим).
- Защита от петли — если сам `doubled-graph` решит коммитить (например, обновляет `.doubled-graph/cache/` и это попало в staging) — переменная `DOUBLED_GRAPH_INHIBIT_HOOK` отключает hook.
- `chmod -x` — задокументированный способ отключения.

### 1.4 Установка

```bash
doubled-graph init-hooks --all            # устанавливает все рекомендованные hooks
doubled-graph init-hooks --post-commit    # ставит один конкретный (аналогично --claude-code / --prepare-commit-msg)
doubled-graph init-hooks --dry-run        # печатает, что поставит, без реальной записи
```

**Совместимость с существующим `post-commit`.** Если hook уже есть:
- `init-hooks` не затирает. Предлагает:
  1. добавить `doubled-graph` вызов в конец существующего файла (patch),
  2. сохранить оригинал как `.git/hooks/post-commit.backup` и поставить свой,
  3. отказаться и показать команду, которую пользователь вставит сам.

**Совместимость с `husky`, `pre-commit` (фреймворк), `lefthook`.**
- Если обнаружен `.husky/` или `lefthook.yml` — предлагаем patch в их конфиге, а не в raw `.git/hooks/`.
- Не конкурируем с ними: наш baseline уживается с любым из них.

### 1.5 CI/remote

- На CI `git commit` обычно не вызывается → hook не срабатывает → **нужно явно** запускать `doubled-graph analyze --mode full` в CI-workflow перед `detect_changes`. Шаблон — в `methodology/ci-templates/` (Фаза 2).
- На `git pull` / `git merge` — hook **не** срабатывает (`post-commit` только на локальных коммитах). Для этих случаев пользователи запускают `doubled-graph analyze --mode incremental --since-ref <pre-merge-HEAD>` вручную ИЛИ через IDE-интеграцию (см. §2).

---

## 2. Ускоритель: Claude Code PostToolUse hook

### 2.1 Что даёт

Между коммитами агент может сделать 10 правок файлов (каждая через `Edit`/`Write` tool). Без PostToolUse hook computed graph остаётся стылым до следующего коммита. `impact` и `context` на таких правках — слепы.

PostToolUse hook запускает `doubled-graph analyze --mode incremental --paths <changed>` **после каждой правки файла**. Окно stale сокращается до секунд.

### 2.2 Конфигурация

В `.claude/settings.json` (или `~/.claude/settings.json`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "doubled-graph analyze --mode incremental --paths \"$CLAUDE_FILE_PATH\" --silent"
          }
        ]
      }
    ]
  }
}
```

**Ключевые решения:**
- Matcher ограничен tool'ами, реально изменяющими файлы (`Edit`, `Write`, `MultiEdit`). Не матчим `Read`, `Bash` etc.
- `--silent` — hook не должен флудить в UI. Логируется в `.doubled-graph/logs/`.
- `$CLAUDE_FILE_PATH` — переменная от Claude Code, содержит путь файла, тронутого последним tool'ом. Не полагаемся на неё для нескольких файлов сразу — в этом случае hook запускается N раз (это ОК).

### 2.3 Устанавливается автоматически

`doubled-graph init-hooks --claude-code` добавляет нужный блок в `.claude/settings.json` через merge (не перезатирая существующие hooks). Если `settings.json` уже содержит PostToolUse-хуки — конфликтов не создаём, добавляем **в конец массива**.

Альтернативно, пользователь сам ставит через `update-config` skill: «добавь PostToolUse-хук `doubled-graph analyze --mode incremental --paths "$CLAUDE_FILE_PATH" --silent` с matcher Edit|Write|MultiEdit».

### 2.4 Что с другими IDE

- **Cursor:** нет PostToolUse-хуков (по R7 на апрель 2026). Baseline `post-commit` — единственный вариант. `detect_changes` на запрос агента компенсирует.
- **Codex / Windsurf / Continue / Cline:** уточнить в runtime-adapters (Фаза 2). Если поддерживают хуки — описать там.
- **Aider:** есть `chat.add_file` callback — можно привязать. Описано в `methodology/runtime-adapters/aider.md` (Фаза 2).

---

## 3. Опциональный: `prepare-commit-msg` для provenance

### 3.1 Зачем

Методология различает AI-код и ручные правки (§10.1 черновика, R4). Без маркировки агент не может решить, доверять ли коду как «только что сгенерированному» или как «тронутому человеком». Claude Code уже добавляет trailer `Co-Authored-By: Claude <noreply@anthropic.com>` — но не во всех случаях (локальный commit вручную через terminal — без него).

### 3.2 Что делает hook

`prepare-commit-msg` смотрит список файлов коммита. Если **все** файлы были тронуты последним tool-use агента (наш `.doubled-graph/logs/` знает это) → добавляет trailer:

```
DG-Authored: ai (session-id abc123)
```

Если часть файлов — не из tool-use → добавляет:

```
DG-Authored: mixed
```

Полностью ручная правка → trailer не добавляется.

### 3.3 Почему опциональный

- Риск false positives (файл тронуто tool'ом, потом пользователь вручную ещё поправил — корректно было бы `mixed`, но наш heuristic видит только tool-use из последнего окна).
- Часть команд принципиально не хочет автоматических trailer'ов.
- Методология НЕ требует этого hook'а для корректности `detect_changes` — он обходится без provenance. Это сугубо для `impact` risk и для `on-user-manual-edit` промпта.

Рекомендация: **выключен по умолчанию**, включается явно:

```bash
doubled-graph init-hooks --prepare-commit-msg   # явно просит поставить
```

---

## 4. CI-шаблон

В `methodology/ci-templates/` (Фаза 2) будут готовые YAML для популярных CI (GitHub Actions, GitLab CI). Общий flow:

```
1. checkout
2. setup Python + Bun
3. pip install doubled-graph  ; bun add -g @osovv/grace-cli
4. doubled-graph analyze --mode full   ← CI стартует с чистого листа
5. doubled-graph detect_changes --scope compare --base-ref ${{ github.base_ref }}
6. grace lint
7. upload .doubled-graph/logs как artifact
```

Шаги 4–6 — обязательные gate'ы. 7 — для поственортема инцидентов.

---

## 5. Взаимодействие уровней

Пример: пользователь работает в Claude Code, агент делает 5 правок → commit'ит.

| Момент | Что срабатывает | Что в индексе |
|--------|-----------------|----------------|
| tool-use 1 (Edit file A) | PostToolUse → `analyze --paths A` | A свежий |
| tool-use 2 (Edit file B) | PostToolUse → `analyze --paths B` | A, B свежие |
| … | … | … |
| tool-use 5 (Edit file E) | PostToolUse → `analyze --paths E` | A–E свежие |
| `git commit` | `post-commit` → `analyze --mode incremental --since-ref HEAD~1` | всё уже свежее; analyze no-op (всё совпадает с fingerprint) |
| [опц] `prepare-commit-msg` | добавляет `DG-Authored: ai` |  |

Без Claude Code (например, Cursor):

| Момент | Что срабатывает | Что в индексе |
|--------|-----------------|----------------|
| правка в IDE | ничего | сталый |
| `git commit` | `post-commit` → `analyze --mode incremental` | свежий |

Между правками, если агент в Cursor вызвал `impact` до коммита — он работает на stale index. В этом случае `impact` в выходе помечает `meta.index_freshness_s` > threshold → агент сначала должен позвать `analyze --mode incremental --paths <touched>`, потом `impact`. Это зашито в промпте `prompts/maintenance/on-before-edit.md` (Фаза 3).

---

## 6. Команды управления

```
doubled-graph init-hooks [--all] [--post-commit] [--claude-code] [--prepare-commit-msg] [--dry-run]
# uninstall — руками: `chmod -x .git/hooks/post-commit` (см. § 1.3) и удаление PostToolUse-блока в .claude/settings.json.
# Отдельного doubled-graph uninstall-hooks в MVP нет — планируется после ревью (см. QUESTIONS_FOR_REVIEW § C).
```

---

## 7. Безопасность и privacy

- Hook'и не отправляют ничего наружу — вся телеметрия в локальный `.doubled-graph/logs/`.
- Trailer `DG-Authored` — локальное значение; коммитится только если пользователь явно включил prepare-commit-msg.
- `.doubled-graph/logs/` **должно быть** в `.gitignore` (`doubled-graph init-hooks` добавляет запись автоматически).

`.gitignore` default:

```
.doubled-graph/logs/
.doubled-graph/cache/
# config.json — коммитится, это часть репо-конфигурации
# code-fingerprint.json — можно либо закоммитить для team consistency, либо игнорировать; решает команда.
```

---

## 8. Что НЕ делают hooks

- **Не коммитят никакие файлы.** Это ответственность агента/пользователя. Hook только читает git-state и пишет в `.doubled-graph/`.
- **Не запускают `detect_changes`.** Это дорого и блокирует; `detect_changes` — по явному вызову из промпта или из CI.
- **Не правят `docs/*.xml`.** Это делает `doubled-graph refresh` / `doubled-graph plan` по запросу.

---

## 9. Статус в MVP (Фаза 1.5)

- [x] Спецификация (этот файл).
- [ ] `doubled-graph init-hooks --post-commit` — реализовать в MVP.
- [ ] `doubled-graph init-hooks --claude-code` — реализовать в MVP (JSON-merge).
- [ ] `prepare-commit-msg` — stub, возвращает `NOT_IMPLEMENTED_MVP` с пояснением.
- [ ] CI-шаблон — откладываем в Фазу 2 (methodology/ci-templates/).
