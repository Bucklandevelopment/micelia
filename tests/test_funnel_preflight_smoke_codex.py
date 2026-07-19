"""
C94 — Preflight LOCAL del funnel: la cadena `register → login → acceso`, e2e contra el
Event/User Store REAL (postgres), a través de los endpoints REALES.

Ataca los ítems LOCALES/automatizables del §5 del runbook
(`docs/FUNNEL_IDMMORTALITY_RUNBOOK.md`): *"register persiste (e2e local)"* y el round-trip
de login. Los ítems `[ ]` que exigen el DOMINIO real (flujo en `micelia.idmmortality.com`,
rollback de infra) quedan fuera — son ⏳HUMANO por diseño.

Qué añade sobre lo ya pineado:
  - `test_auth_endpoints_codex.py` cubre cada rama de auth.py pero con un store STUB.
  - `test_auth_funnel_integration_codex.py` corre bcrypt real pero con un user_store FALSO
    en memoria (no hay SQLite; UserModel es Postgres-only).
  - Este módulo cierra el hueco: el LIFESPAN REAL trae el **UserStore REAL sobre postgres**,
    y se conduce el funnel entero por los endpoints reales — register PERSISTE de verdad, el
    login autentica contra ESE usuario persistido (no el fallback admin), y el token concede
    ACCESO autenticado (`/me`). Es el preflight que C83/C87 hicieron a mano para los dominios,
    ahora para el usuario final del funnel.

Exige postgres → `require_postgres` (skip si no hay). `no_domain_probes` mantiene herméticos
los sondeos del registry que el lifespan hace al arrancar. In-process (ASGITransport), sin
bindear puerto, sin tocar infra/DNS/TLS/secretos ni el runbook (WIP).
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

_PASSWORD = "S3curePass!word"  # cumple la validación de RegisterRequest (>= 8 chars)


def _fresh_email() -> str:
    """Email único por llamada (el store es append-only y persiste entre corridas)."""
    return f"funnel-{uuid4().hex}@example.com"


async def test_funnel_register_login_access_against_the_real_store(
    require_postgres, no_domain_probes
):
    """
    El preflight completo del funnel, e2e y persistente:

      1. REGISTER → 201 + tokens (auto-login), y el usuario PERSISTE en el UserStore real.
      2. LOGIN (mismo email/password) → 200 + tokens, por la ruta de USUARIO REAL (no el
         fallback admin) — se prueba decodificando el `sub` del token = user_id persistido.
      3. ACCESO → el access_token del login concede entrada autenticada a Micelia (`/me`
         responde 200 con la identidad del usuario). register → login → **acceso**.
    """
    from app.core.security import jwt_auth
    from app.main import app

    email = _fresh_email()

    async with app.router.lifespan_context(app):
        assert app.state.user_store is not None, (
            "require_postgres pasó pero el lifespan no trajo el UserStore — regresión en el "
            "wiring de app.main:lifespan (el funnel no podría registrar usuarios)"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # --- (1) REGISTER: 201 + tokens, y persistencia REAL ---
            reg = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
            )
            assert reg.status_code == 201, reg.text
            reg_body = reg.json()
            assert reg_body["access_token"] and reg_body["refresh_token"]

            persisted = await app.state.user_store.get_user_by_email(email)
            assert persisted is not None, "register() no PERSISTIÓ el usuario en el store real"
            assert persisted["email"] == email
            user_id = persisted["user_id"]

            # --- (2) LOGIN: 200, por la ruta de usuario real (sub == user_id) ---
            login = await client.post(
                "/api/v1/auth/login", json={"username": email, "password": _PASSWORD}
            )
            assert login.status_code == 200, login.text
            access = login.json()["access_token"]
            sub = jwt_auth.decode_token(access).get("sub")
            assert sub == user_id, (
                "el login no autenticó contra el usuario persistido: sub="
                f"{sub!r} != user_id={user_id!r}. ¿Cayó en el fallback admin en vez de la "
                "ruta del UserStore? El funnel estaría logueando al usuario equivocado."
            )

            # --- (3) ACCESO: el token concede entrada autenticada (register→login→acceso) ---
            me = await client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
            )
            assert me.status_code == 200, me.text
            me_body = me.json()
            assert me_body["auth_method"] == "jwt"
            assert me_body["auth_identity"] == user_id, (
                "el /me tras el login no identifica al usuario registrado; el token del funnel "
                "no concede acceso como ese usuario."
            )


async def test_funnel_duplicate_email_returns_409(require_postgres, no_domain_probes):
    """
    §5 del runbook: registrar un email ya existente → 409 (contra el store real, no un stub).
    El primer register persiste; el segundo choca con el UNIQUE del UserStore real.
    """
    from app.main import app

    email = _fresh_email()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
            )
            assert first.status_code == 201, first.text
            dup = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
            )
            assert dup.status_code == 409, (
                f"un email duplicado no dio 409 sino {dup.status_code}: {dup.text}. El "
                f"UNIQUE del UserStore real no se está honrando en el flujo del funnel."
            )


async def test_funnel_login_wrong_password_is_401(require_postgres, no_domain_probes):
    """Un usuario persistido + password equivocada → 401 (bcrypt real rechaza contra el hash
    persistido). Cierra el flanco de seguridad del login del funnel contra el store real."""
    from app.main import app

    email = _fresh_email()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            reg = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
            )
            assert reg.status_code == 201, reg.text
            bad = await client.post(
                "/api/v1/auth/login",
                json={"username": email, "password": "wrong-" + _PASSWORD},
            )
            assert bad.status_code == 401, (
                f"login con password equivocada dio {bad.status_code} en vez de 401: {bad.text}"
            )


async def test_funnel_refresh_renews_session_preserving_identity(
    require_postgres, no_domain_probes
):
    """
    Cierra el CICLO DE SESIÓN del funnel que C94 dejó sin ejercer: register/login devuelven un
    `refresh_token` que nadie canjeaba de punta a punta contra el store real.

      1. register (auto-login) → access + refresh de un usuario REAL persistido.
      2. REFRESH → se canjea ESE refresh en `/auth/refresh` → par nuevo. El access renovado
         SIGUE identificando al mismo usuario (`sub == user_id`) — la renovación no pierde la
         identidad — y SIGUE concediendo acceso (`/me` → auth_identity == user_id). Es lo que
         permite a un usuario del funnel seguir dentro cuando su access caduca, sin re-login.
      3. ROTACIÓN → el refresh devuelto por el paso 2 TAMBIÉN sirve para otro refresh → el
         ciclo se repite indefinidamente (sesión larga sin volver a introducir credenciales).
    """
    from app.core.security import jwt_auth
    from app.main import app

    email = _fresh_email()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            reg = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
            )
            assert reg.status_code == 201, reg.text
            first_refresh = reg.json()["refresh_token"]

            user = await app.state.user_store.get_user_by_email(email)
            assert user is not None
            user_id = user["user_id"]

            # --- (2) REFRESH: canjear el refresh de register por un par nuevo ---
            r1 = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": first_refresh}
            )
            assert r1.status_code == 200, r1.text
            renewed = r1.json()
            assert jwt_auth.decode_token(renewed["access_token"]).get("sub") == user_id, (
                "el access renovado no identifica al usuario del funnel; la sesión perdió la "
                "identidad al refrescar."
            )

            # el access renovado concede acceso autenticado como ese mismo usuario
            me = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {renewed['access_token']}"},
            )
            assert me.status_code == 200, me.text
            assert me.json()["auth_identity"] == user_id

            # --- (3) ROTACIÓN: el refresh nuevo también sirve → ciclo repetible ---
            r2 = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": renewed["refresh_token"]}
            )
            assert r2.status_code == 200, (
                "el refresh rotado no sirvió para renovar de nuevo; la sesión del funnel no "
                f"se puede sostener sin re-login. Respuesta: {r2.text}"
            )
            assert jwt_auth.decode_token(r2.json()["access_token"]).get("sub") == user_id


async def test_funnel_access_token_is_rejected_as_a_refresh(
    require_postgres, no_domain_probes
):
    """En el contexto del funnel: el ACCESS token del login NO sirve como refresh (el endpoint
    exige `type == 'refresh'`). Evita que un access robado/reusado extienda la sesión."""
    from app.main import app

    email = _fresh_email()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            reg = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": _PASSWORD}
            )
            assert reg.status_code == 201, reg.text
            access = reg.json()["access_token"]

            bad = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": access}
            )
            assert bad.status_code == 401, (
                f"un access token fue aceptado como refresh ({bad.status_code}); el guard de "
                f"type del funnel no se está honrando. {bad.text}"
            )
