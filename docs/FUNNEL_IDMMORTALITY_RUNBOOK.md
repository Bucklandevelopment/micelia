# Runbook — Funnel `register → login → micelia` en `idmmortality.com`

> **Estado (actualizado 2026-07-17):** DP-1..DP-4 **DECIDIDAS** por el usuario y
> la mitad técnica **EJECUTADA** (stack compose + Caddy TLS listo y validado en
> local, ver §4). Quedan los pasos humanos de panel: router TP-Link + registro A
> en IONOS + API key DDNS (§2-§3, marcados ⏳HUMANO).
>
> La rutina automática `daily-micelia-full-planning` **NO ejecuta** pasos de
> este runbook (guardarraíles: acciones externas irreversibles, secretos,
> DNS/TLS, `git push`). Solo lo mantiene.
>
> Creado en el **Ciclo 34** (2026-07-13) como la mitad **INFRA** del workstream
> funnel-nativo.

---

## 0. Modelo mental (leer primero)

El funnel es la **iteración inicial de marketing** para captar usuarios:
`register → login → acceso a Micelia`, todo bajo subdominios de
`idmmortality.com`. La forma **NATIVA** (elegida, ver
`ITERATION_LOG.md` Ciclo 16 y la memoria `micelia-funnel-native-workstream`)
sirve `register`/`login` como **rutas de la propia app Micelia** (Next.js
`frontend/`), no como landings estáticas HTML pegadas a un proxy.

Consecuencia para infra: lo que se expone públicamente es **la app Next.js**
(el backend FastAPI queda detrás de su proxy same-origin `/api/v1/*`).

**Descartado — NO reabrir:**
- Landings estáticas HTML + integración Stripe/micro-donaciones + proxy.
- `scripts/deploy-landings.sh` + `.env.deploy` (SFTP a IONOS): **sirve las
  landings antiguas** (`index/blog/lab/playground.html`), **no** el funnel
  nativo.

---

## 1. DECISIONES (cerradas el 2026-07-17)

- [x] **DP-1 · Estrategia de hosting = hosting propio local** (ni ngrok ni VPS):
  MacBook M1 Pro como servidor, **port-forward 80/443 en el router TP-Link +
  Caddy** (contenedor en `deploy/docker-compose.yml`) terminando TLS.
  La ruta VPS queda analizada (sin contratar) en
  `deploy/docs/VPS_ANALYSIS_IONOS_VS_HOSTINGER.md`; migrar solo con tracción.
- [x] **DP-2 · Subdominios = `micelia.idmmortality.com` como host único** del
  funnel. `register.`/`login.` siguen sirviendo las landings antiguas; sus
  redirects vanity quedan como bloques comentados en `deploy/caddy/Caddyfile`
  (activar solo si algún día se les cambia el DNS).
- [x] **DP-3 · Secretos = `deploy/.env`** (chmod 600, fuera de git; generados el
  2026-07-17: SECRET_KEY/SYSTEM_API_KEY/JWT_SECRET_KEY aleatorios, password de
  Postgres rotada) **+ `~/.config/utopia/ddns.env`** (API key IONOS, solo humano).
- [x] **DP-4 · Postgres de producción = la del compose local** (`idm-postgres`,
  volumen podman `postgres_data`) con **backup diario 04:00** a
  `~/Backups/utopia/` (launchd `com.utopia.pg-backup`, rotación 14 días).

---

## 2. DNS (⏳HUMANO — panel IONOS)

| Subdominio | Sirve | Estado |
|---|---|---|
| `micelia.idmmortality.com` | App Micelia (register/login/dashboard nativos) | ⏳ cambiar A → IP de casa |
| `register.idmmortality.com` | Landings antiguas (IONOS webspace) | No tocar |
| `login.idmmortality.com` | Landings antiguas (IONOS webspace) | No tocar |

Checklist DNS:
- [ ] ⏳HUMANO — **Modificar** el registro `A` de `micelia.idmmortality.com`
      (hoy `217.160.0.244`, el webspace) → IP pública de casa, **TTL 300**.
- [ ] ⏳HUMANO — Crear API key en <https://developer.hosting.ionos.com/keys> y
      pegarla en `~/.config/utopia/ddns.env` (plantilla ya creada).
- [ ] Correr una vez `deploy/scripts/ddns-ionos.sh bootstrap` — a partir de ahí
      el agente launchd `com.utopia.ddns` (cada 300 s) mantiene el A al día
      (la IP de Digi es dinámica: cambió el mismo 2026-07-17).
- [ ] Verificar propagación (`dig +short micelia.idmmortality.com`).

---

## 3. TLS — resuelto con Caddy (automático)

- [x] Caddy (`deploy/caddy/Caddyfile`) emite y renueva Let's Encrypt solo, y
      fuerza `http → https` (308). Certs persistidos en el volumen `caddy_data`.
- [ ] La **primera emisión ACME** solo puede completarse cuando §2 (DNS) y el
      port-forward 80/443 del TP-Link estén hechos. `podman logs idm-caddy` con
      "certificate obtained" = prueba de reachability externa real.

---

## 4. App — EJECUTADO (compose, no procesos nativos)

La forma final difiere del plan original (`run-local.sh` + `npm start`): todo
corre contenerizado desde `deploy/`:

```
cd deploy && podman compose --profile frontends up -d \
    postgres redis idm-core micelia-frontend caddy
```

