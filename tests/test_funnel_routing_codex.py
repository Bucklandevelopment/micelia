"""
Tripwire del cableado del FUNNEL `register → login → micelia` (C93).

El funnel es el objetivo de marketing del proyecto (captar usuarios bajo subdominios de
idmmortality.com; ver docs/FUNNEL_IDMMORTALITY_RUNBOOK.md). Su forma NATIVA sirve
`/register` y `/login` como rutas de la propia app Next.js (`frontend/`), que hablan con el
backend FastAPI por un proxy same-origin `/api/v1/*`. El backend (`app/api/v1/auth.py`) está
al 100% de cobertura; PERO el CABLEADO frontend↔backend del funnel no lo verificaba nada:

  página → authApi.{register,login} → POST /api/v1/auth/{register,login}
         → (rewrite de next.config) → gateway → auth.py

Cada eslabón vive en un fichero distinto y en dos lenguajes; ni `tsc`/lint (que no entienden
la semántica) ni los tests de backend (que pegan a la ruta directamente, ciegos a lo que el
frontend llama) cazan una deriva. Si alguien:
  - quita `/register` de `PUBLIC_PATHS` → el middleware redirige a `/login` a un usuario NO
    autenticado que intenta registrarse → **no se puede captar usuarios** (la puerta del funnel
    queda cerrada), y ni un test rojo ni el `tsc` avisan;
  - cambia el path de `authApi.register` o el prefijo del router de auth → el POST del funnel
    da 404 en producción;
  - rompe el rewrite `/api/v1/*` → el frontend no alcanza el backend.

Este módulo pinea ese contrato de punta a punta leyendo los ficheros reales (no hay runner de
frontend — solo lint+tsc —, así que este pin en pytest, que `make verify` sí ejecuta, es el
único sitio donde el drift se caza; mismo precedente que test_ecosystem_ports_codex.py).

Scope: el runbook §6 asigna a esta rutina "endurecer + validar las rutas nativas del funnel".
Esto es exactamente eso. NO toca infra (DNS/TLS/hosting = humano), ni el runbook (WIP), ni
secretos. Solo lectura de código + pins.
"""

import re
from pathlib import Path

_MICELIA = Path(__file__).resolve().parents[1]
_FE = _MICELIA / "frontend"
_MIDDLEWARE = _FE / "src" / "middleware.ts"
_NEXT_CONFIG = _FE / "next.config.js"
_API_TS = _FE / "src" / "lib" / "api.ts"
_APP_DIR = _FE / "src" / "app"
_AUTH_PY = _MICELIA / "app" / "api" / "v1" / "auth.py"

# Las dos rutas de la puerta del funnel. Si esto cambia, cambia el funnel entero.
_FUNNEL_PUBLIC = {"/login", "/register"}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# =============================================================================
# 1) Middleware: la puerta del funnel (register/login públicos, resto protegido)
# =============================================================================


def _public_paths() -> set[str]:
    """El array `PUBLIC_PATHS = [...]` de middleware.ts."""
    text = _read(_MIDDLEWARE)
    m = re.search(r"PUBLIC_PATHS\s*=\s*\[([^\]]*)\]", text)
    assert m, "no se encontró PUBLIC_PATHS en middleware.ts (¿se renombró?)"
    return set(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)))


def test_funnel_front_door_is_public():
    """`/register` y `/login` deben estar en PUBLIC_PATHS: un usuario NO autenticado tiene
    que poder llegar a registrarse y a loguearse. Si falta `/register`, no hay captación."""
    paths = _public_paths()
    assert _FUNNEL_PUBLIC <= paths, (
        f"PUBLIC_PATHS del middleware ya no abre la puerta del funnel: falta "
        f"{_FUNNEL_PUBLIC - paths} (hallados: {sorted(paths)}). Sin '/register' público, "
        f"el middleware redirige a los nuevos usuarios a /login → cero captación."
    )


def test_funnel_public_paths_have_real_pages():
    """Cada ruta pública del funnel resuelve a una página Next real (`app/<ruta>/page.tsx`).
    Un PUBLIC_PATHS que whiteliste una ruta inexistente sería un 404 servido sin auth."""
    for path in _FUNNEL_PUBLIC:
        page = _APP_DIR / path.lstrip("/") / "page.tsx"
        assert page.is_file(), (
            f"la ruta pública '{path}' no tiene página ({page.relative_to(_MICELIA)}). "
            f"El funnel enlaza a una ruta que no existe."
        )


def test_unauthenticated_redirect_targets_login():
    """Sin cookie de auth, el middleware redirige a `/login` (la entrada del funnel).
    Si el destino cambia, los usuarios protegidos no aterrizan en el login del funnel."""
    text = _read(_MIDDLEWARE)
    assert re.search(r"redirect\(new URL\('/login'", text), (
        "el middleware ya no redirige a '/login' al usuario sin cookie; el funnel espera "
        "que el no-autenticado caiga en la página de login nativa."
    )


