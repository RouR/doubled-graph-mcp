# Language adapter: Java

Адаптер покрывает Java 17+ (LTS). Для Kotlin применять те же правила до уровня классов/функций, но использовать Kotlin-специфичный адаптер для data class и extension functions (не входит в базовый набор doubled-graph).

## 1. Синтаксис комментариев

- `//` — однострочный якорь (рекомендуемый).
- `/* ... */` — многострочный, допустим, но не используется для якорей по тем же причинам, что в TS: построчный парсинг + закрывающая `*/`.
- Javadoc (`/** ... */`) — для публичного API и типов; **не смешивать** с якорями контрактов.

## 2. Позиция контракта функции

Контракт метода — `//`-комментарии непосредственно перед сигнатурой метода. **Аннотации** (`@Override`, `@Transactional`, `@Valid`) — **после** `END_CONTRACT`, перед сигнатурой.

```java
// START_MODULE_CONTRACT
// Module: M-AUTH-VALIDATE
// Purpose: validate JWT and resolve User
// Scope: src/main/java/com/example/auth/AuthValidator.java
// Dependencies: M-AUTH-TOKENS
// Criticality: critical
// LINKS: UC-001, V-M-AUTH-VALIDATE-01
// END_MODULE_CONTRACT

// START_MODULE_MAP
// exports:
//   - AuthValidator#validateUser (method)
// END_MODULE_MAP

package com.example.auth;

import jakarta.validation.constraints.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class AuthValidator {
  private static final Logger log = LoggerFactory.getLogger(AuthValidator.class);

  // START_CONTRACT: validateUser
  // PURPOSE: validate JWT, resolve user
  // INPUTS: req: HttpRequest (Authorization: Bearer header required)
  // OUTPUTS: Optional<User> (empty if invalid, never throws)
  // SIDE_EFFECTS: none
  // LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
  // END_CONTRACT: validateUser
  @Override
  public Optional<User> validateUser(@NotNull HttpRequest req) {
    // START_BLOCK_DECODE_JWT
    String token = extractToken(req);
    JwtPayload payload = decodeJwt(token);
    // END_BLOCK_DECODE_JWT

    // START_BLOCK_CHECK_CLOCK_SKEW
    if (Math.abs(System.currentTimeMillis() - payload.iat() * 1000L) > 60_000L) {
      return Optional.empty();
    }
    // END_BLOCK_CHECK_CLOCK_SKEW

    return Optional.of(payload.user());
  }
}
```

## 3. Специфика блоков

Java — фигурные скобки, блок-разметка свободная. Ограничения:

- `END_BLOCK_NAME` ставится **внутри блока**, перед закрывающей `}` или перед `return`/`throw`.
- **Lambdas** (`x -> { ... }`): блоки внутри лямбды разрешены, но имя блока должно явно указывать на лямбду — `BLOCK_FILTER_ACTIVE_USERS_LAMBDA`.
- **try-with-resources**: якорь блока покрывает **всю конструкцию целиком**, включая `catch`/`finally`. Не разрывать `try` и `catch` разными блоками.
- **switch expression** (Java 14+): для каждой ветки — отдельный BLOCK, но, как и в TS, без разрыва `case`.

## 4. Runtime-контракты

| Библиотека | Scope | Когда применять |
|---|---|---|
| **Bean Validation** (`jakarta.validation`, Hibernate Validator) | декларативные ограничения на поля и параметры | де-факто стандарт для DTO и controller-аргументов |
| **cofoja** (Contracts for Java) | design-by-contract: `@Requires`, `@Ensures`, `@Invariant` | малоактивный проект; использовать только если команда уже на нём |
| **vavr.Validation** | функциональная валидация (accumulation of errors) | если проект на vavr / functional-стеке |

В Java-мейнстриме **`javax.validation` переименован в `jakarta.validation`** (Jakarta EE 9+). Для Spring Boot 3+ — только `jakarta.*`. Для Spring Boot 2 — `javax.*`.

**Рекомендация doubled-graph:**

- **Critical-модули:** Bean Validation на входящих DTO + ручные `Objects.requireNonNull` / `Preconditions.checkArgument` в теле метода.
- **Standard-модули:** Bean Validation на границах controller/service.
- **Helper-модули:** достаточно unit-тестов и `-Xlint:all`.

```java
import jakarta.validation.constraints.NotNull;
import jakarta.validation.Valid;

// START_CONTRACT: validateUser
// ...
// END_CONTRACT: validateUser
public Optional<User> validateUser(@Valid @NotNull ValidationRequest req) {
  Objects.requireNonNull(req.authorization(), "Authorization header required");
  // ...
}
```

cofoja — если применяется — требует javac-плагина и не сочетается с некоторыми build-конфигурациями (Kotlin, Lombok). Перед внедрением проверить build pipeline.

## 5. Testing framework

**JUnit 5** — стандарт. AssertJ или встроенные assertions — на выбор команды.

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>mvn -pl auth test -Dtest=AuthValidatorTest</Command>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
    <Marker>VALIDATE_FAIL</Marker>
  </Markers>