- [x] Gateway `idm-core` :8888 **solo loopback**; frontend `idm-dashboard`
      :9000 solo loopback; únicos puertos públicos: **80/443 (Caddy)**.
- [x] Rewrite same-origin: el navegador solo habla con el frontend; Next proxya
      `/api/v1/*` → `idm-core:8888`. OJO aprendizaje 2026-07-17: los rewrites de
      `next.config.js` se hornean **en build** (`.next/routes-manifest.json`) —
      la URL del gateway se fija vía ARG/ENV en
      `deploy/dockerfiles/micelia-frontend.Dockerfile`, no por env runtime.
- [x] Imágenes reconstruidas con el código actual (la de junio no tenía
      `POST /auth/register`).
- [x] Autoarranque: launchd `com.utopia.micelia-stack` (RunAtLoad) →
      `deploy/scripts/stack-up.sh` (arranca podman machine + compose + espera
      health). ⏳HUMANO pendiente: `sudo pmset -a sleep 0 disksleep 0 womp 1`.
- [x] `/register` en `PUBLIC_PATHS` de `frontend/src/middleware.ts` (Ciclo 34).

---

## 5. Preflight antes de abrir a usuarios

- [x] Backend `/api/v1/health` responde OK **a través de la cadena completa**
      Caddy→Next→FastAPI (validado 2026-07-17 vía `https://localhost`).
- [x] Postgres de producción accesible; registro persiste (e2e local OK).
- [x] `JWT_SECRET_KEY` de producción ≠ default (generado, en `deploy/.env`).
- [ ] Flujo manual end-to-end **en el dominio real** (tras §2+port-forward):
      `register` (email nuevo) → dashboard → logout → `login` → dashboard.
- [ ] `register` con email duplicado → 409 mostrado correctamente en UI.
- [ ] Rollback probado: revertir el A → `217.160.0.244` (TTL 300 ⇒ ~5 min),
      cerrar forwarding 80/443 en el TP-Link, `podman compose stop caddy`.

---

## 6. Qué hace la rutina automática vs. qué NO

| | Rutina (`daily-micelia-full-planning`) | Humano (este runbook) |
|---|---|---|
| Rutas nativas `/register`,`/login`, dashboard | ✅ endurece + valida en local | — |
| Cobertura/tests de `auth.py`/`user_store.py` | ✅ (ya al 100%) | — |
| Mantener este runbook | ✅ | — |
| DNS / TLS / hosting / secretos / Postgres prod | ⛔ nunca | ✅ |
| `git push` / deploy externo | ⛔ nunca | ✅ |

Operación diaria post-despliegue: logs en `~/Library/Logs/utopia-*.log`,
acceso Caddy en el volumen `caddy_data` (`/data/access.log`), backups en
`~/Backups/utopia/`.

---

## 7. Despliegue REAL — LAN-only detrás de CGNAT (2026-07-21)

> **Contexto:** al desplegar de verdad se confirmó que la conexión está **detrás de
> CGNAT** (Digi no da IP pública enrutable). El plan §1-§3 (A-record → IP de casa +
> port-forward + Let's Encrypt público) **NO es viable**: ni el port-forward llega, ni
> ACME HTTP-01/TLS-ALPN puede validar. Se pivota a **acceso LAN-only** por ahora.

### Qué cambió (ejecutado)
- **Hosting:** solo LAN. Acceso desde `https://MacBook-Pro-de-null.local` (mDNS/Bonjour)
  o `https://192.168.1.100` (IP LAN, reservar en DHCP del TP-Link para que no cambie).
- **TLS = CA interna de Caddy** (Opción B), NO Let's Encrypt (imposible tras CGNAT).
  El bloque `micelia.idmmortality.com` del `deploy/caddy/Caddyfile` pasó a incluir la IP
  LAN y `tls internal` (para el móvil/otros dispositivos). El bucle de ACME público queda
  parado (evita el rate-limit de Let's Encrypt).
  - **Root CA extraída** a `~/Desktop/micelia-caddy-root-CA.crt` — instalar+confiar en
    cada dispositivo (iOS: Ajustes→VPN/Gestión→perfil, luego Ajustes→General→Info→
    Certificados de confianza; Android: Ajustes→Seguridad→Cifrado→Instalar certificado CA).
    Con la root instalada, el navegador del móvil NO se queja.
- **DDNS desactivado:** `launchctl bootout/disable gui/$UID/com.utopia.ddns` (ya no tiene
  sentido sin A-record público). Reversible: `launchctl enable` + `bootstrap` del plist.
  `com.utopia.micelia-stack` y `com.utopia.pg-backup` **siguen activos**.
- **DNS IONOS:** NO se tocó el A-record (sigue en el webspace `217.160.0.244`). El §2 queda
  **aparcado** hasta tener IP pública (fibra sin CGNAT / IPv6 / VPS / túnel).

### Verificado en vivo (2026-07-21)
Flujo completo por la cadena real Caddy→Next→FastAPI sobre HTTPS:
`register` (201) → `login` (200) → `/auth/me` (200, identidad = UUID del usuario) →
password mala (401) → email duplicado (409). ✓

### Para volver a exposición pública el día que haya IP enrutable
Reactivar A-record IONOS + DDNS + port-forward 80/443 (§2-§3), quitar la IP LAN y el
`tls internal` del bloque `micelia.` para que Caddy vuelva a ACME público. El resto del
stack no cambia.