# =============================================================================
# 2) Proxy same-origin: el frontend alcanza el backend por /api/v1/*
# =============================================================================


def test_same_origin_api_rewrite_points_at_gateway():
    """next.config.js debe reescribir `/api/v1/:path*` hacia el gateway. Sin esto, los POST
    de register/login del funnel no llegan al backend (el navegador solo habla con Next)."""
    text = _read(_NEXT_CONFIG)
    m = re.search(
        r"source:\s*'/api/v1/:path\*'.*?destination:\s*`([^`]+)`", text, re.DOTALL
    )
    assert m, (
        "no se encontró el rewrite same-origin '/api/v1/:path*' en next.config.js. Es el "
        "puente frontend→backend del funnel (aprendizaje C-2026-07-17: se hornea en build)."
    )
    dest = m.group(1)
    assert "/api/v1/:path*" in dest, f"el rewrite no preserva el path: {dest!r}"
    assert ("MICELIA_URL" in dest or "IDM_CORE" in dest or "8888" in dest), (
        f"el destino del rewrite ya no apunta al gateway (MICELIA_URL/IDM_CORE/:8888): {dest!r}"
    )


# =============================================================================
# 3) Cableado frontend↔backend: authApi ↔ rutas de auth.py (mismo path + shape)
# =============================================================================


def _authapi_call(method: str) -> tuple[str, set[str]]:
    """(path, claves del body JSON) del `fetch` de `authApi.<method>` en api.ts.

    Devuelve el path con `API_BASE` ya resuelto a '/api/v1' para poder cruzarlo con el
    backend."""
    text = _read(_API_TS)
    base_m = re.search(r"API_BASE\s*=\s*'([^']+)'", text)
    api_base = base_m.group(1) if base_m else "/api/v1"
    # bloque del método dentro de `export const authApi = { ... }`
    block = re.search(rf"{method}:\s*async[^{{]*\{{(.*?)\n  \}}", text, re.DOTALL)
    assert block, f"no se encontró authApi.{method} en api.ts"
    body = block.group(1)
    fetch_m = re.search(r"fetch\(`\$\{API_BASE\}([^`]+)`", body)
    assert fetch_m, f"authApi.{method} no hace fetch a `${{API_BASE}}...`"
    path = api_base + fetch_m.group(1)
    keys = set(re.findall(r"JSON\.stringify\(\{([^}]*)\}", body)[0].split(",")) \
        if re.search(r"JSON\.stringify\(\{", body) else set()
    keys = {k.strip() for k in keys if k.strip()}
    return path, keys


def _backend_auth_routes() -> set[str]:
    """Rutas completas que sirve el router de auth: prefix + cada @router.post('/x')."""
    text = _read(_AUTH_PY)
    prefix_m = re.search(r'APIRouter\(prefix="([^"]+)"', text)
    prefix = prefix_m.group(1) if prefix_m else ""
    posts = re.findall(r'@router\.post\("([^"]+)"', text)
    # el gateway monta el router bajo /api/v1 (app.include_router(prefix="/api/v1"))
    return {f"/api/v1{prefix}{p}" for p in posts}


def test_funnel_authapi_paths_match_backend_routes():
    """El path que el frontend llama para register/login == una ruta que el backend sirve.
    Si divergen (renombre en cualquier lado), el funnel da 404 en producción y nada más lo
    caza: los tests de backend pegan a la ruta directa, ciegos a lo que el frontend usa."""
    backend = _backend_auth_routes()
    for method in ("register", "login"):
        path, _ = _authapi_call(method)
        assert path in backend, (
            f"authApi.{method} llama a '{path}' pero el backend de auth sirve {sorted(backend)}. "
            f"El POST del funnel daría 404. Re-alinea api.ts o auth.py."
        )


def test_funnel_payload_shapes_match_backend_models():
    """El body que el frontend envía coincide con el modelo Pydantic del backend:
    register → {email,password}; login → {username,password}. Un drift de campo daría 422."""
    _, reg_keys = _authapi_call("register")
    _, login_keys = _authapi_call("login")
    assert reg_keys == {"email", "password"}, (
        f"authApi.register envía {reg_keys}, pero RegisterRequest espera email+password."
    )
    assert login_keys == {"username", "password"}, (
        f"authApi.login envía {login_keys}, pero LoginRequest espera username+password."
    )

    auth_text = _read(_AUTH_PY)
    # anti-vacío/deriva del lado backend: los modelos siguen declarando esos campos.
    assert re.search(r"class RegisterRequest\b", auth_text) and "email" in auth_text
    assert re.search(r"class LoginRequest\b", auth_text) and "username" in auth_text
