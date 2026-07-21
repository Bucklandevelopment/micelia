# SSO — Micelia como Identity Provider (C119)

> Un login en Micelia vale para los dominios. Piloto: **biohack (salud)**. Estado: **código
> completo y cadena backend verificada en vivo**; falta el rollout (rebuild + arranque) para la
> UX de navegador end-to-end.

## Diseño (decidido con el usuario)
- **Micelia = Identity Provider (IdP).** Emite JWT HS256. Los dominios (relying parties) validan
  ese JWT con el **mismo secreto** (`JWT_SECRET_KEY` de Micelia == `SECRET_KEY` del dominio).
- **Entrega:** *token hand-off* desde el hub. Al abrir un dominio SSO desde `/servicios`, el hub
  adjunta el access token en el **fragmento** de la URL (`#sso_token=…`; no viaja al servidor ni
  se loguea). El frontend del dominio lo consume, deja la sesión iniciada y limpia la URL.
- **Identidad:** el access token de Micelia lleva `email` + `iss:"micelia"` (además de `sub`=UUID).
  El dominio resuelve al usuario por **email**; si no existe y `iss=="micelia"`, lo **auto-provisiona**
  (resuelve el viejo DP-6). Sin password local usable → el usuario entra solo por SSO.
- **Seguridad (aceptada para LAN local):** HS256 compartido ⇒ un dominio comprometido podría
  forjar tokens de Micelia (frontera de confianza). Hardening futuro: **RS256** (Micelia firma con
  privada, dominios verifican con pública) y hand-off por **código de un solo uso**/postMessage
  en vez de fragmento.

## Qué se cambió (por fase)
| Fase | Repo | Ficheros | Qué |
|---|---|---|---|
| 1 | micelia | `app/core/security.py`, `app/api/v1/auth.py` | access token del funnel lleva `email`+`iss` |
| 2 | biohack | `backend/app/core/auth.py`, `backend/app/api/v1/auth.py` | valida el JWT de Micelia + auto-provisión; `/me` deduplicado al validador del core |
| 3 | micelia + biohack | `frontend/.../services.ts`, `servicios/page.tsx`; `frontend/src/services/sso.ts`, `main.tsx` | hand-off del token por fragmento y su consumo |

## Verificado en vivo (backend)
biohack con `SECRET_KEY` = el de Micelia + postgres/redis efímeros: token de Micelia (email+iss)
→ `/api/v1/auth/me` **200 + usuario auto-provisionado**; 2ª llamada 200 (idempotente); token sin
`iss` + email desconocido → **401** (no crea cuentas ajenas).

## Rollout pendiente (pasos del dueño, a su ritmo)
1. **Secreto compartido:** poner `SECRET_KEY` de biohack = `JWT_SECRET_KEY` de Micelia (en el
   `.env`/arranque de biohack). SIN esto, biohack rechaza los tokens de Micelia.
2. **Rebuild de idm-core (backend, email-claim) Y micelia-frontend (hand-off) en el deploy**
   con `deploy/scripts/sso-rollout.sh` (usa `--force-recreate`: podman-compose NO recrea el
   contenedor tras un rebuild, así el código nuevo no llegaba a producción). Verificado en vivo:
   el token del funnel ya lleva `email`+`iss:micelia`.
   ~~Rebuild del frontend de Micelia~~ (la imagen actual no tiene el email-claim ni
   el hand-off): `cd deploy && podman compose build micelia-frontend && podman compose up -d`.
3. **Arrancar biohack** (front `:5173` + back `:8080`, python 3.11, con postgres) con el secreto
   compartido. Idealmente exponerlo en LAN para el móvil (paso aparte).
4. **Probar UX:** login en Micelia → `/servicios` → "Salud" → biohack abre ya logueado.

## ideacursi (educación) — FUERA de SSO (decisión del dueño, 2026-07-21)
ideacursi **NO** entra en el SSO: mantiene su sistema de login **OAuth (GitHub/GitLab)** actual.
Quien quiera acceder a educación se autentica en ideacursi como hasta ahora. Razón: ideacursi es
OAuth-only (identidad = usuario de git, no email), así que puentearlo al SSO por email era trabajo
desproporcionado para el valor — el dueño prefiere dejarlo con su flujo propio.

Alcance real del SSO, por tanto: **dominios con login propio de email/password** (hoy: biohack).
Si en el futuro otro dominio añade login por email, se replica el patrón de biohack (Fase 2).
