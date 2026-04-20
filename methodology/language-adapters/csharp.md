# Language adapter: C#

Адаптер покрывает .NET 6+ (LTS). Для .NET Framework 4.x применим частично — SLF4J-аналогов меньше, Code Contracts ещё работают, но это legacy-сценарий.

## 1. Синтаксис комментариев

- `//` — однострочный якорь (рекомендуемый).
- `/* ... */` — многострочный, не используется.
- `///` — **XML-doc-комментарий** (аналог Javadoc). Для якорей **не использовать** — см. Anti-patterns.

## 2. Позиция контракта функции

Контракт метода — `//`-комментарии непосредственно перед сигнатурой. **Атрибуты** (`[HttpPost]`, `[Authorize]`, `[ValidateAntiForgeryToken]`) — **после** `END_CONTRACT`, перед сигнатурой.

```csharp
// START_MODULE_CONTRACT
// Module: M-AUTH-VALIDATE
// Purpose: validate JWT and resolve User
// Scope: src/Auth/AuthValidator.cs
// Dependencies: M-AUTH-TOKENS
// Criticality: critical
// LINKS: UC-001, V-M-AUTH-VALIDATE-01
// END_MODULE_CONTRACT

// START_MODULE_MAP
// exports:
//   - AuthValidator.ValidateUser (method)
// END_MODULE_MAP

namespace Example.Auth;

using Microsoft.Extensions.Logging;
using FluentValidation;

public class AuthValidator
{
    private readonly ILogger<AuthValidator> _log;

    public AuthValidator(ILogger<AuthValidator> log) => _log = log;

    // START_CONTRACT: ValidateUser
    // PURPOSE: validate JWT, resolve user
    // INPUTS: req: HttpRequest (Authorization: Bearer header required)
    // OUTPUTS: User? (null if invalid, never throws)
    // SIDE_EFFECTS: none
    // LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
    // END_CONTRACT: ValidateUser
    [HttpGet("validate")]
    public User? ValidateUser(HttpRequest req)
    {
        // START_BLOCK_DECODE_JWT
        var token = ExtractToken(req);
        var payload = DecodeJwt(token);
        // END_BLOCK_DECODE_JWT

        // START_BLOCK_CHECK_CLOCK_SKEW
        if (Math.Abs(DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - payload.Iat * 1000L) > 60_000L)
            return null;
        // END_BLOCK_CHECK_CLOCK_SKEW

        return payload.User;
    }
}
```

## 3. Специфика блоков

