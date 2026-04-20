# Language adapter: Swift

Адаптер покрывает Swift 5.9+. Для Objective-C / mixed-проектов применим частично — разметка работает в `.swift`-файлах, `.m`/`.mm` не индексируются CGC.

## 1. Синтаксис комментариев

- `//` — однострочный якорь (рекомендуемый).
- `/* ... */` — многострочный, не используется.
- `///` — **Swift-doc-комментарий** (markdown-based). Для якорей **не использовать**.
- `/** ... */` — DocC-блок; для якорей не использовать.

## 2. Позиция контракта функции

Контракт функции/метода — `//`-комментарии непосредственно перед `func`. **Атрибуты** (`@MainActor`, `@objc`, `@available(...)`, `@discardableResult`) — **после** `END_CONTRACT`, перед `func`.

```swift
// START_MODULE_CONTRACT
// Module: M-AUTH-VALIDATE
// Purpose: validate JWT and resolve User
// Scope: Sources/Auth/AuthValidator.swift
// Dependencies: M-AUTH-TOKENS
// Criticality: critical
// LINKS: UC-001, V-M-AUTH-VALIDATE-01
// END_MODULE_CONTRACT

// START_MODULE_MAP
// exports:
//   - AuthValidator.validateUser (method)
// END_MODULE_MAP

import Foundation
import os

public struct AuthValidator {
    private let logger = Logger(subsystem: "com.example.auth", category: "validate")

    // START_CONTRACT: validateUser
    // PURPOSE: validate JWT, resolve user
    // INPUTS: req: Request (Authorization: Bearer header required)
    // OUTPUTS: User? (nil if invalid, never throws)
    // SIDE_EFFECTS: none
    // LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
    // END_CONTRACT: validateUser
    @discardableResult
    public func validateUser(_ req: Request) -> User? {
        // START_BLOCK_DECODE_JWT
        guard let token = extractToken(req) else { return nil }
        guard let payload = try? decodeJwt(token) else { return nil }
        // END_BLOCK_DECODE_JWT

        // START_BLOCK_CHECK_CLOCK_SKEW
        let nowMs = Int64(Date().timeIntervalSince1970 * 1000)
        let skew = abs(nowMs - payload.iat * 1000)
        if skew > 60_000 { return nil }
        // END_BLOCK_CHECK_CLOCK_SKEW

        return payload.user
    }
}
```

## 3. Специфика блоков

- `END_BLOCK_NAME` ставится перед закрывающей `}` или перед `return`.
- **`guard`-statements**: если весь `guard`-блок — единая semantic unit, оборачивать его одним BLOCK с именем `BLOCK_GUARD_<CHECK>`. Не ставить якорь между `guard ... else { ... }` и последующим кодом (это сломает парность).
- **Closures** (`{ x in ... }`): якорь блока допустим внутри closure, имя должно указывать на это: `BLOCK_CLOSURE_MAP_USERS`.
- **`do`/`catch`**: якорь блока покрывает **всю конструкцию**, не разрывать `do` и `catch`.
- **`async`/`await` / `Task { ... }`**: разметка идентична синхронному коду. Для `Task { ... }`-closure — имя `BLOCK_TASK_<NAME>`.
- **`actor`-методы**: актёр-изоляция на разметку не влияет, но в имени блока, если доступ идёт через actor-границу, полезно указать `BLOCK_ACTOR_HOP_<NAME>` (опционально).

## 4. Runtime-контракты

Swift **не имеет** design-by-contract библиотек с `@requires`/`@ensures`-атрибутами. Stdlib предоставляет:

| Инструмент | Scope | Когда применять |
|---|---|---|
| **`precondition(_:)`** | runtime-инвариант, срабатывает всегда (release тоже) | критические условия на границах |
| **`preconditionFailure(_:)`** | unreachable + сообщение | недостижимые ветки switch/guard |
| **`assert(_:)`** / **`assertionFailure(_:)`** | работает только в debug-build'е | development-проверки |
| **`fatalError(_:)`** | немедленная остановка, release тоже | непоправимые состояния |
| **Result-типы + `throws`** | статические гарантии | всегда на публичных API |

Типичные community-решения (`SwiftAssertion`, property wrappers для валидации) есть, но ни одно не является де-факто стандартом в апреле 2026.

