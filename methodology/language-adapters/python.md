# Language adapter: Python

## 1. Синтаксис комментариев

`#` для однострочных якорей, `"""..."""` для docstring-адресованных контрактов.

## 2. Позиция контракта функции — критический нюанс

**Python docstring идёт ПОСЛЕ `def`, а не до.** Это выбивает стандартный шаблон якорей методологии doubled-graph, рассчитанный на C/Java-стиль «блок-комментарий перед определением».

**Правило для Python:**
- `START_MODULE_CONTRACT` / `END_MODULE_CONTRACT` — **как комментарии `#`**, в начале файла, до импортов.
- `START_CONTRACT: fn` / `END_CONTRACT: fn` — **внутри docstring функции**, как отдельные строки-маркеры.

```python
# START_MODULE_CONTRACT
# Module: M-AUTH-VALIDATE
# Purpose: validate JWT and resolve User.
# Scope: single file src/auth/validate.py
# Dependencies: M-AUTH-TOKENS
# Criticality: critical
# LINKS: UC-001, V-M-AUTH-VALIDATE-01
# END_MODULE_CONTRACT

# START_MODULE_MAP
# exports:
#   - validate_user (function)
#   - validate_token (function)
# END_MODULE_MAP

from typing import Optional


def validate_user(req: "Request") -> Optional["User"]:
    """Validate JWT and resolve user.

    START_CONTRACT: validate_user
    PURPOSE: validate JWT, resolve user
    INPUTS: req: Request (with Authorization: Bearer header)
    OUTPUTS: User | None (None if invalid, never raises)
    SIDE_EFFECTS: none
    LINKS: UC-001, M-AUTH-VALIDATE, V-M-AUTH-VALIDATE-01
    END_CONTRACT: validate_user
    """
    # START_BLOCK_DECODE_JWT
    token = _extract_token(req)
    payload = _decode_jwt(token)
    # END_BLOCK_DECODE_JWT

    # START_BLOCK_CHECK_CLOCK_SKEW
    if abs(_now_ms() - payload.iat * 1000) > 60_000:
        return None
    # END_BLOCK_CHECK_CLOCK_SKEW

    return payload.user


# START_CHANGE_SUMMARY
# 2026-04-12: tightened JWT clock-skew tolerance to 60s (DG-Authored: ai)
# 2026-04-18: --
# END_CHANGE_SUMMARY
```

**Почему так:** `doubled-graph lint` парсит комментарии `#` как якори на уровне файла, а докстринговые маркеры — на уровне функции. Путать нельзя.

## 3. Блоки — `END_BLOCK` перед dedent

В Python нет фигурных скобок; блок-якоря парятся по отступу. **Правило:** `END_BLOCK_NAME` ставится **на том же уровне отступа, что и `START_BLOCK_NAME`**, непосредственно перед тем, как уровень отступа уменьшится.

```python
def handle(req):
    # START_BLOCK_PARSE
    if req.json:
        data = req.json
        validate_shape(data)
    # END_BLOCK_PARSE        ← на уровне def, перед следующим блоком

    # START_BLOCK_PERSIST
    db.save(data)
    # END_BLOCK_PERSIST
```

Если блок содержит ранний `return`, якорь `END_BLOCK` должен стоять **до** `return`:

```python
    # START_BLOCK_VALIDATE
    if not ok:
        # END_BLOCK_VALIDATE  ← правильно
        return None
```

## 4. Runtime-контракты — какие использовать

Три популярных подхода, разный scope (R3):

| Библиотека | Scope | Когда применять |
|---|---|---|
| **pydantic v2** | data validation на границах (API входы, JSON) | почти всегда; de-facto стандарт |
| **beartype** | runtime type-check через декоратор, zero-overhead-ish | если хочется «как mypy, но в runtime» |
| **icontract** | design-by-contract pre/post/invariant | для критичных модулей (auth, payments) |
| **deal** | похож на icontract, но с LSP-aware | альтернатива icontract, активное развитие |

**Рекомендация doubled-graph:**

- **Critical-модули** (`criticality="critical"` в `development-plan.xml`): pydantic **+** icontract (или deal).
- **Standard-модули:** pydantic на границах API.
- **Helper-модули:** обычно достаточно mypy + unit-тестов.

