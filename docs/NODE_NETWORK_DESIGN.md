# Red de nodos externos — diseño mínimo (propuesta, no implementada)

> **Estado: PROPUESTA.** Nada de lo descrito aquí existe todavía en el código.
> Documentado para decisión del dueño — ver **DP-22** en `DP_LEDGER.md`. Hasta que
> se implemente, cualquier mención pública de esto (blog incluido) debe contarse
> como *vía preparada*, nunca como hecho.

## 1. El problema que resuelve

Cuando el repo de Micelia sea público, cualquiera podrá clonarlo y levantar su
propio nodo (ver el tutorial del blog). Eso abre tres preguntas que hoy no
tienen respuesta:

1. ¿Cuánta gente ha descargado y ejecutado el software?
2. ¿Sigue activo un nodo concreto, sin que tenga que estar permanentemente
   conectado al nodo semilla (el mío)?
3. ¿Cómo llega información útil para depurar y mejorar el código desde nodos
   que yo no controlo?

## 2. Principios no negociables

- **Opt-in explícito.** Apagado por defecto. El software funciona al 100% con
  la telemetría desactivada.
- **Anónimo por diseño.** Un `node_id` (UUID v4) generado localmente en cada
  nodo, nunca vinculado a email, nombre o cuenta. No es un sistema de usuarios.
- **Sin conexión permanente.** Un pulso periódico (push, HTTP), no un socket
  abierto ni una VPN obligatoria. Un nodo puede estar "activo" sin estar
  "conectado a mí" en todo momento — que es exactamente lo que pidió el dueño.
- **Los datos identifican una instalación, no una persona.**
- **Transparencia radical.** El código que envía el latido es público y su
  payload es exactamente el documentado aquí — nada implícito, nada añadido
  "por si acaso" (mismo principio que ya aplica el `service_registry.py`
  interno: declarar, no suponer).

## 3. Arquitectura propuesta

Es el mismo patrón que `app/services/service_registry.py` ya resuelve **hacia
dentro** del ecosistema (gateway → satélites, sondeo por *pull*, latido cada
30s), pero invertido: los nodos externos no son alcanzables por IP fija ni
tienen DNS, así que el nodo semilla no puede sondearlos. La dirección tiene
que ser **push**: el nodo externo llama al nodo semilla, no al revés.

```
Nodo externo (portátil de un lector)          Nodo semilla (micelia.idmmortality.com)
┌─────────────────────────────┐               ┌───────────────────────────────┐
│ app/services/network_beacon │  POST cada     │ POST /api/v1/network/heartbeat│
│  (nuevo, opt-in)            │  30-60 min ──▶ │  → upsert en `network_nodes`  │
│  node_id local persistido   │               │ GET  /api/v1/network/summary  │
│  fuera del repo             │  ◀── 204/200   │  → conteo agregado, público   │
└─────────────────────────────┘               └───────────────────────────────┘
```

### 3.1 Identidad del nodo

- Generado una vez, guardado en `~/.config/utopia/node_id` (fuera del repo y
  fuera de `.env`, igual que `ddns.env` en el proyecto `deploy`).
- Si el fichero no existe al arrancar con el opt-in activado, se crea con
  `uuid4()`. Si se borra, el nodo simplemente aparece como "nuevo" — no hay
  forma de correlacionar el nodo viejo con el nuevo, y eso es intencional.

### 3.2 Payload del latido (exhaustivo — esto es TODO lo que se envía)

```json
{
  "node_id": "3f2e1a90-...-uuid4",
  "version": "1.4.0",
  "uptime_s": 3600,
  "profile": "core"
}
```

- `version`: la del propio código (`pyproject.toml`), para saber qué versiones
  siguen en uso real cuando algo se rompe.
- `profile`: qué perfil de `docker-compose` corre (`core`, `full`, `lite`...) —
  ayuda a depurar sin preguntar.
- **Lo que NUNCA se envía en el cuerpo**: IP, hostname, ubicación, nombre,
  email, datos de la app (salud, código, lo que sea que procese ese nodo).
- La IP de origen queda inevitablemente en el log HTTP del servidor (como en
  cualquier petición web) pero no se copia a la tabla `network_nodes`; se
  purga con la rotación normal de logs (`logs/`, ya gitignorado).

### 3.3 Estado en el nodo semilla

Tabla nueva `network_nodes` en la Postgres del nodo semilla:

| columna | tipo | nota |
|---|---|---|
| `node_id` | uuid, PK | generado por el nodo externo |
| `first_seen` | timestamp | primer latido recibido |
| `last_heartbeat` | timestamp | último latido |
| `version` | text | del último latido |
| `profile` | text | del último latido |
| `heartbeat_count` | int | contador simple |

Sin tabla de usuarios, sin claves foráneas hacia nada personal. Un nodo sin
latido en 24h se considera `dormant` (calculado al leer, no un campo aparte);
no hay estado "muerto" — solo "activo" / "dormant", igual de honesto que el
`connection_refused` sin drama del registry interno.

### 3.4 Endpoints propuestos

- `POST /api/v1/network/heartbeat` — público, rate-limited por IP (reutiliza
  el rate limiter que ya existe en el gateway), sin autenticación (no hay
  cuenta que autenticar). Idempotente: upsert por `node_id`.
- `GET /api/v1/network/summary` — público, **solo agregados**: `{"active": N,
  "dormant": M}`. Nada por-nodo expuesto públicamente. El detalle por-nodo
  (si algún día hace falta para depurar una versión concreta) se consulta
  directo en la Postgres del nodo semilla, no por API.

## 4. Activación y consentimiento

- Flag `MICELIA_NETWORK_OPT_IN=false` por defecto en `.env.example`.
- El tutorial del blog explica, antes de proponer activarlo, exactamente el
  payload de la sección 3.2 y cómo desactivarlo (`=false` + reinicio del
  gateway).
- El propio README del repo público lleva una sección "Telemetría" que es un
  espejo literal de este documento — no una versión resumida que prometa
  menos de lo que el código hace, ni al revés.

## 5. Fuera de alcance de este MVP (roadmap, no construir todavía)

- **Informes de error/depuración más ricos**: GlitchTip autoalojado (fork
  libre de Sentry) en el nodo semilla, con envío manual ("enviar diagnóstico")
  nunca automático. Requiere su propio diseño de consentimiento; no mezclar
  con el heartbeat de esta propuesta.
- **Conectividad directa entre nodos** (más allá de hablar con el nodo
  semilla): Headscale (control-plane autoalojado de Tailscale) si algún día
  interesa que nodos activos se vean entre sí sin pasar por mí. El heartbeat
  HTTP de este documento no lo necesita — resuelve el caso de uso pedido
  (saber quién está activo) sin montar una malla VPN.

## 6. Lo que esta propuesta explícitamente NO hace

- No identifica personas ni cuentas.
- No mantiene conexión persistente ni exige que el nodo esté siempre online.
- No es obligatoria: el nodo funciona igual con `MICELIA_NETWORK_OPT_IN=false`.
- No es analítica de producto ni tracking de uso interno de la app — es
  exclusivamente el pulso "¿cuántos nodos siguen vivos y en qué versión?".
