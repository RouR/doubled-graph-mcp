# Language adapter: Go

Адаптер покрывает Go 1.21+ (когда stdlib получил `log/slog`).

## 1. Синтаксис комментариев

- `//` — однострочный якорь (рекомендуемый).
- `/* ... */` — многострочный, допустим, но в Go практически не используется — разметку не делать.
- **Godoc-комментарии** — это просто `//`-комментарий **непосредственно перед** экспортируемым идентификатором. Специального синтаксиса нет, но у него есть семантика (см. ниже).

## 2. Позиция контракта функции

Контракт функции — `//`-комментарии непосредственно перед `func`. **Ключевой нюанс Go:** godoc-комментарий — это комментарий, начинающийся с имени функции и расположенный **непосредственно** перед ней без пустых строк. Если поставить контракт **между** godoc-комментарием и `func`, godoc сломается (Go tooling перестанет его видеть).

**Правило для Go:**

- Либо godoc **совпадает** с контрактом: первая строка контракта = `// ValidateUser validates JWT and resolves user.`, затем `// PURPOSE: ...`, и т. д.
- Либо контракт идёт **до** godoc-комментария, а между ними **пустая строка**. Тогда godoc остаётся godoc'ом, а контракт — просто блоком комментариев.

Второй вариант — предпочтительный для doubled-graph, потому что позволяет держать godoc-формат чистым.

```go
// START_MODULE_CONTRACT
// Module: M-AUTH-VALIDATE
// Purpose: validate JWT and resolve User
// Scope: internal/auth/validate.go
// Dependencies: M-AUTH-TOKENS
// Criticality: critical
// LINKS: UC-001, V-M-AUTH-VALIDATE-01
// END_MODULE_CONTRACT

// START_MODULE_MAP
// exports:
//   - ValidateUser (function)
// END_MODULE_MAP

package auth

import (
	"log/slog"
	"time"
)

// START_CONTRACT: ValidateUser
// PURPOSE: validate JWT, resolve user
// INPUTS: req *Request (Authorization: Bearer header required)
// OUTPUTS: *User, error (nil, nil = no auth; user, nil = valid; nil, err = protocol error)
// SIDE_EFFECTS: none
// LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
// END_CONTRACT: ValidateUser

// ValidateUser validates a JWT and resolves the user.
// Returns (nil, nil) when token is absent or invalid.
func ValidateUser(req *Request) (*User, error) {
	// START_BLOCK_DECODE_JWT
	token := extractToken(req)
	payload, err := decodeJwt(token)
	if err != nil {
		return nil, nil
	}
	// END_BLOCK_DECODE_JWT

	// START_BLOCK_CHECK_CLOCK_SKEW
	skew := time.Now().UnixMilli() - payload.IAT*1000
	if skew < -60_000 || skew > 60_000 {
		return nil, nil
	}
	// END_BLOCK_CHECK_CLOCK_SKEW

	return &payload.User, nil
}
```

Обрати внимание на **пустую строку между `END_CONTRACT` и godoc-строкой** — она сохраняет godoc работоспособным.

## 3. Специфика блоков

- `END_BLOCK_NAME` ставится перед закрывающей `}` блока или перед `return`.
- **`defer`**: если в блоке есть `defer`, его исполнение произойдёт после `END_BLOCK`. В имени блока, содержащего `defer`, явно указывать это: `BLOCK_OPEN_TX_WITH_DEFER`.
- **Горутины** (`go func() { ... }()`): тело горутины — отдельная функция. Якорь блока допустим внутри, но имя должно содержать `GOROUTINE`: `BLOCK_GOROUTINE_FLUSH_CACHE`.
- **`select`-блок**: один `case` = один BLOCK максимум. Не разрывать.
- **named return values**: не меняют разметку, но повышают риск, что `END_BLOCK` окажется перед неявным `return`. Имя блока должно соответствовать семантике до `return`, не после.

## 4. Runtime-контракты

**Go не имеет зрелых design-by-contract библиотек**. Это осознанное решение комьюнити.

**Альтернативы для doubled-graph:**

| Подход | Когда применять |
|---|---|
| **`errors` + `fmt.Errorf("%w", ...)`** | все ошибки типизированы, sentinel-errors для `errors.Is` |
| **`staticcheck` + `go vet`** | в CI обязательно; ловит 60–70% того, что в других языках делают контракты |
| **Таблицы тест-кейсов** (table-driven tests) + `testify/assert` | основной способ фиксации pre/post-условий |
| **`validator` v10** (`go-playground/validator`) | декларативные теги на структурах: `validate:"required,email"` |

**Рекомендация doubled-graph:**

- **Critical-модули:** `validator` на входящих структурах + явные `if cond { return nil, ErrXxx }` на границах + table tests.
- **Standard-модули:** `validator` на DTO + линтеры.
- **Helper-модули:** линтеры + unit-тесты.

Псевдо-контракты через assertions (`testify/require` в runtime-коде) — **анти-паттерн**: в Go принято возвращать ошибку, а не паниковать.

```go
import "github.com/go-playground/validator/v10"

var validate = validator.New()

type Request struct {
	Authorization string `validate:"required,startswith=Bearer "`
}

// START_CONTRACT: ValidateUser
// ...
// END_CONTRACT: ValidateUser
func ValidateUser(req *Request) (*User, error) {
	if err := validate.Struct(req); err != nil {
		return nil, nil
	}
	// ...
}
```

## 5. Testing framework