</Verification>
```

Для Gradle: `./gradlew :auth:test --tests com.example.auth.AuthValidatorTest`. Для property-based: `jqwik`. Для integration: `@SpringBootTest` + testcontainers.

## 6. Structured logs

**SLF4J API + logback + logstash-logback-encoder** — стандартная связка для JSON-логов.

`logback.xml`:
```xml
<appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
  <encoder class="net.logstash.logback.encoder.LogstashEncoder"/>
</appender>
```

В коде — через `MDC` (Mapped Diagnostic Context) для обязательных полей:

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import net.logstash.logback.argument.StructuredArguments;

private static final Logger log = LoggerFactory.getLogger(AuthValidator.class);

// внутри validateUser:
try (var ignored = MDC.putCloseable("correlation_id", req.correlationId())) {
  log.info("jwt_decoded",
      StructuredArguments.kv("anchor", "validateUser:BLOCK_DECODE_JWT"),
      StructuredArguments.kv("module", "M-AUTH-VALIDATE"),
      StructuredArguments.kv("requirement", "UC-001"),
      StructuredArguments.kv("belief", "payload trusted, skew=0"));
}
```

Альтернативы: `log4j2` с JSON-layout, `tinylog`. Главное — output валидный JSON-lines.

## 7. CGC: Java — полная поддержка

CodeGraphContext парсит Java через tree-sitter-java. Поддерживаются классы, интерфейсы, методы, конструкторы, поля, импорты, вызовы. Ограничения:

- **Inner / anonymous classes**: парсятся, но имя в графе строится как `Outer$Inner` — проверяй, что имя в `START_CONTRACT` совпадает с именем метода **внутри** анонимного класса, а не с самим классом.
- **Generics**: type parameters не разворачиваются; все `List<User>` индексируются под именем `List`.
- **Lombok @Data, @Builder**: методы, сгенерированные Lombok'ом, **не видны** CGC (нет исходника). Если разметка требует ссылок на `setX()` / `getX()` — писать их вручную или не полагаться на Lombok для публичного API.

## 8. Project-layout

Maven:
```
repo/
├── pom.xml
├── src/
│   ├── main/java/com/example/auth/AuthValidator.java
│   ├── main/resources/logback.xml
│   └── test/java/com/example/auth/AuthValidatorTest.java
└── docs/
    ├── requirements.xml
    └── ...
```

Gradle — та же структура, но с `build.gradle(.kts)` и опциональным multi-module `settings.gradle`.

В `development-plan.xml`:

```xml
<Paths>
  <Path>src/main/java/com/example/auth/AuthValidator.java</Path>
</Paths>
```

Для multi-module Maven/Gradle: путь — от корня репо, включая имя модуля (`auth/src/main/java/...`).

## 9. Anti-patterns

- **Якоря в Javadoc:**
  ```java
  /**
   * START_CONTRACT: validateUser   ← парсер якорей не видит Javadoc
   */
  public Optional<User> validateUser(...) {}
  ```
  Использовать `//` над Javadoc или без Javadoc.

- **Lombok-сгенерированные методы в MODULE_MAP:**
  ```java
  // exports:
  //   - User#getName   ← сгенерирован @Data, в коде отсутствует
  ```
  Либо не использовать Lombok для публичных экспортов, либо фиксировать Lombok-сгенерированные методы в отдельном разделе `MODULE_MAP` с пометкой `(lombok)`.

- **Аннотация между CONTRACT и сигнатурой:**
  ```java
  // END_CONTRACT: validateUser
  @Transactional          ← ok, это правильный порядок
  @Override
  public Optional<User> validateUser(...) {}
  ```
  Это **правильно**. Неправильно — вставлять аннотацию **внутрь** блока контракта.

- **Контракт на конструкторе без имени:** `START_CONTRACT: <init>` **не допускается** — использовать имя класса: `START_CONTRACT: AuthValidator`.

- **MDC без try-with-resources:** если `MDC.put` не закрыт, контекст утечёт на следующий запрос в thread-pool'е. Всегда через `MDC.putCloseable(...)` в try-with-resources.

## 10. Запуск doubled-graph lint на Java-проекте

```bash
doubled-graph lint --path .
```

CLI `grace` парсит Java-комментарии через tree-sitter-java (та же грамматика, что использует CGC). Никаких Maven/Gradle-плагинов не требуется.

---

## Чек-лист применения

- [ ] MODULE_CONTRACT / MODULE_MAP — `//`-комментарии в начале файла, после `package`, до импортов.
- [ ] CONTRACT: method — `//`-комментарии перед сигнатурой, аннотации между `END_CONTRACT` и сигнатурой.
- [ ] BLOCK_NAME — `//`, `END_BLOCK` перед закрывающей `}` или `return`.
- [ ] Bean Validation (`jakarta.*` для Spring Boot 3+, `javax.*` для Spring Boot 2) на границах controller/service.
- [ ] JUnit 5 команда в `verification-plan.xml`.
- [ ] SLF4J + logstash-logback-encoder, MDC в try-with-resources для `correlation_id`.
- [ ] Якоря для Lombok-сгенерированных методов не используются (или явно помечены).
- [ ] Контракт конструктора — под именем класса, не `<init>`.