**Рекомендация doubled-graph:**

- **Critical-модули:** `precondition` на входных параметрах + `throws`-функции с типизированными ошибками + текстовый контракт.
- **Standard-модули:** `throws` + `guard` + `assert` в debug.
- **Helper-модули:** только типы и тесты.

```swift
public func validateUser(_ req: Request) -> User? {
    precondition(!req.authorization.isEmpty, "Authorization header must be present")
    // ...
}
```

**Важно:** `precondition` убивает процесс при срабатывании — использовать только для условий, которые реально невозможны при корректных вызовах. Для пользовательского ввода — `guard` + `return nil` / `throw`.

## 5. Testing framework

**XCTest** — стандарт. **Swift Testing** (новый фреймворк, 2024+) — альтернатива, активно развивается, но в апреле 2026 XCTest всё ещё доминирует в production-кодбазах.

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>swift test --filter AuthValidatorTests</Command>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
    <Marker>VALIDATE_FAIL</Marker>
  </Markers>
</Verification>
```

Для Xcode-проектов: `xcodebuild test -scheme Auth -destination 'platform=iOS Simulator,name=iPhone 15'`. Для property-based: `SwiftCheck`.

## 6. Structured logs

**`os.Logger`** (Apple OS, iOS 14+/macOS 11+) — рекомендованный API для Apple-платформ. Для серверного Swift (Linux) — `swift-log` + JSON-backend (`swift-log-format-plus` или вручную).

`os.Logger` из коробки JSON **не пишет** — он использует бинарный формат `OSLogStore`. Для doubled-graph нужен JSON-вывод, поэтому:

- на Apple-платформах использовать кастомный JSON-formatter поверх `os.Logger` (или параллельный writer);
- на Linux/server — `swift-log` + `Logging` API, с JSON-handler'ом.

Пример с `swift-log` + кастомный JSON-handler:

```swift
import Logging

LoggingSystem.bootstrap { label in
    JSONLogHandler(label: label)
}

let logger = Logger(label: "com.example.auth")

// внутри validateUser:
logger.info("jwt_decoded", metadata: [
    "anchor": "validateUser:BLOCK_DECODE_JWT",
    "module": "M-AUTH-VALIDATE",
    "requirement": "UC-001",
    "correlation_id": "\(req.correlationId)",
    "belief": "payload trusted, skew=0",
])
```

`JSONLogHandler` — пишется руками (~50 строк) или берётся из небольших community-пакетов. Это **известное ограничение** Swift для structured logging.

## 7. CGC: Swift — частичная поддержка

CodeGraphContext парсит Swift через tree-sitter-swift. Поддерживаются: `func`, `class`, `struct`, `enum`, `protocol`, `actor`, `init`, variable declarations, imports, calls. **Ограничения (зафиксированы по коду `extra/research/CodeGraphContext-main/src/codegraphcontext/tools/languages/swift.py`):**

- **`extension`-блоки не парсятся отдельно.** Методы, объявленные в `extension Foo { ... }`, попадают в граф как функции, но связь с типом `Foo` может быть потеряна или восстановлена только по эвристике. Для разметки: якорь `MODULE_MAP` в файле с extension перечисляет методы явно, не полагаясь на CGC.
- **Protocol conformance по файлам не восстанавливается.** Если `class Foo: Protocol` объявлен в одном файле, а методы протокола — в extension другого файла, CGC **не свяжет** их между собой. Для `impact`-анализа это означает: изменение protocol-метода может не показать extension-конформанс как затронутый.
- **Generics (`<T: Equatable>`)**: type parameters сохраняются как текст, не разворачиваются.
- **Property wrappers** (`@State`, `@Published`, custom): парсятся как переменные; сгенерированные accessors (`$x`, `_x`) невидимы.
- **Result builders / DSL** (SwiftUI body, function builders): парсер видит `body` как одну функцию, но тело (декларативный UI) не даёт useful symbol'ов. Якоря блоков внутри `body` допустимы, но их связь с рендерингом — только по соглашению.
- **Actor-методы** — парсер их распознаёт (через `declaration_kind: "actor"`), но isolation-семантика в графе не отражена.

**Следствие для doubled-graph:**
1. Для любого файла, содержащего `extension`, явно заполнять `MODULE_MAP` со всеми публичными методами.
2. Если модуль охватывает несколько файлов с extension'ами, `Paths` в `development-plan.xml` перечисляет все эти файлы — не полагаться на CGC для автоматического склеивания.
3. `doubled-graph impact` для Swift **может недооценивать** blast radius при изменениях protocol default implementations. В `development-plan.xml` для critical-модулей на Swift указывать `criticality="critical"` и дополнительно проверять вручную.

## 8. Project-layout

Swift Package Manager:
```
repo/
├── Package.swift
├── Sources/
│   └── Auth/
│       ├── AuthValidator.swift
│       └── Request.swift
├── Tests/
│   └── AuthTests/
│       └── AuthValidatorTests.swift
└── docs/
    ├── requirements.xml
    └── ...
