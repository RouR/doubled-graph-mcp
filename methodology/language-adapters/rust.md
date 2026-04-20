# Language adapter: Rust

Адаптер покрывает stable Rust (edition 2021+).

## 1. Синтаксис комментариев

- `//` — однострочный якорь (рекомендуемый).
- `/* ... */` — многострочный, не используется для якорей.
- `///` — **doc-комментарий элемента** (аналог Javadoc), привязан к следующему item. Для якорей **не использовать** — см. Anti-patterns.
- `//!` — doc-комментарий родителя (обычно модуля). Для MODULE_CONTRACT **не использовать**.

## 2. Позиция контракта функции

Контракт функции — `//`-комментарии непосредственно перед `fn` (или `pub fn`, `async fn`, `pub async fn`). **Атрибуты** (`#[derive(...)]`, `#[tokio::main]`, `#[contracts::ensure(...)]`) — **после** `END_CONTRACT`, перед `fn`.

```rust
// START_MODULE_CONTRACT
// Module: M-AUTH-VALIDATE
// Purpose: validate JWT and resolve User
// Scope: src/auth/validate.rs
// Dependencies: M-AUTH-TOKENS
// Criticality: critical
// LINKS: UC-001, V-M-AUTH-VALIDATE-01
// END_MODULE_CONTRACT

// START_MODULE_MAP
// exports:
//   - validate_user (function)
// END_MODULE_MAP

use contracts::{requires, ensures};
use tracing::info;

// START_CONTRACT: validate_user
// PURPOSE: validate JWT, resolve user
// INPUTS: req: &Request (Authorization: Bearer header required)
// OUTPUTS: Option<User> (None if invalid, never panics)
// SIDE_EFFECTS: none
// LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
// END_CONTRACT: validate_user
#[requires(req.headers.contains_key("Authorization"))]
#[ensures(ret.is_none() || matches!(ret, Some(_)))]
pub fn validate_user(req: &Request) -> Option<User> {
    // START_BLOCK_DECODE_JWT
    let token = extract_token(req)?;
    let payload = decode_jwt(&token).ok()?;
    // END_BLOCK_DECODE_JWT

    // START_BLOCK_CHECK_CLOCK_SKEW
    if (now_ms() as i64 - (payload.iat as i64) * 1000).abs() > 60_000 {
        return None;
    }
    // END_BLOCK_CHECK_CLOCK_SKEW

    Some(payload.user)
}
```

Для методов `impl`-блока — те же правила, контракт внутри `impl { ... }`:

```rust
impl AuthService {
    // START_CONTRACT: validate
    // ...
    // END_CONTRACT: validate
    pub fn validate(&self, req: &Request) -> Option<User> { ... }
}
```

## 3. Специфика блоков

Rust использует фигурные скобки, но его особенность — **блок-выражения возвращают значение**. Это влияет на имена блоков:

- Имя блока должно отражать **семантику**, не scope. Если блок возвращает значение, имя описывает **результат**: `BLOCK_COMPUTE_HASH`, не `BLOCK_INNER`.
- `END_BLOCK` ставится перед закрывающей `}` блока-выражения.
- **`?`-оператор** (early return): если блок может завершиться через `?`, `END_BLOCK` должен стоять **до** строки с `?`, либо покрывать и последующий код (выбрать один вариант для файла).
- **`match`-выражения**: одна ветка = один BLOCK максимум. Не разрывать `match` пополам.
- **unsafe-блоки**: якорь блока допустим внутри `unsafe { ... }`, но имя **должно** явно содержать `UNSAFE_`: `BLOCK_UNSAFE_RAW_DEREF`.

## 4. Runtime-контракты

| Библиотека | Scope | Когда применять |
|---|---|---|
| **contracts** (crate) | `#[requires]`, `#[ensures]`, `#[invariant]` — DbC-атрибуты | для критических модулей; проверки отключаются в release через feature flag |
| **Type system + `Result<T, E>`** | статические гарантии | всегда; это основа Rust и покрывает большую часть того, что в других языках делает runtime-проверка |
| **proptest** / **quickcheck** | property-based testing | для алгоритмов и парсеров |
| **validator** (crate) | аннотации для serde-структур | когда данные приходят из JSON/forms и есть типичные ограничения (email, length) |

**Рекомендация doubled-graph:**

- **Critical-модули:** `contracts` + `Result<T, AppError>` на публичных границах (имя типа ошибки — выбор команды; примеры нейтральные). Текстовый контракт + формальные `#[requires]`/`#[ensures]` (они проверяются только в debug-build — осознавать это ограничение).
- **Standard-модули:** типы + `Result`; контрактные атрибуты опциональны.
- **Helper-модули:** только типы, достаточно.

Пример с `contracts`:

```rust
#[requires(input.len() > 0)]
#[ensures(ret.len() == input.len())]
fn transform(input: &[u8]) -> Vec<u8> { ... }
```

**Важно:** `contracts` по умолчанию отключается в release (`cfg(debug_assertions)`). Если нужна проверка в production — использовать feature flag `contracts/always` явно, либо дублировать критичные инварианты через `assert!` / `debug_assert!`.

## 5. Testing framework

**`cargo test`** — стандарт. Property-based — `proptest`. Async-тесты — `#[tokio::test]` или `#[async_std::test]`.

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>cargo test --package auth --lib validate -- --nocapture</Command>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
    <Marker>VALIDATE_FAIL</Marker>
  </Markers>