```python
import icontract


@icontract.require(lambda req: req.headers.get("Authorization") is not None)
@icontract.ensure(lambda result: result is None or isinstance(result, User))
def validate_user(req: Request) -> Optional[User]:
    """
    START_CONTRACT: validate_user
    PURPOSE: validate JWT, resolve user
    ...
    END_CONTRACT: validate_user
    """
```

Формальный контракт (`@require`, `@ensure`) **не заменяет** текстовый контракт в docstring — они дополняют друг друга. Текстовый — для ИИ и человека при чтении; формальный — для runtime-защиты.

## 5. Testing framework

**pytest** — по умолчанию.

```xml
<Verification id="V-M-AUTH-VALIDATE-01" module="M-AUTH-VALIDATE" kind="unit">
  <Command>pytest tests/test_auth_validate.py -v</Command>
  <Markers>
    <Marker>VALIDATE_SUCCESS</Marker>
    <Marker>VALIDATE_FAIL</Marker>
  </Markers>
</Verification>
```

Для property-based — `hypothesis`. Для integration — pytest-asyncio + testcontainers.

## 6. Structured logs

**`structlog`** — первый выбор. `loguru` — альтернатива с меньшей конфигурацией.

```python
import structlog

logger = structlog.get_logger()

def validate_user(req):
    """... contract ..."""
    logger.info(
        "jwt_decoded",
        anchor="validate_user:BLOCK_DECODE_JWT",
        module="M-AUTH-VALIDATE",
        requirement="UC-001",
        correlation_id=req.correlation_id,
        belief="payload trusted, skew=0",
    )
```

Логеры конфигурируются в `src/<pkg>/logging.py`; формат обязан быть JSON (для парсеров observability).

## 7. CGC: Python — first-class

CodeGraphContext имеет **полную поддержку Python** (это его родной язык, самый проверенный парсер). Ограничений нет. Если встретилась ошибка — см. upstream issues, не writing-around.

## 8. Project-layout

```
repo/
├── pyproject.toml
├── src/
│   └── <package_name>/
│       ├── __init__.py
│       └── auth/validate.py
├── tests/
│   └── test_auth_validate.py
└── docs/
    ├── requirements.xml
    ├── development-plan.xml
    └── ...
```

`Paths` в `development-plan.xml`:

```xml
<Paths>
  <Path>src/<package_name>/auth/validate.py</Path>
</Paths>
```

## 9. Anti-patterns

- ❌ **Контракт перед `def`:**
  ```python
  # START_CONTRACT: validate_user  ← здесь парсер его не заметит
  def validate_user(req): ...
  ```
  Идёт в docstring, не комментарием над.

- ❌ **Смешивание `#` и docstring в одном контракте.** `START_CONTRACT` и `END_CONTRACT` должны быть в одном типе (оба docstring).

- ❌ **`# noqa` на якорях.** Линтеры не ругаются на якори; если ругается — обнови `.ruff.toml` / `flake8` exclude.

- ❌ **Декораторы до `START_CONTRACT`.** Порядок: декораторы → `def` → docstring с `START_CONTRACT`.

- ❌ **Использование `from __future__ import annotations` без явного `cast()`** в контракте — pydantic может не распознать тип. Если используешь future-annotations — в контракте пиши строковые типы тоже как строки: `INPUTS: req: "Request"`.

## 10. Запуск doubled-graph lint на Python-проекте

```bash
doubled-graph lint --path .
```

CLI `grace` написан на Bun, но **парсит Python-комментарии корректно** — специально для этой цели. Не требует установки Python-специфичных плагинов.

---

## Чек-лист применения

- [ ] MODULE_CONTRACT и MODULE_MAP — как `#`-комментарии в начале файла.
- [ ] CONTRACT: fn — внутри docstring функции.
- [ ] BLOCK_NAME — `#`-комментарии, `END` перед dedent.
- [ ] pydantic на API-границах, icontract/deal на критических контрактах.
- [ ] pytest-команда в `verification-plan.xml`.
- [ ] structlog/loguru с обязательными полями `anchor`, `module`, `requirement`, `correlation_id`.
- [ ] Декораторы идут **до** `def`, не между `def` и docstring.