```

Для Xcode-проектов (`.xcodeproj`): структура произвольная, но `Paths` в `development-plan.xml` указывает на фактические `.swift`-файлы от корня репо.

```xml
<Paths>
  <Path>Sources/Auth/AuthValidator.swift</Path>
</Paths>
```

## 9. Anti-patterns

- **Якоря в `///` DocC-комментариях:**
  ```swift
  /// START_CONTRACT: validateUser   ← парсер якорей не видит DocC
  public func validateUser(...) {}
  ```
  Использовать `//` перед `///` или вместо него.

- **Атрибут внутри блока контракта:**
  ```swift
  // START_CONTRACT: validateUser
  @MainActor                        ← неправильно
  // END_CONTRACT: validateUser
  public func validateUser(...) {}
  ```
  Атрибуты — после `END_CONTRACT`.

- **`precondition` на пользовательском вводе:**
  ```swift
  public func validate(_ req: Request) -> User? {
      precondition(req.authorization.hasPrefix("Bearer "))  ← роняет процесс
  }
  ```
  Это должна быть `guard req.authorization.hasPrefix("Bearer ") else { return nil }`. `precondition` — только для инвариантов, которые **невозможно** нарушить при корректном вызове.

- **Extension без явной ссылки в MODULE_MAP:** если метод объявлен в `extension Foo { ... }` и не указан в `MODULE_MAP`, его связь с модулем может потеряться в CGC. Перечислять явно.

- **MODULE_CONTRACT внутри `class`/`struct`:** модуль-контракт идёт **в начале файла**, не внутри типа, даже если в файле всего один тип.

- **Использование `os.Logger` напрямую для JSON-логов без formatter'а:** `os.Logger` пишет бинарный `OSLog`, а не JSON. Для doubled-graph нужен JSON — либо `swift-log` + JSON-handler, либо параллельный writer.

## 10. Запуск doubled-graph lint на Swift-проекте

```bash
doubled-graph lint --path .
```

CLI `grace` парсит Swift через tree-sitter-swift — та же грамматика, что использует CGC, **с теми же ограничениями**. Extension-методы могут не попадать в отчёт `doubled-graph lint`, если не указаны в `MODULE_MAP`. Рекомендация: перед merge запускать `grace lint --strict`, который ругается на методы без явного MODULE_MAP-entry.

---

## Чек-лист применения

- [ ] MODULE_CONTRACT / MODULE_MAP — `//`-комментарии в начале файла, до `import`.
- [ ] CONTRACT: func — `//`-комментарии перед `func`; атрибуты между `END_CONTRACT` и `func`.
- [ ] BLOCK_NAME — `//`, `END_BLOCK` перед `}` или `return`.
- [ ] Closures и Task-блоки в имени содержат `_CLOSURE_` / `_TASK_`.
- [ ] `precondition` только для unreachable-состояний; для валидации ввода — `guard`/`throw`.
- [ ] Все методы из `extension`-блоков явно перечислены в MODULE_MAP (CGC не связывает extensions автоматически).
- [ ] `Paths` в `development-plan.xml` перечисляет все файлы модуля, включая extension-файлы.
- [ ] `swift test` (XCTest) команда в `verification-plan.xml`.
- [ ] Для JSON-логов — `swift-log` + JSON-handler, не `os.Logger` напрямую.
- [ ] Для critical-модулей на Swift — ручная верификация blast radius (CGC-`impact` может недооценивать из-за extension/protocol-ограничений).
