# Language adapter template — `<язык>`

**Структура адаптера** (этот файл — шаблон, копируй и заполняй).

## 1. Синтаксис комментариев

Какой маркер комментария используется для якорей: `//`, `#`, `///`, `/*…*/`, `(**…*)` и т. п.

## 2. Позиция контракта функции

Где размещается `START_CONTRACT: fn / END_CONTRACT: fn`:
- перед определением функции (большинство языков);
- в docstring сразу под `def ...:` (Python, OCaml);
- в атрибуте/annotation (Rust `///`, C# XML doc).

## 3. Специфика разметки блоков

Ограничения языка, которые влияют на блоки:
- JS/TS/Java: фигурные скобки позволяют блоки произвольного размера;
- Python: блоки по отступу, `END_BLOCK` ставится **перед** dedent;
- Go: `defer` может ломать ожидание, что блок завершается на `}`;
- Rust: блоки-выражения возвращают значение — имя блока должно отражать semantic a не scope.

## 4. Рекомендованные runtime-контракты

Библиотеки для pre/post/invariant (из R3):
- Python: `icontract`, `deal`, `pydantic`, `beartype`.
- TS: `zod`, `effect`, runtime type-check через декораторы.
- Java: Bean Validation, `cofoja`.
- Rust: `contracts` crate.
- Go: — (нет зрелых; использовать unit-тесты).
- C#: Code Contracts (legacy), Roslyn analyzers.
- Swift: `precondition`, `assert`.

Когда применять — на границах модуля, не внутри. См. § «Политика runtime-контрактов».

## 5. Testing framework

Рекомендованный фреймворк для `verification-plan.xml § Command`:
- Python — pytest;
- TS — vitest (или jest для legacy);
- Java — JUnit 5;
- Rust — `cargo test` (+ `proptest`);
- Go — `go test`;
- C# — xUnit;
- Swift — XCTest.

## 6. Log-формат

Как пишутся structured logs на этом языке:
- Python — `structlog` / `loguru`.
- TS — `pino` / `winston`.
- Java — SLF4J + logstash-logback-encoder.
- Rust — `tracing`.
- Go — `log/slog` (stdlib с 1.21).
- C# — Serilog.
- Swift — `os.Logger` + JSON formatter.

Поля — см. `../artifacts.md § Structured logs`.

## 7. CGC: известные ограничения парсера

Из сводки по extra/research/CodeGraphContext-main/:
- Haskell: парсер unstable.
- Swift: работает, но неполное покрытие protocols.
- Elixir: ограничения на macros.

Проверяй актуальное состояние: `extra/research/CodeGraphContext-main/src/codegraphcontext/tools/languages/<язык>.py`.

## 8. Project-layout соглашения

Где живут файлы:
- tests: `tests/` (Python), `src/**/*.test.ts` (TS), `src/**.rs` с `#[cfg(test)]` (Rust), `test/` (Java/Maven).
- Конвенция для `Paths` в `development-plan.xml § Module` — абсолютные от корня репо.

## 9. Примеры разметки

Минимум — 1 пример функции с полной разметкой (MODULE_CONTRACT + CONTRACT + BLOCK) + 1 пример класса/модуля.

## 10. Anti-patterns

Что **не делать** на этом языке:
- Python: не ставить контракт перед `def` — он будет проигнорирован как комментарий; должен быть в docstring.
- TS: не использовать старые `@param` JSDoc для контрактов — рвётся парсинг.
- Go: не совмещать `// Deprecated: ...` с блоком контракта.

---

## Чек-лист готовности адаптера

- [ ] Синтаксис комментариев определён.
- [ ] Позиция контракта функции задокументирована (с примером).
- [ ] Правила блоков учитывают особенности языка.
- [ ] Список рекомендованных runtime-библиотек с версиями (или «нет — обоснование»).
- [ ] Testing framework и команда для `verification-plan.xml § Command`.
- [ ] Структурированные логи — библиотека + пример.
- [ ] Зафиксированы CGC-ограничения для языка (если есть).
- [ ] Пример разметки функции + класса.
- [ ] Anti-patterns описаны.