**`go test`** — стандарт. **`testify`** (`assert` / `require` / `mock`) — де-факто расширение. Для property-based — `gopter` или `rapid` (менее популярны, чем в Rust).

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>go test ./internal/auth -run TestValidateUser -v</Command>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
    <Marker>VALIDATE_FAIL</Marker>
  </Markers>
</Verification>
```

Для integration: build tags (`//go:build integration`) + отдельный `go test -tags=integration`.

## 6. Structured logs

**`log/slog`** (stdlib с Go 1.21) — основной выбор. JSON-handler встроен.

Конфигурация:
```go
import (
	"log/slog"
	"os"
)

logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
slog.SetDefault(logger)
```

В коде:
```go
slog.Info("jwt_decoded",
	"anchor", "ValidateUser:BLOCK_DECODE_JWT",
	"module", "M-AUTH-VALIDATE",
	"requirement", "UC-001",
	"correlation_id", req.CorrelationID,
	"belief", "payload trusted, skew=0",
)
```

Для более старых Go (1.20 и ниже) или при потребности в sampling/hooks: **`zap`** (Uber) или **`zerolog`** — оба выдают JSON, оба быстрее stdlib. Переходить на `slog`, когда позволит минимальная версия Go.

## 7. CGC: Go — полная поддержка

CodeGraphContext парсит Go через tree-sitter-go. Поддерживаются функции, методы (с receiver'ом), типы (struct/interface), пакеты, импорты, вызовы. Особенности:

- **Методы с receiver'ом** (`func (a *AuthService) Validate(...)`): CGC сохраняет имя метода, но receiver type отображается отдельно. Имя в `START_CONTRACT` — просто имя метода: `START_CONTRACT: Validate`, без `AuthService.`.
- **Embedded structs и interfaces**: поля/методы, полученные через embedding, **не развёрнуты** в графе — видны только прямые объявления.
- **Generics** (Go 1.18+): type parameters сохраняются как текст в сигнатуре, но не разворачиваются.
- **Сгенерированный код** (`//go:generate`, protobuf, mocks): индексируется как обычный Go-код, но изменения в исходнике генератора не видны до пересборки.

## 8. Project-layout

Стандартная структура:
```
repo/
├── go.mod
├── go.sum
├── cmd/
│   └── server/main.go
├── internal/
│   └── auth/
│       ├── validate.go
│       └── validate_test.go         ← тесты рядом с кодом
├── pkg/                              ← публичные API (опционально)
└── docs/
    ├── requirements.xml
    └── ...
```

В `development-plan.xml`:

```xml
<Paths>
  <Path>internal/auth/validate.go</Path>
</Paths>
```

Go-конвенция: тесты всегда рядом с кодом, `_test.go`-суффикс. Integration-тесты — в том же пакете или в отдельном `_test`-пакете с build tag.

## 9. Anti-patterns

- **Контракт между godoc-комментарием и `func`:**
  ```go
  // ValidateUser validates JWT.
  // START_CONTRACT: ValidateUser    ← ломает godoc
  // END_CONTRACT: ValidateUser
  func ValidateUser(...) {}
  ```
  Вставлять пустую строку между контрактом и godoc-строкой, либо совмещать.

- **`// Deprecated:`-маркер внутри блока контракта:**
  ```go
  // START_CONTRACT: OldValidate
  // Deprecated: use ValidateUser instead.   ← godoc-конвенция сломана
  // END_CONTRACT: OldValidate
  ```
  `// Deprecated:` должен быть в godoc-блоке (между `END_CONTRACT` и `func`), не внутри контракта.

- **Использование `panic()` как runtime-контракта:** в Go ошибки возвращаются, не паникуют. Panic допустим только для unrecoverable-состояний (nil map initialization и т. п.).

- **Receiver name в `START_CONTRACT`:**
  ```go
  // START_CONTRACT: (a *AuthService) Validate   ← парсер не распознаёт
  ```
  Только имя метода: `START_CONTRACT: Validate`.

- **Якорь блока внутри горутины без пометки:**
  ```go
  go func() {
      // START_BLOCK_FLUSH   ← имя не отражает, что это горутина
      ...
  }()
  ```
  Именовать как `BLOCK_GOROUTINE_FLUSH`.

## 10. Запуск doubled-graph lint на Go-проекте

```bash
doubled-graph lint --path .
```

CLI `grace` парсит Go через tree-sitter-go. Дополнительных Go-плагинов не требуется. Вручную рекомендуется дополнить CI-пайплайном: `go vet ./...` + `staticcheck ./...` + `doubled-graph lint` в одном gate.

---

## Чек-лист применения

- [ ] MODULE_CONTRACT / MODULE_MAP — `//`-комментарии до `package`.
- [ ] CONTRACT: Func — `//`-комментарии, пустая строка перед godoc-блоком.
- [ ] BLOCK_NAME — `//`, `END_BLOCK` перед `}` или `return`.
- [ ] Имена блоков с `defer` / горутинами содержат `_DEFER` / `_GOROUTINE`.
- [ ] Валидация через `go-playground/validator` на DTO + явные `if cond { return ErrXxx }`.
- [ ] `go test` (+ `testify`) команда в `verification-plan.xml`.
- [ ] `log/slog` (Go 1.21+) или `zap`/`zerolog`; все обязательные поля как key-value.
- [ ] `staticcheck` и `go vet` в CI — заменяют часть того, что в других языках делает DbC.
- [ ] `// Deprecated:` — в godoc-блоке, не внутри контракта.