</Verification>
```

Тесты живут рядом с кодом: `#[cfg(test)] mod tests { ... }` в конце файла, либо в `tests/` для integration-тестов.

## 6. Structured logs

**`tracing`** — де-факто стандарт 2026. Для JSON-вывода — `tracing-subscriber` с `fmt::layer().json()`.

Конфигурация (обычно в `main.rs` / библиотечном `init_tracing`):

```rust
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

tracing_subscriber::registry()
    .with(EnvFilter::from_default_env())
    .with(fmt::layer().json())
    .init();
```

В коде:

```rust
use tracing::info;

// внутри validate_user:
info!(
    anchor = "validate_user:BLOCK_DECODE_JWT",
    module = "M-AUTH-VALIDATE",
    requirement = "UC-001",
    correlation_id = %req.correlation_id,
    belief = "payload trusted, skew=0",
    "jwt_decoded"
);
```

`%` перед `req.correlation_id` — форматирование через `Display`. Для `Debug`-форматирования — `?`.

Альтернативы: `log` + `env_logger` (legacy, без structured-поддержки), `slog` (уходит в архив).

## 7. CGC: Rust — полная поддержка

CodeGraphContext парсит Rust через tree-sitter-rust. Поддерживаются `fn`, `struct`, `enum`, `trait`, `impl`, модули, use-декларации, вызовы. Особенности:

- **`impl` блоки**: парсер корректно определяет parent context — методы в `impl Foo` привязываются к типу `Foo`. Методы в `impl Trait for Foo` — тоже к `Foo`, но знание о `Trait` в CGC ограничено.
- **Макросы (`macro_rules!`, proc-macros)**: тело макроса **не парсится**. Код, сгенерированный макросами (derive, `tokio::main`, `tracing::instrument`), не виден в графе.
- **`mod` inline vs file**: `mod foo;` и `mod foo { ... }` обрабатываются одинаково, но для inline-модуля весь код попадает в один узел файла.
- **Generics**: type parameters в сигнатурах сохраняются как текст, но не разворачиваются.

Следствие для разметки: если функция генерируется макросом (например, через `#[async_trait]`), её якори **не найдутся** в computed graph. Разметку для таких методов делать в том файле, где расположен trait, и указывать в `MODULE_MAP` с пометкой `(macro-expanded)`.

## 8. Project-layout

Cargo workspace:
```
repo/
├── Cargo.toml                       ← workspace root
├── crates/
│   └── auth/
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   └── validate.rs
│       └── tests/
│           └── validate_integration.rs
└── docs/
    ├── requirements.xml
    └── ...
```

В `development-plan.xml`:

```xml
<Paths>
  <Path>crates/auth/src/validate.rs</Path>
</Paths>
```

Для single-crate проекта путь — `src/validate.rs`.

## 9. Anti-patterns

- **Якоря в `///` doc-комментариях:**
  ```rust
  /// START_CONTRACT: validate_user   ← doc-комментарий, не якорь
  pub fn validate_user(...) { ... }
  ```
  Использовать `//`. `///` — для rustdoc.

- **Атрибут между CONTRACT и `fn`:**
  ```rust
  // END_CONTRACT: validate_user
  #[tokio::main]            ← ok, это правильно
  async fn validate_user(...) {}
  ```
  Правильный порядок: `//`-контракт → атрибуты → `fn`. Неправильно — атрибут **внутри** блока контракта.

- **Использование `#[contracts::requires(...)]` без понимания debug/release поведения:**
  без feature flag `contracts/always` проверки **не работают в release-build'е**. Критические инварианты дублировать через `assert!` или `debug_assert!`.

- **Имя блока, отражающее scope вместо семантики:**
  ```rust
  // START_BLOCK_INNER_MATCH   ← плохо: scope
  // START_BLOCK_COMPUTE_SKEW  ← хорошо: семантика
  ```

- **Контракт на функции внутри `macro_rules!` тела:** парсер якорей его **не найдёт** (макрос не expand'ится). Контракт писать на точке вызова или в trait-определении.

- **MODULE_CONTRACT как `//!`:**
  ```rust
  //! START_MODULE_CONTRACT   ← не используется
  ```
  Только обычные `//`.

## 10. Запуск doubled-graph lint на Rust-проекте

```bash
doubled-graph lint --path .
```

CLI `grace` парсит Rust через tree-sitter-rust. Cargo-плагин не требуется.

---

## Чек-лист применения

- [ ] MODULE_CONTRACT / MODULE_MAP — `//`-комментарии в начале файла, до `use`.
- [ ] CONTRACT: fn — `//`-комментарии перед `fn`, атрибуты между `END_CONTRACT` и `fn`.
- [ ] Имена блоков отражают семантику, не scope.
- [ ] `contracts`-атрибуты используются с пониманием debug/release; критические инварианты продублированы через `assert!`.
- [ ] Типы + `Result<T, E>` — основная линия защиты на границах.
- [ ] `cargo test` команда в `verification-plan.xml`, при необходимости — `proptest`.
- [ ] `tracing` + JSON-layer, все обязательные поля через key-value.
- [ ] Код, сгенерированный макросами, помечен в MODULE_MAP как `(macro-expanded)`.
- [ ] Не использовать `///` и `//!` для якорей методологии doubled-graph (это doc-комментарии rustdoc, разметка путает lint).