- `END_BLOCK_NAME` ставится перед закрывающей `}` или перед `return`/`throw`.
- **`using`-блоки** (`using (var x = ...)` и `using var x = ...;` с неявным scope): якорь блока должен покрывать **весь scope `using`**, включая `Dispose()`.
- **`switch` expression** (C# 8+): каждая arm — не более одного BLOCK; не разрывать.
- **`async`/`await`**: разметка идентична синхронному коду. Не ставить якори между `await` и продолжением в той же строке.
- **Pattern-matching** (`is`, `when`): якорь блока допустим вокруг `if` с pattern-matching'ом, но имя должно отражать паттерн, не механику.
- **Expression-bodied methods** (`public int Foo() => 42;`) не содержат блоков — только function-level контракт.

## 4. Runtime-контракты

**.NET Code Contracts** (`System.Diagnostics.Contracts`) — **deprecated** в .NET 5+, не поддерживаются. Не использовать.

Живые альтернативы:

| Подход | Scope | Когда применять |
|---|---|---|
| **FluentValidation** | валидация DTO через fluent API | стандарт для ASP.NET Core входных моделей |
| **DataAnnotations** (`[Required]`, `[Range]`) | декларативные атрибуты в моделях | простые ограничения, ModelState-интеграция |
| **Roslyn Analyzers** + **Nullable reference types** (`<Nullable>enable</Nullable>`) | compile-time защита | обязательно в .NET 6+ |
| **`ArgumentException.ThrowIfNull(...)`** / **`ArgumentOutOfRangeException.ThrowIf*`** (.NET 6/7+) | ручные precondition-чеки | везде, где типы не покрывают |

**Рекомендация doubled-graph:**

- **Critical-модули:** FluentValidation на входящих DTO + явные `ArgumentException.ThrowIfNull(...)` в теле метода + Nullable reference types включены.
- **Standard-модули:** DataAnnotations или FluentValidation на границах контроллеров.
- **Helper-модули:** Nullable reference types + Roslyn analyzers + unit-тесты.

```csharp
using FluentValidation;

public class RequestValidator : AbstractValidator<Request>
{
    public RequestValidator()
    {
        RuleFor(r => r.Authorization).NotEmpty().Must(a => a.StartsWith("Bearer "));
    }
}

// START_CONTRACT: ValidateUser
// ...
// END_CONTRACT: ValidateUser
public User? ValidateUser(Request req)
{
    ArgumentNullException.ThrowIfNull(req);
    var result = new RequestValidator().Validate(req);
    if (!result.IsValid) return null;
    // ...
}
```

## 5. Testing framework

**xUnit** — стандарт. Альтернативы: NUnit (legacy), MSTest (редко).

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>dotnet test tests/Auth.Tests --filter FullyQualifiedName~AuthValidatorTests</Command>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
    <Marker>VALIDATE_FAIL</Marker>
  </Markers>
</Verification>
```

Для property-based: `FsCheck` (.NET) или `CsCheck`. Для integration: `Microsoft.AspNetCore.Mvc.Testing` + testcontainers-dotnet.

## 6. Structured logs

**Serilog** + **Serilog.Formatting.Json** (или `Serilog.Formatting.Compact` — JSON Lines) — стандартная связка.

Конфигурация `Program.cs`:
```csharp
using Serilog;
using Serilog.Formatting.Compact;

Log.Logger = new LoggerConfiguration()
    .Enrich.FromLogContext()
    .WriteTo.Console(new CompactJsonFormatter())
    .CreateLogger();

var builder = WebApplication.CreateBuilder(args);
builder.Host.UseSerilog();
```

В коде:
```csharp
using Serilog.Context;

using (LogContext.PushProperty("correlation_id", req.CorrelationId))
{
    _log.LogInformation("jwt_decoded {Anchor} {Module} {Requirement} {Belief}",
        "ValidateUser:BLOCK_DECODE_JWT",
        "M-AUTH-VALIDATE",
        "UC-001",
        "payload trusted, skew=0");
}
```

Альтернатива: `Microsoft.Extensions.Logging` (`ILogger<T>`) с JSON-формате через `AddJsonConsole()` — проще, но меньше возможностей, чем Serilog.

## 7. CGC: C# — полная поддержка

CodeGraphContext парсит C# через tree-sitter-c-sharp. Поддерживаются классы, методы, properties, namespaces, using-директивы, вызовы, интерфейсы, records. Особенности:

- **Partial classes**: парсятся как отдельные единицы; для `impact`-анализа имя `ClassName` собирается из всех `partial`-файлов, но якоря `MODULE_CONTRACT` нужно ставить **в каждом файле** partial-класса, который размечается отдельно как модуль, либо выбрать один "owner"-файл.
- **Source generators** (`[Generator]`-атрибуты, runtime-код): сгенерированный код **не индексируется**. Методы, созданные `[GeneratedRegex(...)]`, `[JsonSerializable]`, MediatR source-gen — не видны.
- **Records** (C# 9+): позитивные properties (`public record User(string Name)`) индексируются как класс + автосгенерированные методы. Сами методы не видны (как Lombok в Java).
- **File-scoped namespaces** (C# 10+): работают нормально; MODULE_CONTRACT идёт **до** `namespace X;`-строки.

## 8. Project-layout

Стандартная .NET-структура (SDK-style):
```
repo/
├── Example.sln
├── src/
│   ├── Example.Auth/
│   │   ├── Example.Auth.csproj
│   │   └── AuthValidator.cs
│   └── Example.Api/
│       └── ...
├── tests/
│   └── Example.Auth.Tests/
│       ├── Example.Auth.Tests.csproj
│       └── AuthValidatorTests.cs
└── docs/
    ├── requirements.xml
    └── ...
```

В `development-plan.xml`:

```xml
<Paths>
  <Path>src/Example.Auth/AuthValidator.cs</Path>
</Paths>
```

Для больших solutions: `Paths` перечисляет все файлы модуля; один `M-*` может охватывать несколько файлов в одном проекте (`*.csproj`), но **не** через границы проектов — каждый проект оформляется отдельным `M-*`.

## 9. Anti-patterns

- **Якоря в `///` XML-doc:**
  ```csharp
  /// <summary>
  /// START_CONTRACT: ValidateUser   ← парсер якорей не видит XML-doc
  /// </summary>
  public User? ValidateUser(...) {}
  ```
  Использовать `//` над или между XML-doc и атрибутами.

- **Использование deprecated Code Contracts:**
  ```csharp
  Contract.Requires(req != null);   ← .NET 5+ не поддерживает
  ```
  Заменить на `ArgumentNullException.ThrowIfNull(req)` + FluentValidation.

- **Контракт на auto-property / primary constructor record:**
  ```csharp
  public record User(string Name);   ← нет явной сигнатуры метода для якоря
  ```
  Для records контракт — на методах, которые явно написаны в теле. Auto-generated `Equals`/`GetHashCode` — не размечать.

- **Атрибут внутри блока контракта:**
  ```csharp
  // START_CONTRACT: ValidateUser
  [HttpGet]                        ← неправильно
  // END_CONTRACT: ValidateUser
  public User? ValidateUser(...) {}
  ```
  Атрибуты — после `END_CONTRACT`.

- **Source-generator-ссылки в MODULE_MAP:** сгенерированные методы (Mediatr handlers, regex-источники) не видны в CGC; в MODULE_MAP помечать их как `(generated)` или не ссылаться.

- **`LogContext.PushProperty` без `using`-scope:** свойство утечёт. Всегда через `using (LogContext.PushProperty(...))`.

## 10. Запуск doubled-graph lint на C#-проекте

```bash
doubled-graph lint --path .
```

CLI `grace` парсит C# через tree-sitter-c-sharp. Плагины для MSBuild/dotnet CLI не требуются.

---

## Чек-лист применения

- [ ] MODULE_CONTRACT / MODULE_MAP — `//`-комментарии в начале файла, до `namespace`.
- [ ] CONTRACT: Method — `//`-комментарии перед сигнатурой; атрибуты между `END_CONTRACT` и сигнатурой.
- [ ] Code Contracts **не используются** (deprecated); вместо них — FluentValidation + `ArgumentNullException.ThrowIfNull` + Nullable reference types.
- [ ] `dotnet test` (xUnit) команда в `verification-plan.xml`.
- [ ] Serilog с JSON-formatter; `LogContext.PushProperty` для `correlation_id` всегда в `using`-scope.
- [ ] Partial-классы: якоря на методах, не на объявлении класса дважды.
- [ ] Source-generators и Records с auto-properties — в MODULE_MAP помечены `(generated)` или пропущены.
- [ ] `///` XML-doc **не используется** для якорей.
