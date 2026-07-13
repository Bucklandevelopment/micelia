# Runbook — Funnel `register → login → micelia` en `idmmortality.com`

> **Estado:** documento de referencia para ejecución **HUMANA**. La rutina
> automática `daily-micelia-full-planning` **NO ejecuta** ninguno de los pasos de
> este runbook (todos caen en los guardarraíles: acciones externas irreversibles,
> secretos, DNS/TLS, `git push`). La rutina solo **mantiene este documento**.
>
> Creado en el **Ciclo 34** (2026-07-13) como la mitad **INFRA** del workstream
> funnel-nativo. La mitad **LOCAL** (rutas nativas `/register`, `/login`,
> dashboard; su backend `auth.py`/`user_store.py` al 100%; validación e2e local)
> sí es in-scope de la rutina y se aborda por separado.

---

## 0. Modelo mental (leer primero)

El funnel es la **iteración inicial de marketing** para captar usuarios:
`register → login → acceso a Micelia`, todo bajo subdominios de
`idmmortality.com`. La forma **NATIVA** (elegida, ver
`ITERATION_LOG.md` Ciclo 16 y la memoria `micelia-funnel-native-workstream`)
sirve `register`/`login` como **rutas de la propia app Micelia** (Next.js
`frontend/`), no como landings estáticas HTML pegadas a un proxy.

Consecuencia para infra: lo que hay que exponer públicamente es **la app
Next.js + el backend FastAPI**, no ficheros estáticos.

**Descartado — NO reabrir:**
- Landings estáticas HTML + integración Stripe/micro-donaciones + proxy.
- `scripts/deploy-landings.sh` + `.env.deploy` (SFTP a IONOS): **sirve las
  landings antiguas** (`index/blog/lab/playground.html`), **no** el funnel
  nativo. Queda documentado aquí solo para que nadie lo confunda con el deploy
  del funnel.

---

## 1. DECISIONES PENDIENTES (para Jessicache — bloquean el arranque)

Estas decisiones son irreversibles o cuestan dinero/secretos → **humano decide**:

- [ ] **DP-1 · Estrategia de hosting.** Elegir UNA:
  - **(a) Túnel ngrok con dominio reservado** — más rápido para validar con
    usuarios reales. Config ya soportada: `settings.ngrok_domain`
    (`app/core/config.py:136`, ej. `idmmortality.com`) + router
    `app/api/v1/tunnel.py`. La MacBook M1 hace de servidor mientras esté
    encendida. **Local-first, reversible.** Recomendado para el primer piloto.
  - **(b) Hosting gestionado** (VPS/PaaS con Node + Python) — permanente, pero
    implica proveedor, coste y operación 24/7. Diferir hasta tener tracción.
- [ ] **DP-2 · Alcance de subdominios.** Confirmar el mapa DNS deseado
  (ver §2). Los `source-id` de dominio **no se tocan**; esto es solo hosting.
- [ ] **DP-3 · Gestión de secretos en producción.** `JWT_SECRET_KEY`,
  `AUTH_PASSWORD_HASH`, `SYSTEM_API_KEY` **NO** pueden ir al repo ni a este
  runbook. Definir dónde viven (gestor de secretos / `.env` fuera de git en el
  host). La rutina nunca los crea ni los lee.
- [ ] **DP-4 · Base de datos de usuarios.** El funnel escribe en `user_store`
  (PostgreSQL). Decidir la Postgres de producción (misma M1 vía
  `make docker-infra`, o gestionada). En local degrada, pero el registro real
  necesita persistencia.

---

## 2. DNS (ejecución humana en el panel de idmmortality.com)

Objetivo mínimo del funnel: que un visitante llegue a **registro → login →
dashboard**. Con hosting **(a) ngrok**, el mapeo natural es un único host de app;
con **(b)** puedes separar subdominios. Mapa sugerido (ajustar según DP-1/DP-2):

| Subdominio | Sirve | Notas |
|---|---|---|
| `micelia.idmmortality.com` | App Micelia (register/login/dashboard nativos) | Host principal del funnel |
| `register.idmmortality.com` | Redirect 302 → `micelia…/register` | Opcional (vanity/marketing) |
| `login.idmmortality.com` | Redirect 302 → `micelia…/login` | Opcional (vanity/marketing) |

Checklist DNS:
- [ ] Crear registro(s) `A`/`AAAA` (hosting propio) **o** `CNAME` (ngrok/PaaS)
      según DP-1.
- [ ] TTL bajo (300s) durante el piloto para poder revertir rápido.
- [ ] Verificar propagación (`dig +short micelia.idmmortality.com`).

---

## 3. TLS

- [ ] Certificado para el/los host(s) de §2.
  - ngrok: TLS lo termina ngrok (nada que hacer salvo usar el dominio reservado).
  - Hosting propio: Let's Encrypt (certbot) o el TLS gestionado del proveedor.
- [ ] Renovación automática configurada (si aplica).
- [ ] Redirección `http → https` forzada.

---

## 4. App (build + arranque en el host elegido)

El funnel nativo son **dos procesos** (ver `DEPLOY_LOCAL_2026-06-09.md` para el
equivalente 100% local):

- [ ] **Backend FastAPI** (:8888) — `bash scripts/run-local.sh start` (local) o
      el equivalente supervisado en el host. Requiere Postgres accesible (DP-4)
      para que `register`/`login` persistan.
- [ ] **Frontend Next.js** (:3001) — `make frontend-build` + `npm start`
      (o `make frontend-dev` en piloto). `next.config.js` ya proxya
      `/api/v1/*` → `MICELIA_URL || http://localhost:8888`; en el host, apuntar
      `MICELIA_URL` al backend.
- [ ] Exponer **solo el frontend** públicamente; el backend queda detrás del
      proxy `/api` del propio Next (no publicar :8888 directo).

> Nota de código ya resuelta en local (Ciclo 34): `/register` está en
> `PUBLIC_PATHS` de `frontend/src/middleware.ts` (si no, el middleware rebota a
> `/login` a los no autenticados y el registro es inalcanzable).

---

## 5. Preflight antes de abrir a usuarios

- [ ] `make -C micelia verify` verde en el commit desplegado.
- [ ] Backend `/api/v1/health` responde `healthy` en el host.
- [ ] Postgres de producción migrada y accesible (registro real persiste).
- [ ] `JWT_SECRET_KEY` de producción **≠** el default `change-me-jwt-secret`
      (`app/core/config.py:169`).
- [ ] Flujo manual end-to-end en el dominio real:
      `register` (email nuevo) → redirige a dashboard → logout → `login` →
      dashboard.
- [ ] `register` con email duplicado → 409 mostrado correctamente en UI.
- [ ] Rollback probado: bajar el proceso / revertir el CNAME (TTL 300s).

---

## 6. Qué hace la rutina automática vs. qué NO

| | Rutina (`daily-micelia-full-planning`) | Humano (este runbook) |
|---|---|---|
| Rutas nativas `/register`,`/login`, dashboard | ✅ endurece + valida en local | — |
| Cobertura/tests de `auth.py`/`user_store.py` | ✅ (ya al 100%) | — |
| Mantener este runbook | ✅ | — |
| DNS / TLS / hosting / secretos / Postgres prod | ⛔ nunca | ✅ |
| `git push` / deploy externo | ⛔ nunca | ✅ |

Cuando DP-1..DP-4 estén decididas, este runbook se ejecuta **una vez** a mano; a
partir de ahí la rutina sigue endureciendo la mitad local sin tocar infra.
