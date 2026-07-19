"""
Tripwire del RENDER de errores del funnel (`register`/`login`), C95.

El §5 del runbook pide, entre el preflight, *"register con email duplicado → **409 mostrado
correctamente en UI**"*. C94 pineó que el backend devuelve 409/401 y que el flujo funciona;
pero que la PÁGINA se lo MUESTRE al usuario es otra capa, y ni `tsc`/lint ni los tests de
backend la tocan. La cadena completa es:

  backend 409/401  →  authApi mapea a `ApiError.message`  →  page `catch → setError(msg)`
                   →  JSX `{error && <div>{error}</div>}`

Si cualquier eslabón se rompe (se quita el `{error && …}`, el `catch` deja de llamar
`setError`, `ApiError` deja de extender `Error`, o el mapeo del 409 desaparece), el usuario
que se equivoca **no ve por qué** — un funnel que falla en silencio espanta al usuario que
intentábamos captar. No hay runner de frontend (solo lint+tsc), así que este pin estático en
pytest —que `make verify` ejecuta— es el único sitio donde el drift se caza (mismo precedente
que test_funnel_routing_codex.py / test_ecosystem_ports_codex.py).

Scope (runbook §6): endurecer las rutas nativas del funnel. Solo lectura de código frontend
committed; sin tocar infra, el runbook (WIP) ni secretos.
"""

import re
from pathlib import Path

_FE = Path(__file__).resolve().parents[1] / "frontend"
_REGISTER = _FE / "src" / "app" / "register" / "page.tsx"
_LOGIN = _FE / "src" / "app" / "login" / "page.tsx"
_API_TS = _FE / "src" / "lib" / "api.ts"

_PAGES = {"register": _REGISTER, "login": _LOGIN}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# =============================================================================
# Lado PÁGINA: estado de error + catch que lo setea + render en JSX
# =============================================================================


def _page(name: str) -> str:
    p = _PAGES[name]
    assert p.is_file(), f"falta la página del funnel: {p}"
    return _read(p)


def test_pages_have_an_error_state():
    """Ambas páginas declaran `const [error, setError] = useState(...)` — el estado que
    guarda el mensaje a mostrar. Sin él no hay qué renderizar."""
    for name in _PAGES:
        text = _page(name)
        assert re.search(r"\[\s*error\s*,\s*setError\s*\]\s*=\s*useState", text), (
            f"la página /{name} ya no tiene estado `error`/`setError`; no puede mostrar "
            f"el 409/401 al usuario."
        )


def test_pages_catch_the_api_error_and_set_it():
    """El submit handler envuelve la llamada a `authApi` en try/catch y, en el catch, hace
    `setError(... err ... message ...)` — surfacea el MENSAJE del backend (vía ApiError), no
    un texto fijo. Mutación: quitar el setError del catch → el error nunca se muestra."""
    for name in _PAGES:
        text = _page(name)
        m = re.search(r"catch\s*\(\s*err[^)]*\)\s*\{(.*?)\}", text, re.DOTALL)
        assert m, f"la página /{name} ya no captura el error de authApi.{name} en un catch"
        catch_body = m.group(1)
        assert "setError(" in catch_body, (
            f"el catch de /{name} ya no llama setError → el fallo del funnel quedaría "
            f"invisible para el usuario."
        )
        assert "message" in catch_body, (
            f"el catch de /{name} ya no usa `err.message` → dejaría de mostrar el motivo "
            f"real (p.ej. 'Email already registered') y caería a un texto genérico."
        )


def test_pages_render_the_error_to_the_user():
    """El JSX renderiza condicionalmente el error: `{error && ( … {error} … )}`. Es lo que
    de verdad lo PONE en pantalla; sin este bloque, setError no se ve."""
    for name in _PAGES:
        text = _page(name)
        assert re.search(r"\{\s*error\s*&&", text), (
            f"la página /{name} ya no renderiza `{{error && …}}` → el mensaje de error no "
            f"aparece aunque setError lo fije."
        )
        # anti-vacío: dentro del render se interpola `{error}` (el valor, no solo el guard).
        assert re.search(r"\{\s*error\s*\}", text), (
            f"la página /{name} tiene el guard `{{error &&}}` pero no interpola `{{error}}` "
            f"→ no muestra el texto."
        )


# =============================================================================
# Lado api.ts: el 409 duplicado se mapea a un mensaje, y ApiError.message lo lleva
# =============================================================================


def _authapi_block(method: str) -> str:
    text = _read(_API_TS)
    m = re.search(rf"{method}:\s*async[^{{]*\{{(.*?)\n  \}}", text, re.DOTALL)
    assert m, f"no se encontró authApi.{method} en api.ts"
    return m.group(1)


def test_register_maps_409_to_duplicate_message():
    """El caso concreto del §5: `authApi.register` mapea el **409** a 'Email already
    registered' (no a un genérico). Es el mensaje que la página mostrará ante un email
    duplicado. Mutación: quitar la rama 409 → el usuario ve 'Registration failed' y no
    entiende que el email ya existe."""
    block = _authapi_block("register")
    assert re.search(r"status\s*===\s*409", block), (
        "authApi.register ya no distingue el 409; el email duplicado del §5 caería en el "
        "mensaje genérico."
    )
    assert "Email already registered" in block, (
        "authApi.register ya no emite 'Email already registered' para el 409 → la UI no "
        "diría al usuario que el email ya está tomado."
    )


def test_login_throws_apierror_on_failure():
    """`authApi.login` lanza ApiError cuando la respuesta no es ok (p.ej. 401) → la página lo
    captura y lo muestra. Sin el throw, un login inválido no daría feedback."""
    block = _authapi_block("login")
    assert re.search(r"if\s*\(\s*!res\.ok\s*\)\s*throw new ApiError", block), (
        "authApi.login ya no lanza ApiError ante !res.ok; un 401 no llegaría al catch de la "
        "página y el usuario no vería 'Invalid credentials'."
    )


def test_apierror_message_reaches_the_page():
    """`ApiError extends Error` y su constructor hace `super(message)` → `err.message` (lo que
    la página renderiza) lleva el texto mapeado. Es el eslabón que conecta el mapeo de api.ts
    con el `err.message` del catch: si ApiError dejara de extender Error, `err instanceof
    Error` sería falso y la página caería al texto genérico."""
    text = _read(_API_TS)
    assert re.search(r"class ApiError extends Error", text), (
        "ApiError ya no extiende Error → `err instanceof Error` en las páginas sería falso y "
        "se perdería el mensaje específico."
    )
    m = re.search(r"class ApiError extends Error\s*\{(.*?)\n\}", text, re.DOTALL)
    assert m and "super(message)" in m.group(1), (
        "el constructor de ApiError ya no pasa `message` a super() → `err.message` quedaría "
        "vacío y la página no mostraría el motivo."
    )
