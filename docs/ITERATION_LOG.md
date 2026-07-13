# ITERATION_LOG — Daily Micelia Full Planning

> Memoria persistente de la tarea diaria. Cada ejecución añade una entrada NUEVA
> arriba del todo. No editar entradas anteriores.

## Formato de entrada

```
## YYYY-MM-DD
- Hecho: (commits + resumen de 1 línea cada uno)
- Verify: (verde/rojo + cobertura %)
- Bloqueado/pendiente: (qué y por qué)
- DECISIÓN PENDIENTE: (si aplica, para Jessicache)
- Mañana: (siguiente paso concreto recomendado)
```

---

## 2026-07-13 — Ciclo 30 (router `energy.py` 33→100% — CIERRA el mayor router descubierto restante · verify verde 1302 pass · cov 88.86% limpio · gate 86→87)

**Contexto:** Ciclo 29 (misma fecha) cerró `system.py` 35→100% dejando `make verify` verde (1272 pass,
cov 87.57% limpio, gate 86) y recomendó como "Mañana (Ciclo 30)" la opción **(a) recomendada**:
`app/api/v1/energy.py` (133 stmts, **33%**, 89 miss) — **el mayor router descubierto que quedaba**, router
del sistema de energía inteligente (batería/solar/red + decisiones de cómputo, 3 endpoints HTTP + 1 WebSocket
+ 3 helpers). Prioridad #1 (rojo→verde) satisfecha en baseline (confirmado antes de tocar nada: `make verify`
verde exit 0, 1272 pass, cov 87.57%/gate 86; `energy.py` a 33% con miss 57-98,108-128,133-159,166-178,195-250,
266-289,295-310) y hito DoD ≥70% cumplido → el día cae en **prioridad #3 (roadmap: subir cobertura)**. Trabajo
autónomo-seguro: solo un fichero de tests + Makefile + docs, sin infra/red/`.env`/`uv.lock`, sin tocar runtime.

**Hecho (3 commits atómicos):**
- `test(api)` (`energy.py`): nuevo `tests/test_api_energy_codex.py` (**+30 tests**). Convención `_codex`
  (plantilla `test_api_frangels_codex.py`/`test_api_sync_codex.py`). **Helpers puros** probados llamándolos
  directo: `get_battery_status` parcheando `energy.subprocess.run` con stdout `pmset` canned — 5 ramas de
  parseo (`\d+%` presente/ausente→fallback 100; `AC Power`/`charging`→is_charging; `H:MM remaining`→minutos
  vs −1; `power_source` ac/battery/unknown; `except`→dict fallback). Descubierto al escribir: el código trata
  cualquier substring `"charging"` — **incluida `"discharging"`** — como is_charging=True, así que el caso
  batería-descargando usa stdout sin esa subcadena (documentado en el test, no es bug a arreglar en este ciclo).
  `calculate_state` las **5 ramas** SURVIVAL/CRITICAL/CONSERVING/ABUNDANT/NORMAL; `get_recommendations` los 5
  estados (parametrizado). **Endpoints** sobre `FastAPI()` local con `AsyncClient`+`ASGITransport` y **auth real**
  (`api_key_manager.generate_key(permissions={"all"})` + `X-API-Key`): `/status` (NORMAL/CONSERVING/CRITICAL vía
  `get_battery_status` parcheado + `settings.solar_api_url` None/valor→`solar_available` False/True), `/compute-
  recommendation` (las **5 ramas** de `ComputeRecommendation` — **ABUNDANT y SURVIVAL forzadas parcheando
  `energy.calculate_state`**, pues los endpoints fijan `is_online=True`/`solar_watts=0.0` y esos dos estados son
  inalcanzables por la vía HTTP), `/history` (`app.state.event_store` None→`{"events":[],"message":"..."}` vs
  `MagicMock` con `query_events=AsyncMock`→eventos con eco de `hours` + assert de kwargs `category`/`subcategory`/
  `limit`). **WebSocket `/ws`** (patrón nuevo — **no había ningún test de websocket en el repo**): `TestClient`
  síncrono de Starlette; `verify_auth` usa `APIKeyHeader(Security)` que **no resuelve en scope WebSocket**
  (`TypeError: APIKeyHeader.__call__() missing ... 'request'`), así que se usa `app.dependency_overrides[verify_auth]`
  (idiom de `test_auth_endpoints_codex.py`) para alcanzar el cuerpo; `get_battery_status` con
  `side_effect=[dict, RuntimeError]` + `energy_check_interval=0` → una iteración: `accept`→`send_json` (1
  `energy_update`)→`sleep(0)`→2ª llamada lanza→`except`→`finally: close()` limpio; el cliente recibe el único
  mensaje. Auth **401/403** parametrizada en los 3 GET. **`energy.py` 133/133 stmts, 100%, 0 miss.** Ni `pmset`,
  ni macOS, ni subprocess real, ni infra, ni red, ni `.env`.
- `chore(cov)`: total (checkout limpio) 87.57%→**88.86%** (+1.29 pts). Ratchet **efectivo**: `floor(88.86)−1 = 87`
  → gate `--cov-fail-under` **86→87** en `Makefile` (target `cov` + comentario + nota). `docs/COVERAGE_ROADMAP.md`:
  header (medición 87.57→88.86% limpio, gate 86→87, margen +18.86) + entrada Ciclo 30 en el histórico.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (`ruff` app/sdk/tests), typecheck ✓ (`mypy app/`, 0 errores),
test ✓ (**1302 pass** + 2 skip, era 1272: +30 nuevos), cov ✓ (**89.12%** con el fichero suelto ajeno /
**88.86%** en checkout limpio, ambos ≥ gate **87**). Frontend no tocado (no aplica `frontend-lint`). Sin procesos
residuales (ciclo solo-tests, sin runtime).

> **NOTA de medición (honestidad, igual que Ciclos 27-29):** el árbol de trabajo sigue incluyendo el cambio
> **pre-existente sin commitear ajeno a este ciclo** (`tests/test_api_prompts_codex.py`, no tocado por Ciclo 30).
> El **árbol commiteado por este ciclo** (sin ese fichero, medido vía `git stash push` → `pytest --cov=app` →
> `stash pop`) mide **88.86%** (1284 pass); con el fichero suelto daría 89.12% (1302 pass). El ratchet a **87**
> se fija sobre la medición **limpia** (`floor(88.86)−1 = 87`), segura en checkout limpio (margen +1.86). Sigue
> pendiente para Jessicache: decidir qué hacer con ese cambio suelto de `test_api_prompts_codex.py`.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems humano-dependientes**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Cobertura:
con `energy.py` cerrado, **ya no quedan routers descubiertos grandes**; los mayores huecos restantes son del
eje SDK y colas menores: `app/sdk/client.py` (197 stmts, **59%**, 80 miss — cliente HTTP del SDK, requiere
`respx`/`httpx` mock), `app/api/v1/gateway.py` (70 stmts, 60%), `app/api/v1/events.py` (69 stmts, 68%),
`app/api/v1/ai.py` y `app/api/v1/prompts.py` con colas. Dir legacy vacío `micelia/vital-core/docs/` sigue en
árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por
Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 31 — NEXT STEP):** sin routers descubiertos grandes, el eje de mayor valor pasa a ser el **SDK**:
**`app/sdk/client.py`** (197 stmts, 59%, 80 miss — cliente HTTP del SDK; cubrir con `respx`/`httpx` mock, primer
módulo del SDK atacado; gran superficie de una pieza). Alternativa de menor tamaño: cerrar los routers
parcialmente cubiertos `app/api/v1/gateway.py` (70 stmts, 60%) y `app/api/v1/events.py` (69 stmts, 68%) en un
ciclo combinado. **Recomendado: (a) `app/sdk/client.py`** por ser el mayor hueco restante y abrir el eje SDK.
No tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-13 — Ciclo 29 (router `system.py` 35→100% — CIERRA el mayor bloque descubierto del proyecto · verify verde 1272 pass · cov 87.57% limpio · gate 81→86)

**Contexto:** Ciclo 28 (misma fecha) cerró `frangels.py` 36→100% dejando `make verify` verde (1192 pass,
cov 82.57% limpio, gate 81) y recomendó como "Mañana (Ciclo 29)" la opción **(a) recomendada**:
`app/api/v1/system.py` (414 stmts, **35%**, 270 miss) — **el mayor bloque descubierto que quedaba en el
proyecto**, router de integración macOS/OSASCRIPT (28 endpoints). Prioridad #1 (rojo→verde) satisfecha en
baseline (confirmado antes de tocar nada: 1192 pass + 2 skip, cov 83%/82.57% limpio, gate 81) y hito DoD
≥70% cumplido → el día cae en **prioridad #3 (roadmap: subir cobertura)**. Trabajo autónomo-seguro: solo un
fichero de tests + Makefile + docs, sin infra/red/`.env`/`uv.lock`, sin tocar runtime de `app/`.

**Hecho (3 commits atómicos):**
- `test(api)` (`system.py`): nuevo `tests/test_api_system_codex.py` (**+80 tests**). Convención `_codex`
  (plantilla `test_api_frangels_codex.py`). Los 28 endpoints comparten forma: guard
  `check_osascript_enabled()` (503 si `settings.osascript_enabled=False`) → método **síncrono** del singleton
  `osascript_service` (import a nivel de módulo) → `await audit_logger.log_operation(...)`. Se monkeypatchea
  el nombre enlazado en el namespace del router (`system.osascript_service`) a un `MagicMock` síncrono → el
  singleton real (que hace `subprocess.run` de `osascript` en macOS) **nunca se toca**: sin subprocess, sin
  macOS. `audit_logger` se usa **real** y degrada solo: `log_operation` lee
  `getattr(request.app.state,'event_store',None)` → la `FastAPI()` local no tiene `event_store` → no toca
  disco/DB/red. Auth **real** con key `{"all"}` (`api_key_manager.generate_key`, rate_limit 100000). Cubiertas
  las **3 formas** de endpoint y sus ramas: **lectura GET** (happy + `except OSAScriptError`→500; params
  opcionales sanitizados con/sin valor en `/calendar/today`,`/reminders`,`/notes`; `/music/current` track
  truthy→`{playing:True}` vs None→`{playing:False}`; `/contacts/search` `q` min_length→422); **escritura POST**
  (`success`→200 con eco / falsy→500 + 422 de body incompleto); **high-risk con `OSAScriptSecurityContext`**
  (`/volume`,`/dark-mode/toggle`,`/safari/open`,`/finder/reveal`,`/clipboard`: happy/500/**403** forzando
  `settings.osascript_disabled_operations`); **validadores de modelos** (subtitle/location/notes con `""`
  **explícito** para que Pydantic v2 ejecute el `return v` del branch falsy —los defaults no disparan el
  validador—, sound/voice fuera de whitelist→fallback `default`/`Samantha`, clamp `set_volume` >100→100,
  `validate_url` esquema no-http→422); y cross-cutting (**503** con `osascript_enabled=False` parametrizado,
  **400** de `validate_path` fuera de prefijos permitidos (`/etc/passwd`), **401** parametrizado con
  `osascript_require_auth` forzado a True → `verify_api_key` levanta durante la resolución de dependencias,
  **antes** del rate-limit —clave: sin forzarlo, el entorno resuelve auth opcional y el limiter por-IP
  devolvía 429—). **`system.py` 414/414 stmts, 100%, 0 miss.** Ni subprocess, ni infra, ni red, ni `.env`.
- `chore(cov)`: total (checkout limpio) 82.57%→**87.57%** (+5.00 pts, el mayor salto de un ciclo). Ratchet
  **efectivo**: `floor(87.57)−1 = 86` → gate `--cov-fail-under` **81→86** en `Makefile` (target `cov` +
  comentario + nota). `docs/COVERAGE_ROADMAP.md`: header (medición 82.57→87.57% limpio, gate 81→86, margen
  +17.57) + entrada Ciclo 29 en el histórico.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (`ruff` app/sdk/tests), typecheck ✓ (`mypy app/`, 0 errores),
test ✓ (**1272 pass** + 2 skip, era 1192: +80 nuevos), cov ✓ (**87.83%** con el fichero suelto / **87.57%** en
checkout limpio, ambos ≥ gate **86**). Frontend no tocado (no aplica `frontend-lint`). Sin procesos residuales
(ciclo solo-tests, sin runtime).

> **NOTA de medición (honestidad, igual que Ciclos 27-28):** el árbol de trabajo sigue incluyendo el cambio
> **pre-existente sin commitear ajeno a este ciclo** (`tests/test_api_prompts_codex.py`, no tocado por Ciclo 29).
> El **árbol commiteado por este ciclo** (sin ese fichero, medido vía `git stash push` → `pytest --cov=app` →
> `stash pop`) mide **87.57%** (1254 pass); con el fichero suelto daría 87.83% (1272 pass). El ratchet a **86**
> se fija sobre la medición **limpia** (`floor(87.57)−1 = 86`), segura en checkout limpio (margen +1.57). Sigue
> pendiente para Jessicache: decidir qué hacer con ese cambio suelto de `test_api_prompts_codex.py`.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems humano-dependientes**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Cobertura:
con `system.py` cerrado, **ya no quedan bloques descubiertos grandes**; los mayores huecos restantes son
`app/api/v1/energy.py` (133 stmts, **33%**, 89 miss), `app/sdk/client.py` (197 stmts, **59%**, 80 miss — cliente
HTTP), `app/api/v1/gateway.py` (70 stmts, 60%), `app/api/v1/events.py` (69 stmts, 68%). Dir legacy vacío
`micelia/vital-core/docs/` sigue en árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin
`/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 30 — NEXT STEP):** cerrar `app/api/v1/energy.py` (133 stmts, 33%, 89 miss — router de
energía/presupuesto energético; inspeccionar dependencias y montarlo sobre `FastAPI()` local con los servicios
mockeados, mismo patrón). Alternativa del eje SDK: **`app/sdk/client.py`** (197 stmts, 59%, 80 miss — cliente
HTTP con `respx`/`httpx` mock, primer módulo del SDK). **Recomendado: (a) `energy.py`** por ser el mayor router
descubierto que queda y seguir el patrón ya dominado. No tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-13 — Ciclo 28 (router `frangels.py` 36→100% — PRIMER router del eje providers · verify verde 1192 pass · cov 82.57% limpio · gate 80→81)

**Contexto:** Ciclo 27 (misma fecha) cerró los 8 módulos de servicio near-100% → 100% dejando `make verify` verde
(1154 pass, cov 81.09%, gate 80) y recomendó como "Mañana (Ciclo 28)" **atacar superficie grande**, opción (a)
**recomendada**: `app/api/v1/frangels.py` (187 stmts, **36%**, 120 miss — el mayor router sin cubrir), montándolo
sobre `FastAPI()` local con las dependencias mockeadas (mismo patrón de Ciclos 16-25). Prioridad #1 (rojo→verde)
satisfecha en baseline y hito DoD ≥70% cumplido → el día cae en **prioridad #3 (roadmap: subir cobertura)**.
Baseline confirmado verde antes de tocar nada (make verify: 1154 pass, cov 81.09% con fichero suelto; `frangels.py`
187/120 miss a 36%). Trabajo autónomo-seguro: solo un fichero de tests + Makefile + docs, sin infra/red/`.env`/
`uv.lock`, sin tocar runtime de `app/`.

**Hecho (3 commits atómicos):**
- `test(api)` (`frangels.py`): nuevo `tests/test_api_frangels_codex.py` (**+38 tests**). Convención `_codex`
  (plantilla `test_api_budget_codex.py`). El router obtiene sus tres singletons por **import a nivel de módulo**
  (`get_provider_store`/`get_quota_manager`/`get_frangels_orchestrator`), así que se monkeypatchea el nombre ya
  enlazado en el namespace del router (`app.api.v1.frangels.*`) → los singletons reales (que tocan almacenamiento
  encriptado en disco y el orquestador httpx/ngrok) **nunca se construyen**. Store/quota-manager = `MagicMock`
  síncrono (ningún método se `await`ea); orquestador con `chat`/`test_provider` = `AsyncMock`. `ANGEL_REGISTRY`,
  `AngelCategory`, `PrivacyLevel` se usan **reales**; `QuotaStatus`/`InferenceResult` se construyen **reales** para
  que `asdict`/la proyección JSON queden serializables. Cubre los **15 endpoints** y todas sus ramas: `/providers`
  (ternario `quota` presente vs None + `summary` + `by_category`), `GET /providers/{id}` (404 + asdict con/sin
  quota), `POST /providers` (400 desconocido / 400 api_key vacía / 422 body incompleto + assert `set` con `strip`),
  `DELETE` (404 + happy), `PATCH /toggle` (404 / 400 no-configurado (`store.get`→None) / enable / disable), `POST
  /test` (404 / happy / **rama `except`**→`{success:false, latency_ms:0}` sin 500), `/usage`, `/quotas` (summary
  `exhausted`+`warning` con QuotaStatus a 100%/85%/10%), `/quotas/{id}` (404/happy), `POST /chat` (happy con
  proyección `usage`/`message`; `privacy_level` válido→coerción a `PrivacyLevel` / inválido→**rama `except
  ValueError: pass`** / error del orquestador→**502**), `/chat/available-providers` (`side_effect` de `store.get`
  y `can_use` para ejercer los **3 `continue`** —no-INFERENCE, cred None/no-enabled, `can_use` False— + orden por
  tier premium-first), `/status` (`available_by_category` contando enabled+can_use), `POST /sync-env` (delta
  `imported = after-before` vía `list_configured.side_effect`), `GET /export-env` (masking **>8 chars** parcial vs
  **≤8 chars** total), y `test_requires_auth` **parametrizado** sobre 9 endpoints (401/403). **`frangels.py`
  187/187 stmts, 100%, 0 miss.** Ni infra, ni red, ni `.env`.
- `chore(cov)`: total (checkout limpio) 80.83%→**82.57%** (+1.74 pts). Ratchet **efectivo**: `floor(82.57)−1 = 81`
  → gate `--cov-fail-under` **80→81** en `Makefile` (target `cov` + comentario + nota). `docs/COVERAGE_ROADMAP.md`:
  header (medición 81.09→82.57% limpio, gate 80→81, margen +12.57) + entrada Ciclo 28 en el histórico.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (`ruff` app/sdk/tests), typecheck ✓ (`mypy app/`, 0 errores),
test ✓ (**1192 pass** + 2 skip, era 1154: +38 nuevos), cov ✓ (**82.83%** con el fichero suelto / **82.57%** en
checkout limpio, ambos ≥ gate **81**). Frontend no tocado (no aplica `frontend-lint`). Sin procesos residuales
(ciclo solo-tests, sin runtime).

> **NOTA de medición (honestidad, igual que Ciclo 27):** el árbol de trabajo sigue incluyendo el cambio
> **pre-existente sin commitear ajeno a este ciclo** (`tests/test_api_prompts_codex.py`, no tocado por Ciclo 28).
> El **árbol commiteado por este ciclo** (sin ese fichero, medido vía `git stash push` → `pytest --cov=app` →
> `stash pop`) mide **82.57%** (1154 pass); con el fichero suelto daría 82.83% (1192 pass). El ratchet a **81** se
> fija sobre la medición **limpia** (`floor(82.57)−1 = 81`), segura en checkout limpio (margen +1.57). Sigue
> pendiente para Jessicache: decidir qué hacer con ese cambio suelto de `test_api_prompts_codex.py`.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems humano-dependientes**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Cobertura: con
`frangels.py` cerrado, los mayores huecos que quedan son **routers grandes aún sin cubrir descubiertos al medir el
baseline**: `app/api/v1/system.py` (414 stmts, **35%**, 270 miss — el mayor bloque descubierto del proyecto ahora),
`app/api/v1/energy.py` (133 stmts, **33%**, 89 miss), `app/api/v1/gateway.py` (70 stmts, 60%), `app/api/v1/events.py`
(69 stmts, 68%); y del eje SDK `app/sdk/client.py` (197 stmts, 59%, 80 miss). Dir legacy vacío
`micelia/vital-core/docs/` sigue en árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin
`/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 29 — NEXT STEP):** el mayor bloque descubierto pasa a ser **`app/api/v1/system.py`** (414 stmts,
35%, 270 miss — router de integración macOS/sistema; inspeccionar dependencias, probablemente `osascript`/`app.state`,
y montarlo sobre `FastAPI()` local con los servicios mockeados, mismo patrón; gran ganancia de golpe → gate 81→82+).
Alternativa de menor tamaño pero también alta: **`app/api/v1/energy.py`** (133 stmts, 33%, 89 miss). Candidato del
eje SDK: **`app/sdk/client.py`** (197 stmts, 59%, 80 miss — cliente HTTP con `respx`/`httpx` mock). **Recomendado:
(a) `system.py`** por ganancia/esfuerzo. No tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-13 — Ciclo 27 (cierre de huecos residuales en 8 módulos near-100% → 100% · verify verde 1154 pass · cov 80.70→81.09% · gate 79→80)

**Contexto:** Ciclo 26 (2026-07-12) cerró `osascript.py` 24→100% (el último bloque descubierto grande) dejando `make
verify` verde y recomendó como "Mañana (Ciclo 27)" la vía (a): **cerrar los huecos pequeños de alto valor** —
medir con `term-missing` los módulos con menos miss y cerrarlos en un solo ciclo "hasta rozar ~81% (ratchet a 80)".
Prioridad #1 (rojo→verde) satisfecha en baseline y hito DoD ≥70% cumplido → el día cae en **prioridad #3 (roadmap:
subir cobertura)**. Baseline vivo confirmado verde antes de tocar nada: **1138 pass + 2 skip, cov 80.70%** (algo por
encima del 80.44% documentado — la suite había crecido), gate 79. Medición `term-missing`: ya **no quedan bloques
descubiertos grandes**; solo huecos repartidos en 8 módulos near-100% (24-27 stmts). Como el baseline real (80.70%)
era mayor de lo previsto, cerrarlos **cruza el 81.0% sin necesidad de tocar módulos grandes** (ni el `sdk/client.py`
59%). Todos ya tenían `tests/test_*_codex.py` (salvo `angels`, sin fichero) → se **añaden casos**. Trabajo
autónomo-seguro: solo tests + Makefile + docs, sin infra/red/`.env`/`uv.lock`, sin tocar runtime de `app/`.

**Hecho (3 commits atómicos):**
- `test(services)`: **+16 tests** cerrando 8 módulos near-100% a **100%, 0 miss**:
  - `agents/prompt_os_agents.py` 98→100% (miss 54-55): `_extract_json` con bloque `{...}` de JSON inválido → el
    regex lo captura, `json.loads` lanza `JSONDecodeError` (`except pass`) y termina en el `raise ValueError`.
  - `context_assembler.py` 97→100% (miss 103-104, 144-145): las dos ramas `except Exception: pass` de lectura de
    `cowork.md` (layer 0) y del md de lista activa (layer 1), forzando `IsADirectoryError` (el path existe pero es
    un directorio) → el ensamblado degrada sin propagar.
  - `frangels/quota_manager.py` 97→100% (miss 84-85, 95-96, 292, 294): `_load` con `usage.json` corrupto → `except`
    logea y degrada a vacío; `_save` con `usage_file` apuntando a un directorio → `write_text` lanza → `except`
    logea; `get_best_provider(require_vision=True)`/`(require_tools=True)` → el `continue` que excluye ángeles sin
    esa capacidad (deepseek/cohere/mistral/huggingface sin visión; huggingface sin tools).
  - `google_calendar.py` 98→100% (miss 24-28): el guard `except ImportError` del import opcional de google libs
    (que SÍ están instaladas aquí, por eso no corría). Nuevo `TestImportFallback`: `importlib.reload` con los 3
    submódulos (`google.oauth2.credentials`, `google_auth_oauthlib.flow`, `googleapiclient.discovery`) puestos a
    `None` en `sys.modules` → `from … import …` lanza `ImportError` → `GOOGLE_LIBS_AVAILABLE=False`. Restaura
    `sys.modules` y hace `reload` de vuelta en `finally` (estado limpio, sin contaminar otros tests).
  - `prompt_agent.py` 98→100% (miss 161, 207, 221): rama `if group_id` que setea `correlation_id` (dos prompts
    pendientes con 2 tags compartidos → `_find_group` devuelve gid); y las dos coerciones de datetime naive→UTC de
    `scheduled_at` (207) y `created_at` (221) con ISO sin zona.
  - `service_registry.py` 97→100% (miss 112, 252-254): hint `else`→`make docker-full` cuando el conjunto unhealthy
    ≠ `{"health"}` (varios dominios habilitados y caídos); y el `except Exception` del loop de monitoring (`fake_sleep`
    lanza `RuntimeError` en la 1ª pasada → `log.error` + backoff `sleep(5)`, `CancelledError` en la 3ª → salida limpia).
  - `frangels/angels.py` 97→100% (miss 455, 460): nuevo `tests/test_angels_codex.py` para los helpers
    `get_inference_angels()` y `get_available_angels()` (lookups puros sobre `ANGEL_REGISTRY`).
  - `scheduler.py` 99→100% (miss 137): `except ImportError` de `_sync_calendar` (patcheando `get_google_calendar`
    para que lance `ImportError`, mismo shape que los tests hermanos de sync).
- `chore(cov)`: total 80.70%→**81.09%**. Ratchet **efectivo**: `floor(81.09)−1 = 80` → gate `--cov-fail-under`
  **79→80** en `Makefile` (target `cov` + comentario + nota). `docs/COVERAGE_ROADMAP.md`: header (medición
  80.44→81.09%, gate 79→80, margen +11.09) + entrada Ciclo 27 en el histórico.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (`ruff` app/sdk/tests), typecheck ✓ (`mypy app/`, 0 errores),
test ✓ (**1154 pass** + 2 skip, era 1138: +16 nuevos), cov ✓ (**81.09%** ≥ gate **80**). Frontend no tocado (no
aplica `frontend-lint`). Sin procesos residuales (ciclo solo-tests, sin runtime).

> **NOTA de medición (honestidad):** el 80.70%→81.09% se midió con el árbol de trabajo tal cual, que incluía un
> cambio **pre-existente y sin commitear ajeno a este ciclo** (`tests/test_api_prompts_codex.py`, +44 líneas, no
> tocado por Ciclo 27 y **dejado sin commitear a propósito** — no es mío). El **árbol commiteado por este ciclo**
> (sin ese fichero) mide **80.83%** (1136 pass), verificado por stash → `make cov` → pop. Sigue **≥ gate 80**
> (margen +0.83), así que el ratchet es seguro en checkout limpio. Pendiente para Jessicache: decidir qué hacer con
> ese cambio suelto de `test_api_prompts_codex.py`.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems humano-dependientes**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Cobertura: cerrados
los módulos de servicio near-100%, los mayores huecos que quedan son de **superficie no-crítica o cara de mockear**:
`app/sdk/client.py` 59% (80 miss — cliente HTTP del SDK, requiere respx/httpx exhaustivo), `app/api/v1/frangels.py`
36% (120 miss — router de providers), y colas menores en otros routers `ai.py`/`prompts.py`. Dir legacy vacío
`micelia/vital-core/docs/` sigue en árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin
`/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 28 — NEXT STEP):** sin huecos near-100% restantes, la cobertura sube ya solo atacando superficie
grande. Dos vías: (a) **`app/api/v1/frangels.py`** (187 stmts, 36%, 120 miss — el mayor router sin cubrir; montar
sobre `FastAPI()` local con `get_frangels_orchestrator`/`provider_store` mockeados, mismo patrón que los routers de
Ciclos 16-25, gran ganancia de golpe → gate 80→81+); o (b) **`app/sdk/client.py`** (197 stmts, 59%, 80 miss —
cliente HTTP del SDK con `respx`/`httpx` mock). **Recomendado: (a)** por ganancia/esfuerzo y por reutilizar el patrón
de routers ya establecido; (b) queda como candidato del eje SDK. Alternativa de eje nuevo: arrancar el ratchet `mypy
strict` en `app/services/frangels/` (~100% cubierto, superficie acotada). No tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 26 (servicio osascript.py 0%*→100% — PIVOTE de routers a servicios · verify verde 1120 pass · cov 76.94→80.44% · gate 75→79)

**Contexto:** Ciclo 25 (misma fecha) cerró el **backlog de routers a 0%** dejando `make verify` verde (1042 pass,
cov 76.94%, gate 75) y recomendó como "Mañana (Ciclo 26)" **pivotar de "cubrir routers" a "subir cobertura donde
más falta"**, con candidato #1 explícito: `app/services/osascript.py` (318 stmts, **24%** — el mayor bloque
descubierto del proyecto), evaluando cuánto es testeable mockeando el subprocess. Prioridad #1 (rojo→verde)
satisfecha en baseline y el hito ≥70% (DoD v0.1) cumplido → el día cae de nuevo en **prioridad #3 (roadmap: subir
cobertura hacia v0.2)**. Este ciclo cubre `osascript.py` — primer **servicio** atacado tras la campaña de routers.
Tras leer el módulo: todo son wrappers de `subprocess.run` + parseo de stdout → **100% testeable sin macOS real**.
Trabajo autónomo-seguro: sin infra, sin red, sin `.env`/secretos, sin `uv.lock`, sin tocar `app/` de runtime.
Baseline confirmado verde antes de tocar nada (1042 pass, 76.94%; `osascript.py` a 24%). (*medido 24%, no 0%.)

**Hecho (3 commits atómicos):**
- `test(services)` (`osascript.py`): nuevo `tests/test_osascript_codex.py` (**+78 tests**). Convención `_codex`
  (plantilla `test_tunnel_codex.py`). **Dos estrategias de mock complementarias**: (1) tests de helpers/verify
  parchean `osa.subprocess.run` — cubren las **4 ramas** de `_run_applescript` (`["osascript","-e",script]`) y
  `_run_applescript_file` (`["osascript"]` + `input=script`): éxito con `.strip()`, `returncode≠0`→`OSAScriptError`
  con `stderr`, `TimeoutExpired`→`OSAScriptError("timed out")`, `Exception` genérica→`OSAScriptError(str)`; y las
  ramas de `_verify_osascript`/`__init__` (rc0 ok, rc≠0→`log.warning`, excepción→`log.warning`; **ninguna propaga**)
  + singleton de módulo. (2) Los **~30 métodos públicos** parchean el helper de instancia
  (`patch.object(svc, "_run_applescript[_file]", ...)`) devolviendo string canned o lanzando `OSAScriptError`, lo
  que **aísla parseo y AppleScript construido** sin depender de detalles de subprocess: `split("|")`/`"|||"`/`", "`,
  degradación (`[]`/`None`/`False`/`""`), clamp de `set_volume` (150→100, −5→0), escape de `create_note`
  (`"`→`\\"`, `\\n`), `missing value`→`None` en `search_contacts`, y asserts del script (nombre de
  calendario/lista/carpeta, `subtitle "…"`, `make new tab` vs `set URL of current tab`, `due date:date`,
  `whose completed is false` presente/ausente). Grupos: sistema (info/frontmost/running/notification/say/volume/
  dark-mode), calendario, recordatorios, notas, safari, contactos, finder, clipboard, music. **`osascript.py`
  318/318 stmts, 100%, 0 miss.** Ni infra, ni red, ni `.env`.
- `chore(cov)`: total 76.94%→**80.44%** (+3.50 pts, **el mayor salto de un ciclo**). Ratchet **efectivo**:
  regla `floor(80.44)−1 = 79` → gate `--cov-fail-under` **75→79** en `Makefile` (target `cov` + comentario + nota).
  `docs/COVERAGE_ROADMAP.md` actualizado (medición + entrada Ciclo 26 en el histórico).
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (`ruff` app/sdk/tests), typecheck ✓ (`mypy app/`, 0 errores),
test ✓ (**1120 pass** + 2 skip, era 1042: +78 nuevos), cov ✓ (**80.44%** ≥ gate **79**). Frontend no tocado
(no aplica `frontend-lint`). Sin procesos residuales (ciclo solo-tests, sin runtime).

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems humano-dependientes**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Cobertura: con
`osascript.py` cerrado, ya **no quedan bloques descubiertos grandes**; el resto son huecos pequeños repartidos
(ver `term-missing`): `google_calendar.py` 240/98% (miss 24-28), `service_registry.py` 120/97%, `quota_manager.py`
188/97%, `context_assembler.py` 131/97%, `prompt_agent.py` 144/98%, `prompts.py`/`ai.py` en API. Dir legacy vacío
`micelia/vital-core/docs/` sigue en árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin
`/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 27 — NEXT STEP):** ya sin un único bloque descubierto grande, la cobertura sube más despacio.
Dos vías de valor: (a) **cerrar huecos pequeños de alto valor** — empezar por `app/services/google_calendar.py`
(miss 24-28, ~5 stmts: probable rama de import/config opcional) y `app/services/agents/prompt_os_agents.py`
(miss 54-55), baratos y suben el total; o (b) **iniciar el ratchet `mypy strict`** en `app/services/frangels/`
(~99% cubierto, superficie acotada) como nuevo eje de calidad además de cobertura. **Recomendado: (a)** medir con
`term-missing` los 3-4 módulos con menos miss y cerrarlos en un solo ciclo hasta rozar ~81% (ratchet a 80); dejar
(b) documentado como candidato de eje nuevo. No tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 25 (routers sync.py + audit.py 0%→100% — CIERRA backlog de routers a 0% · verify verde 1042 pass · cov 76.14→76.94% · gate 75 sin cambio)

**Contexto:** Ciclo 24 (misma fecha) dejó `make verify` verde (1021 pass, cov 76.14%, gate 75). Prioridad #1
(rojo→verde) satisfecha en baseline y el hito de cobertura ≥70% (DoD v0.1) cumplido → el día vuelve a caer en
**prioridad #3 del protocolo (roadmap: subir cobertura hacia v0.2)**. El propio Ciclo 24 recomendó como
"Mañana (Ciclo 25)" cubrir `app/api/v1/sync.py` (30 stmts) y luego `app/api/v1/audit.py` (25 stmts) — **los dos
últimos routers a 0%**. Este ciclo los cubre **ambos** para **cerrar el backlog de routers sin tests**. Trabajo
autónomo-seguro: sin infra, sin red, sin `.env`/secretos, sin `uv.lock`; mismo patrón de Ciclos 16-24. Baseline
confirmado verde antes de tocar nada (1021 pass, 76.14%; `sync.py` 30/30 y `audit.py` 25/25 a 0%).

**Hecho (4 commits atómicos):**
- `test(api)` (`sync.py`): nuevo `tests/test_api_sync_codex.py` (**+9 tests**). Monta `sync.router` sobre un
  `FastAPI()` local. **Patrón `app.state`** (como `dashboard.py`/`agents.py`): el router lee el servicio desde
  `request.app.state.md_sync`, así que el fake se **inyecta en `app.state`** (no monkeypatch de import); ausente →
  `getattr(..., None)` → rama "not initialized". El fake `md_sync` (`MagicMock`): `get_status` síncrono →
  `MagicMock`; `full_sync`/`get_today_inbox_md` **awaited** → `AsyncMock`. Cubre los **3 endpoints** y sus ramas:
  `GET /status` (sin servicio→`disabled`; con servicio→delega en `get_status`, `assert_called_once_with()`),
  `POST /run` (sin servicio→`error` + `full_sync` **no** awaited; con servicio→`await full_sync` + respuesta
  `{status:ok, timestamp, result}` con `result` reflejado), `GET /inbox` (sin servicio→`PlainTextResponse` **503**;
  con contenido→markdown tal cual con `media_type=text/markdown`; contenido `""`/`None` **parametrizado**→fallback
  "# Inbox <fecha>\\n\\n_No captured prompts today._"), y `test_requires_auth` **parametrizado** sobre los 3
  endpoints (401/403 sin `X-API-Key`). Router **30/30 stmts, 100%, 0 miss**. Ni infra, ni red, ni `.env`.
- `test(api)` (`audit.py`): nuevo `tests/test_api_audit_codex.py` (**+12 tests**). Monta `audit.router` sobre un
  `FastAPI()` local. **Patrón import a nivel de módulo** (como `budget.py`/`tunnel.py`): el router obtiene el
  servicio por `from app.services.entire_session import get_entire_service`, así que se monkeypatchea el nombre ya
  enlazado en el namespace del módulo: `monkeypatch.setattr("app.api.v1.audit.get_entire_service", lambda: fake)`
  → el singleton real (`EntireSessionService`) nunca se construye. El fake es un `MagicMock` **síncrono** (ningún
  método se `await`ea). Cubre los **4 endpoints** y sus ramas: `GET /status` (delega en `get_status`), `GET
  /sessions` (defaults `limit=50`/`offset=0` + **eco** con assert de kwargs `limit`/`offset`; `total=len(sessions)`),
  `GET /sessions/{id}` (encontrado→sesión; `None`→**404** `"Session not found"`), `GET /prompts/{id}/sessions`
  (`{prompt_id, sessions}`), y `test_requires_auth` **parametrizado** (401/403). Router **25/25 stmts, 100%, 0
  miss**. Ni infra, ni red, ni `.env`.
- `chore(cov)`: ambos routers suben el total 76.14%→**76.94%** (6.912 stmts). **Ratchet no-op**: la regla
  conservadora del log es `floor(medido)−1 = floor(76.94)−1 = 75`, así que el gate `--cov-fail-under` del `Makefile`
  **se mantiene en 75** (subir a 76 exigiría medir ≥77%). `Makefile`: solo el comentario/nota del target `cov`
  (medido 76.14→76.94%). `docs/COVERAGE_ROADMAP.md`: header (última medición 76.14→76.94%, margen +6.94) + línea del
  Ciclo 25 en el histórico anotando el ratchet no-op y el cierre del backlog de routers a 0%.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (Ruff `app/ sdk/ tests/`), typecheck ✓ (mypy `app/`, 0 errores),
test ✓ (**1042 pass** + 2 skip, era 1021: +21 nuevos), cov ✓ (**76.94%** ≥ gate **75**). Frontend no tocado (sin
`frontend-lint`). Sin gateway ni infra levantados (tests puros ASGI in-process); sin procesos `uvicorn`/podman
residuales.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems que dependen de humano**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar el doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. **Ya no quedan
routers a 0%** — backlog de routers cerrado (`prompts`, `routine`, `mcp`, `skills`, `calendar`, `dashboard`,
`agents`, `budget`, `tunnel`, `sync`, `audit` todos cubiertos). Dir legado vacío `micelia/vital-core/docs/` sigue en
árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por Jessicache,
Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 26):** sin routers a 0% restantes, **pivotar** de "cubrir routers" a subir cobertura donde más
falta. Dos candidatos de mayor valor: (a) `app/services/osascript.py` (318 stmts, **24%** — el mayor bloque sin
cubrir del proyecto; ~242 stmts miss, integración macOS — evaluar cuánto es testeable sin `osascript` real vía
mocks de subprocess, o marcar lo no-testeable); (b) arrancar el ratchet `mypy strict` en `app/services/frangels/`
(~99% cubierto, superficie acotada). Recomendado: empezar por (a) acotando a los helpers puros/parseables de
`osascript.py` con `create_subprocess_exec` mockeado (patrón Ciclo 12 de `entire_session.py`), midiendo ganancia
antes de comprometer el gate. Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 24 (router tunnel.py 0%→100% + ratchet gate 74→75 · verify verde 1021 pass · cov 75.67→76.14%)

**Contexto:** Ciclo 23 (misma fecha) dejó `make verify` verde (1008 pass, cov 75.67%, gate 74). Prioridad #1
(rojo→verde) satisfecha en baseline y el hito de cobertura ≥70% (DoD v0.1) cumplido → el día vuelve a caer en
**prioridad #3 del protocolo (roadmap: subir cobertura hacia v0.2)**. El propio Ciclo 23 recomendó como
"Mañana (Ciclo 24)" cubrir el siguiente router a 0% de mayor ganancia (`app/api/v1/tunnel.py`, 33 stmts — **el
router, no el servicio `app/services/tunnel.py` ya al 100%**) con `get_tunnel_service` mockeado + ratchet del gate.
Trabajo autónomo-seguro: sin infra, sin red, sin `.env`/secretos, sin `uv.lock`; mismo patrón de Ciclos 16-23.
Baseline confirmado verde antes de tocar nada (1008 pass, 75.67%; `tunnel.py` router 33/33 a 0%).

**Hecho (3 commits atómicos):**
- `test(api)`: nuevo `tests/test_api_tunnel_codex.py` (**+13 tests**). Monta `tunnel.router` sobre un `FastAPI()`
  local. **Mismo shape que Ciclo 23 (budget)**: el router obtiene el servicio por **import a nivel de módulo**
  (`from app.services.tunnel import get_tunnel_service`), así que se monkeypatchea el nombre ya enlazado en el
  namespace del módulo: `monkeypatch.setattr("app.api.v1.tunnel.get_tunnel_service", lambda: fake)` → el singleton
  real (`TunnelService`) nunca se construye, `pyngrok` jamás se importa, cero red. El fake: `start`/`stop` son
  `await`eados → `AsyncMock`; `get_info` es síncrono → `MagicMock` con dict plano; `is_connected`/`public_url` son
  atributos → valores planos. Cubre los **4 endpoints** y todas sus ramas: `GET /status` y `GET /info` (delegan a
  `get_info`, con `assert_called_once_with()`), `POST /start` (**3 ramas**: `is_connected`→early return con
  `public_url` sin `await` de `start`; no-conectado + `start` devuelve URL→`{success, public_url}`; no-conectado +
  `start`→`None`→**HTTP 500**) con el **plumbing del port** (body `{port: N}`→`start` awaited con `N`; sin body
  →`request None`→`None`; body vacío `{}`→`None`), `POST /stop` (**2 ramas**: no-conectado→early return sin `await`
  de `stop`; conectado→`await stop` + mensaje) y `test_requires_auth` **parametrizado** sobre los 4 endpoints
  (401/403 sin `X-API-Key`). El router queda **33/33 stmts, 100%, 0 miss**. Ni infra, ni red, ni `.env`.
- `chore(cov)`: `tunnel.py` cubierto sube el total 75.67%→**76.14%** (6.912 stmts). **Ratchet efectivo**: la regla
  conservadora del log es `floor(medido)−1 = floor(76.14)−1 = 75`, así que el gate `--cov-fail-under` del `Makefile`
  sube **74→75** (target `cov`, comentario y nota actualizados: medido 75.17→76.14%). `docs/COVERAGE_ROADMAP.md`:
  header 75.67→76.14% (margen +6.14, gate 75) + línea del Ciclo 24 en el histórico.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (Ruff `app/ sdk/ tests/`), typecheck ✓ (mypy `app/`, 0 errores),
test ✓ (**1021 pass** + 2 skip, era 1008: +13 nuevos), cov ✓ (**76.14%** ≥ gate **75**). Frontend no tocado (sin
`frontend-lint`). Sin gateway ni infra levantados (tests puros ASGI in-process); sin procesos `uvicorn`/podman
residuales.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems que dependen de humano**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar el doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Routers aún a
0% (cubribles sin infra, mismo patrón): `sync.py` (30 stmts), `audit.py` (25). **Siguiente de mayor ganancia:
`sync.py`.** Dir legado vacío `micelia/vital-core/docs/` sigue en árbol (anotado, intacto). Frontend
`middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 25):** seguir prioridad #3 con el siguiente router a 0% de mayor ganancia,
`app/api/v1/sync.py` (30 stmts) — inspeccionar sus dependencias (probablemente `app.state` / un servicio de sync
markdown) y montarlo sobre `FastAPI()` local con `AsyncMock`/`MagicMock`, mismo patrón; ratchet gate 75→76 **sólo
si** la medición alcanza ≥77%. Tras `sync.py` queda `audit.py` (25 stmts) para cerrar los routers a 0%. Alternativa
si resulta bloqueado: arrancar el ratchet `mypy` hacia `strict` en `app/services/frangels/` (~99% cubierto). Sin
tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 23 (router budget.py 0%→100% · verify verde 1008 pass · cov 75.17→75.67% · gate 74 sin cambio)

**Contexto:** Ciclo 22 (misma fecha) dejó `make verify` verde (993 pass, cov 75.17%, gate 74) con el DoD v0.1
cerrado salvo los 2 ítems que dependen de humano. Prioridad #1 (rojo→verde) satisfecha en baseline y el hito de
cobertura ≥70% cumplido → el día cae en **prioridad #3 del protocolo (roadmap: subir cobertura hacia v0.2)**. El
propio Ciclo 22 recomendó como "Mañana (Ciclo 23)" cubrir el siguiente router a 0% de mayor ganancia
(`app/api/v1/budget.py`, 34 stmts) con el policy engine mockeado + ratchet del gate. Trabajo autónomo-seguro: sin
infra, sin red, sin `.env`/secretos, sin `uv.lock`; mismo patrón de Ciclos 16-22. Baseline confirmado verde antes
de tocar nada (993 pass, 75.17%).

**Hecho (3 commits atómicos):**
- `test(api)`: nuevo `tests/test_api_budget_codex.py` (**+15 tests**). Monta `budget.router` sobre un `FastAPI()`
  local. **Diferencia con Ciclos 21/22**: `budget.py` obtiene el motor por **import a nivel de módulo**
  (`from ...policy_engine import get_policy_engine`, no `app.state`), así que se monkeypatchea el nombre ya
  enlazado en el namespace del módulo: `monkeypatch.setattr("app.api.v1.budget.get_policy_engine", lambda: fake)`
  → el singleton real nunca se construye (sin disco/estado global). El fake es un `MagicMock` síncrono (el router
  no `await`ea ninguno de sus métodos); `evaluate` devuelve un `PolicyDecision` **real** para que la proyección
  de los 5 campos quede JSON-serializable. Cubre los **4 endpoints** y sus ramas: `GET /status` (happy +
  `assert_called_once_with()`), `PATCH /limits` (assert kwargs `daily`/`monthly` en body completo/vacío→`None`/
  parcial), `POST /category-policy` (happy con assert de la llamada + **las 5 políticas válidas parametrizadas** +
  **política inválida→400** con `set_category_policy` no llamado + **body incompleto→422**), `POST /evaluate`
  (defaults `note`/`free-first` con assert del dict pasado + query explícita + assert de los 5 campos proyectados)
  y `test_requires_auth` (401/403 sin `X-API-Key`). El router queda **34/34 stmts, 100%, 0 miss**. Ni infra, ni
  red, ni `.env`.
- `chore(cov)`: `budget.py` cubierto sube el total 75.17%→**75.67%** (6.912 stmts). **Gate `--cov-fail-under` se
  mantiene en 74** — la regla conservadora del log es `floor(medido)−1 = floor(75.67)−1 = 74`; para subir a 75 haría
  falta medir ≥76%, así que el ratchet es **no-op** este ciclo y el `Makefile` no se toca. `docs/COVERAGE_ROADMAP.md`:
  añade la medición del Ciclo 23 al histórico (header 75.17→75.67%, margen +5.67) con la nota del ratchet no-op.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (Ruff `app/ sdk/ tests/`), typecheck ✓ (mypy `app/`, 0 errores),
test ✓ (**1008 pass** + 2 skip, era 993: +15 nuevos), cov ✓ (**75.67%** ≥ gate **74**). Frontend no tocado (sin
`frontend-lint`). Sin gateway ni infra levantados (tests puros ASGI in-process); sin procesos `uvicorn`/podman
residuales.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems que dependen de humano**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar el doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Routers aún a
0% (cubribles sin infra, mismo patrón): `tunnel.py` (33 stmts — el router, no el servicio ya cubierto), `sync.py`
(30), `audit.py` (25). **Siguiente de mayor ganancia: `tunnel.py`.** Dir legado vacío `micelia/vital-core/docs/`
sigue en árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por
Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 24):** seguir prioridad #3 con el siguiente router a 0% de mayor ganancia,
`app/api/v1/tunnel.py` (33 stmts, el router — **ojo, no el servicio `app/services/tunnel.py` ya cubierto**) —
inspeccionar sus dependencias (probablemente `app.state` / un manager de túnel ngrok) y montarlo sobre `FastAPI()`
local con `AsyncMock`/`MagicMock`, mismo patrón; ratchet gate 74→75 **sólo si** la medición alcanza ≥76%.
Alternativa si resulta bloqueado: arrancar el ratchet `mypy` hacia `strict` en `app/services/frangels/` (~99%
cubierto). Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 22 (router agents.py 0%→100% + ratchet gate 73→74 · verify verde 993 pass · cov 74.26→75.17%)

**Contexto:** Ciclo 21 (misma fecha) dejó `make verify` verde (977 pass, cov 74.26%, gate 73). Prioridad #1
(rojo→verde) satisfecha en baseline y el hito de cobertura ≥70% (DoD v0.1) cumplido → el día vuelve a caer en
**prioridad #3 del protocolo (roadmap: subir cobertura hacia v0.2)**. El propio Ciclo 21 recomendó como
"Mañana (Ciclo 22)" cubrir el siguiente router a 0% de mayor ganancia (`app/api/v1/agents.py`, 63 stmts) con
sus dependencias `app.state` (`crew_manager`/`workflow_engine`) mockeadas + ratchet del gate. Trabajo
autónomo-seguro: sin infra, sin red, sin `.env`/secretos, sin `uv.lock`; mismo patrón de Ciclos 16-21.

**Hecho (3 commits atómicos):**
- `test(api)`: nuevo `tests/test_api_agents_codex.py` (**+16 tests**). Monta `agents.router` sobre un
  `FastAPI()` local e inyecta en `app.state` los colaboradores del sistema multi-agente: `crew_manager`
  (`MagicMock`; `execute` = `AsyncMock` por ser `await`eado, `list_crews`/`create_crew` síncronos) y
  `workflow_engine` (`MagicMock`; `get_runs`/`get_run` síncronos). Cubre los **6 endpoints** y sus ramas:
  `GET /crews` (happy + 503 sin manager vía `_get_crew_manager`), `POST /crews` (happy con assert de kwargs +
  `ValueError`→400 + validación 422 por `agents` vacío), `GET /workflows` (contra el registro real `WORKFLOWS`,
  5 defs, sin mock — `count`, claves por workflow y `agents_used` de-duplicado), `POST /execute` (happy +
  rama `status=="failed"`→`log.warning` + 503 sin manager, con assert de `execute` awaited), `GET /runs`
  (proyección de campos + eco de `limit`/`offset`, validación `le=200`→422, 503 sin engine vía
  `_get_workflow_engine`) y `GET /runs/{id}` (happy + `None`→404), más `test_requires_auth` (401/403). El
  router queda **63/63 stmts, 100%, 0 miss**. Ni infra, ni red, ni `.env`.
- `chore(cov)`: sube el gate `--cov-fail-under` del `Makefile` **73→74** (regla `floor(medido)−1 = floor(75.17)−1 = 74`)
  y actualiza el comentario/nota del target `cov` (medido 74.26→75.17%). `docs/COVERAGE_ROADMAP.md`: añade la
  medición del Ciclo 22 al histórico y tacha `agents.py` en la tabla de media prioridad (ahora cubierta).
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (Ruff `app/ sdk/ tests/`), typecheck ✓ (mypy `app/`, 0 errores),
test ✓ (**993 pass** + 2 skip, era 977), cov ✓ (**75.17%** ≥ gate **74**). Frontend no tocado (sin `frontend-lint`).
Sin gateway ni infra levantados (tests puros ASGI in-process); sin procesos `uvicorn`/podman residuales.

**Bloqueado/pendiente:** DoD v0.1 — mismos **2 ítems que dependen de humano**: (1) QA visual de los 4 flujos del
frontend; (2) actualizar el doc canónico `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado T0. Routers aún a
0% (cubribles sin infra, mismo patrón): `budget.py` (34 stmts), `tunnel.py` (33 — el router, no el servicio ya
cubierto), `sync.py` (30), `audit.py` (25). **Siguiente de mayor ganancia: `budget.py`.** Dir legado vacío
`micelia/vital-core/docs/` sigue en árbol (anotado, intacto). Frontend `middleware.ts`: `PUBLIC_PATHS` sin
`/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas (Jessicache): hosting/DNS/TLS de `*.idmmortality.com`
(Hito 3) y el eventual retorno del funnel público (aparcado desde Ciclo 16).

**Mañana (Ciclo 23):** seguir prioridad #3 con el siguiente router a 0% de mayor ganancia,
`app/api/v1/budget.py` (34 stmts) — inspeccionar sus dependencias (probablemente `app.state` +
`get_policy_engine`/quota, agregación read-only) y montarlo sobre `FastAPI()` local con `AsyncMock`/`MagicMock`,
mismo patrón; ratchet gate 74→75 si la medición lo permite. Alternativa si resulta bloqueado: arrancar el ratchet
`mypy` hacia `strict` en `app/services/frangels/` (~99% cubierto). Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 21 (router dashboard.py 0%→100% + ratchet gate 72→73 · verify verde 977 pass · cov 73.18→74.26%)

**Contexto:** Ciclo 20 (misma fecha) dejó `make verify` verde (962 pass, cov 73.18%, gate 72) con el
**DoD v0.1 cerrado salvo los 2 ítems que dependen de humano** (QA visual frontend + doc Nodo 1), ambos
ya escalados. Prioridad #1 (rojo→verde) satisfecha en baseline y el hito de cobertura ≥70% cumplido →
el día cae en **prioridad #3 del protocolo (roadmap: subir cobertura hacia v0.2)**. El propio Ciclo 20
recomendó como "Mañana (Ciclo 21)" cubrir el siguiente router a 0% de mayor ganancia
(`app/api/v1/dashboard.py`, 75 stmts) con `app.state` mockeado + ratchet del gate. Trabajo
autónomo-seguro: sin infra, sin red, sin `.env`/secretos, sin `uv.lock`; mismo patrón de Ciclos 16-20.

**Hecho (3 commits atómicos):**
- `test(api)`: nuevo `tests/test_api_dashboard_codex.py` (**+15 tests**). Monta `dashboard.router` sobre
  un `FastAPI()` local; fija en `app.state` los seis insumos del agregador (`prompt_store`,
  `prompt_executor`, `prompt_agent`, `prompt_scheduler`, `google_calendar`) a `AsyncMock`/`MagicMock`
  (métodos `await`eados = `AsyncMock`; escalares leídos por `getattr` — `completed_today`, `is_running`,
  `active_count`, `is_connected` — como valores reales) y monkeypatchea
  `app.services.frangels.policy_engine.get_policy_engine` (import función-local en `_get_budget`). El
  singleton real del policy engine nunca se construye. Cubre el endpoint `GET /dashboard/summary` y las
  **6 sub-agregaciones** con todas sus ramas: `_get_activity` (sin store→defaults / dicts con `total` /
  no-dict→`isinstance` falso / `Exception`→warning+defaults / executor presente vs ausente), `_get_budget`
  (engine con budget / `except`→ceros / clave ausente→default), `_get_queue_preview` y `_get_recent_results`
  (sin store→`[]` / dict con `prompts` / no-dict→`[]` / `Exception`→`[]`, truncado `content[:100]` y
  defaults por campo), `_get_agent_status` (todos presentes / parciales / ausentes), `_get_calendar_upcoming`
  (ausente / presente-no-conectado / conectado con eventos `dateTime`+`date` / `Exception`→`[]` / `None`→`[]`)
  y 401/403 sin `X-API-Key`. **`dashboard.py` 0%→100%** (75 stmts, 0 miss).
- `chore(cov)`: `dashboard.py` cubierto sube el total 73.18%→**74.26%** (6.912 stmts). `--cov-fail-under`
  72→**73** en el target `cov` del `Makefile` (criterio conservador `floor(medido)−1`, ~1.26 pts de
  margen) + header e histórico de `docs/COVERAGE_ROADMAP.md` con la línea del Ciclo 21.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓ (mypy app/, 0
errores) · test ✓ (**977 pass** + 2 skip, era 962: +15 nuevos) · cov ✓ (**74.26%** ≥ gate 73, era 73.18%
/gate 72). Frontend no tocado → no aplica `frontend-lint`. No se arrancó gateway ni infra; sin procesos
residuales. Baseline confirmado verde antes de tocar nada.

**Bloqueado/pendiente:**
- **DoD v0.1 — 2 ítems abiertos, ambos requieren humano** (sin cambios respecto a Ciclos 19/20): (1) QA
  visual de los 4 flujos de frontend; (2) actualización del doc canónico
  `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado de T0.
- Routers `app/api/v1/*` aún a 0% (cubribles sin infra, mismo patrón): `agents.py` (63 stmts),
  `budget.py` (34), `tunnel.py` (33 — el router, no el servicio ya cubierto), `sync.py` (30),
  `audit.py` (25). Siguiente de mayor ganancia: `agents.py`.
- Dir legacy vacío `micelia/vital-core/docs/` sigue en el árbol — anotado, no tocado (git no versiona
  dirs vacíos; candidato a limpieza sólo si Jessicache lo aprueba explícitamente).
- Frontend `middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas las de Jessicache: hosting/DNS/TLS de
`*.idmmortality.com` (Hito 3) y eventual retorno del funnel público.

**Mañana (Ciclo 22):** seguir prioridad #3 con el siguiente router a 0% de mayor ganancia,
`app/api/v1/agents.py` (63 stmts) — inspeccionar sus dependencias (probablemente `app.state`
crew_manager/workflow_engine + agregación read-only) y montarlo sobre `FastAPI()` local con
`AsyncMock`/`MagicMock`, mismo patrón; ratchet gate 73→74 si la medición lo permite. Alternativa si
resulta bloqueado: arrancar el ratchet `mypy` hacia `strict` en `app/services/frangels/` (~99% cubierto).
Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 20 (router calendar.py 0%→100% + ratchet gate 70→72 · verify verde 962 pass · cov 71.60→73.18%)

**Contexto:** Ciclo 19 (misma fecha) dejó `make verify` verde (933 pass, cov 71.60%, gate 70) con el
**DoD v0.1 cerrado salvo los 2 ítems que dependen de humano** (QA visual frontend + doc Nodo 1),
ambos ya escalados como bloqueo. Prioridad #1 (rojo→verde) satisfecha en baseline y hito de cobertura
cumplido → el día cae en **prioridad #3 del protocolo (roadmap: subir cobertura hacia v0.2)**. El
propio Ciclo 19 recomendó como "Mañana (Ciclo 20)" cubrir el siguiente router a 0% de mayor ganancia
(`calendar.py`, 109 stmts) con un fake de `get_google_calendar` + ratchet del gate. Trabajo
autónomo-seguro: sin infra, sin red, sin `.env`/secretos, sin `uv.lock`; mismo patrón de Ciclos 16/17/18.

**Hecho (3 commits atómicos):**
- `test(api)`: nuevo `tests/test_api_calendar_codex.py` (**+29 tests**). Monta `calendar.router` sobre
  un `FastAPI()` local con `get_google_calendar` monkeypatcheado a un `MagicMock` (métodos async que el
  router `await`ea = `AsyncMock`; síncronos `get_status`/`is_connected` = returns planos) → el singleton
  real nunca se construye, sin OAuth flow / token file / red. Cubre los **9 endpoints** y todas sus ramas:
  `/auth` (200/501 RuntimeError/400 ValueError/500), `/callback` (200/501/500/422 sin `code`), `/status`
  (200), `/calendars` (403 no conectado/200 count/500), `GET /events` (403/200 con `now`/200 con `date`
  válida/**400 fecha malformada propagada vía `except HTTPException: raise`**/500/422 `days` fuera de
  `[1,90]`), `POST /events` (403/200/400 ValueError/500/422 body incompleto), `/sync` (403/200/500),
  `DELETE /disconnect` (200/500) y 401/403 sin `X-API-Key`. **`calendar.py` 0%→100%** (109 stmts, 0 miss).
- `chore(cov)`: `calendar.py` cubierto sube el total 71.60%→**73.18%** (6.912 stmts). `--cov-fail-under`
  70→**72** en el target `cov` del `Makefile` (criterio conservador `floor(medido)−1`, ~1.18 pts de
  margen) + header e histórico de `docs/COVERAGE_ROADMAP.md` con la línea del Ciclo 20.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓ (mypy app/, 0
errores) · test ✓ (**962 pass** + 2 skip, era 933: +29 nuevos) · cov ✓ (**73.18%** ≥ gate 72, era 71.60%
/gate 70). Frontend no tocado → no aplica `frontend-lint`. No se arrancó gateway ni infra; sin procesos
residuales. Baseline confirmado verde antes de tocar nada.

**Bloqueado/pendiente:**
- **DoD v0.1 — 2 ítems abiertos, ambos requieren humano** (sin cambios respecto a Ciclo 19): (1) QA
  visual de los 4 flujos de frontend; (2) actualización del doc canónico
  `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado de T0.
- Routers `app/api/v1/*` aún a 0% (cubribles sin infra, mismo patrón): `dashboard.py` (75 stmts),
  `agents.py` (63), `budget.py` (34), `tunnel.py` (33 — ojo, es el router, no el servicio ya cubierto),
  `sync.py` (30), `audit.py` (25). Siguiente de mayor ganancia: `dashboard.py`.
- Dir legacy vacío `micelia/vital-core/docs/` sigue en el árbol — anotado, no tocado (git no versiona
  dirs vacíos; candidato a limpieza sólo si Jessicache lo aprueba explícitamente).
- Frontend `middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por Jessicache, Ciclo 16).

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas las de Jessicache: hosting/DNS/TLS de
`*.idmmortality.com` (Hito 3) y eventual retorno del funnel público.

**Mañana (Ciclo 21):** seguir prioridad #3 con el siguiente router a 0% de mayor ganancia,
`app/api/v1/dashboard.py` (75 stmts) — inspeccionar sus dependencias (probablemente `app.state`
prompt_store/service_registry + agregación read-only) y montarlo sobre `FastAPI()` local con
`AsyncMock`/`MagicMock`, mismo patrón; ratchet gate 72→73 si la medición lo permite. Alternativa si
resulta bloqueado: arrancar el ratchet `mypy` hacia `strict` en `app/services/frangels/` (~99% cubierto).
Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 19 (cierre parcial DoD v0.1 + fix quirk skills 503 · verify verde 933 pass · cov 71.58→71.60%)

**Contexto:** Ciclo 18 (misma fecha) alcanzó el **hito DoD ≥70% de cobertura** (verify verde, 932
pass, cov 71.58%, gate 70) y recomendó como "Mañana (Ciclo 19)": (1) reconciliar los checkboxes
del DoD `PLAN_MICELIA_v0.md §7` con evidencia, (2) FASE 5 — release notes, (3) opcional `fix(api)`
del quirk 503→500 de `skills.py`. Con prioridad #1 (rojo→verde) satisfecha en baseline y el hito de
cobertura cumplido, el día cae en **prioridad #2 (roadmap): cerrar el resto del DoD v0.1**. Estado
verificado hoy (read-only): grep de strings legado sobre `app/`+`sdk/` ya **vacío**;
`RELEASE_NOTES_MICELIA_v0.1.md` **existe pero fechado 24-may** (previo a Ciclos 6–18); checkboxes
del DoD todos `[ ]` aunque varios ya ciertos; quirk `skills.py` confirmado (un solo test lo pinaba).

**Hecho (3 commits atómicos):**
- `fix(api)` (`3886640`): `create_skill` y `list_skills` en `app/api/v1/skills.py` carecían de
  `except HTTPException: raise` antes del `except Exception` genérico → el 503 de `_get_manager`
  (store no inicializado) se tragaba y afloraba como **500**, inconsistente con los 6 endpoints
  hermanos. Añadida la cláusula a ambos (sin cambio de lógica de negocio). Tests en
  `tests/test_api_skills_codex.py`: renombrado `test_list_skills_quirk_503_becomes_500` →
  `test_list_skills_missing_store_503` (assert **503** + `"prompt_store not initialized"`), añadido
  `test_create_skill_missing_store_503` (POST con `CREATE_PAYLOAD` válido y `build_app()` sin store
  → 503), docstring del módulo actualizado (quirk → fixed). El fix añade una rama antes no cubierta
  → cov 71.58%→**71.60%**.
- `docs` (`7323b10`): (a) `RELEASE_NOTES_MICELIA_v0.1.md` — nueva **§11 addendum** (sin reescribir
  lo previo) documentando con evidencia el endurecimiento post-RC: cobertura 24%→71.58% (DoD T5.1),
  fix bcrypt del funnel (`bcrypt==4.0.1`) + `/register` + auto-login, fixes de contrato
  (`/prompts/lists` reordenada, `skills` 503); header actualizado a 2026-07-12. (b)
  `PLAN_MICELIA_v0.md §7` — **7/9 checkboxes del DoD marcados `[x]`** con evidencia inline (pytest
  932, cov 71.58%, grep legado limpio, alias `idm↔micelia` testeado, 5 dominios source-id válidos,
  `"micelia"` 6º source, release notes publicadas/actualizadas). Quedan `[ ]` los 2 dependientes de
  humano/doc externo: QA visual de 4 flujos frontend y update del doc canónico Nodo 1.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓ (mypy app/,
0 errores) · test ✓ (**933 pass** + 2 skip, era 932: −1 test renombrado, +2 nuevos) · cov ✓
(**71.60%** ≥ gate 70, era 71.58%). Frontend no tocado → no aplica `frontend-lint`. No se arrancó
gateway ni infra; sin procesos residuales. Baseline confirmado verde antes de tocar nada.

**Bloqueado/pendiente:**
- **DoD v0.1 — 2 ítems abiertos, ambos requieren humano:** (1) QA visual de los 4 flujos de
  frontend (`frontend-lint` valida lint+tipos, no el render); (2) actualización del doc canónico
  `Micelia_Nodo1_Impacto_Socioeconomico.md` con el estado de T0 (requiere montarlo en sesión).
- Routers `app/api/v1/*` aún a 0% (cubribles sin infra, mismo patrón; el DoD 70% ya está cumplido,
  margen +1.60): `calendar.py` (109 stmts), `dashboard.py` (75), `agents.py` (63), `budget.py` (34),
  `tunnel.py` (33), `sync.py` (30), `audit.py` (25).
- Dir legacy vacío `micelia/vital-core/docs/` sigue en el árbol (DoD §7 rebrand) — **anotado, no
  tocado** (guardarraíl: no reestructurar carpetas; git no versiona dirs vacíos). Candidato a
  limpieza si Jessicache lo aprueba explícitamente.
- Frontend `middleware.ts`: `PUBLIC_PATHS` sin `/register` (funnel APARCADO por Jessicache, Ciclo 16).
- `osascript.py` (24%, macOS-only) y `cli.py`/`main.py` — el roadmap los marca "no testear"/E2E.

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas las de Jessicache: hosting/DNS/TLS de
`*.idmmortality.com` (Hito 3) y eventual retorno del funnel público.

**Mañana (Ciclo 20):** el DoD v0.1 queda cerrado salvo los 2 ítems que dependen de Jessicache
(QA visual frontend + doc Nodo 1) → escalarlos como bloqueo humano. Trabajo autónomo-seguro
restante: (1) seguir prioridad #3 cubriendo el siguiente router a 0% de mayor ganancia
(`calendar.py`, 109 stmts, con fake de `get_google_calendar` en `app.state`) + ratchet gate 70→71
para ampliar margen; (2) alternativa: arrancar el ratchet mypy hacia `strict` en un paquete ya
cubierto (`app/services/frangels/` ~99%). Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 18 (routers mcp 0%→100% + skills 0%→100% · gate 67→70 · total 67.85→71.58% · **HITO DoD ≥70% ALCANZADO**)

**Contexto:** Ciclo 17 (misma fecha, ejecución anterior) dejó verify verde (866 pass, cov 67.85%,
gate 67) y recomendó cubrir el siguiente router a 0% de mayor ganancia. Prioridad #1 (red→green)
satisfecha → prioridad #3 (cobertura hacia el 70% del DoD). Cálculo previo: `mcp.py` solo (133
stmts) dejaría ~69.7% (corto), así que este ciclo cubre **ambos** candidatos con servicio backing
al 100%: `mcp.py` + `skills.py` (258 stmts) → cruza el 70%.

**Hecho (4 commits atómicos):**
- `test(api)` (`73a6b53`): nuevo `tests/test_api_mcp_codex.py` (**+35 tests**). Monta `mcp.router`
  sobre `FastAPI()` local con `get_mcp_generator` monkeypatcheado a `MagicMock` **síncrono** (el
  singleton real nunca se construye → sin escrituras a disco). Cubre el helper puro
  `_parse_prompt_to_spec` en directo (nombre por "called X" — ojo: el regex matchea leftmost, un
  prompt que empiece por create/build/make captura la palabra siguiente; fallback 3 primeras
  palabras; fallback `mcp-server`; tools por bullets; filtro de tokens ≤2 chars; cap de 10 tools;
  tool `process` por defecto; descripción truncada a 200) y los 8 endpoints con todas sus ramas:
  `/generate` (200 con kwargs exactos/400 ValueError/409 FileExistsError/500/422 name·tools·language),
  `/from-prompt` (200 con `parsed_from_prompt`+`parsed_spec`/400/500/422), `/servers` (200/500),
  `/servers/{id}` (200/404/500), DELETE (200/404/409 running/500), `/start` (200/404/409/500),
  `/stop` (200/409/500), `/templates` (estático) y 401/403 sin auth. `mcp.py` **0%→100%** (133 stmts, 0 miss).
- `test(api)` (`d2d1095`): nuevo `tests/test_api_skills_codex.py` (**+31 tests**). `AsyncMock` de
  `SkillsManager` inyectado en `app.state.skills_manager` con retornos explícitos dict/list/bool
  (el router hace `.get()` y `len()`). CRUD completo (POST 200 kwargs/400/500/422 · GET lista
  count+active/500 · GET slug 200/404/500 · PATCH exclude_none/400 body vacío/404/400/500 ·
  DELETE 200/404/500), acciones (toggle activated/**deactivated con `False is not None`**/404/500 ·
  test 200/404/`template_used == ""` con `get_skill` None/500/422) y las ramas fallback de
  `_get_manager` vía `GET /skills/{slug}`: sin `prompt_store` → 503, singleton fakeado
  (`skills.get_skills_manager` monkeypatcheado) con **cache en `app.state`** verificada,
  RuntimeError → 503. **QUIRK fijado (no corregido):** `list_skills`/`create_skill` no re-lanzan
  `HTTPException` → el 503 de `_get_manager` aflora como **500** en esas rutas (test lo pina;
  candidato `fix(api)` para un ciclo futuro). `skills.py` **0%→100%** (125 stmts, 0 miss).
- `chore(cov)` (`edb1a5a`): sube `--cov-fail-under` 67→**70** (medido **71.58%**) en `Makefile` +
  actualiza header e histórico de `docs/COVERAGE_ROADMAP.md`. **Criterio T5.1 del DoD v0.1
  (cov ≥ 70%) CUMPLIDO.**
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓ (mypy app/,
0 errores en 66 ficheros) · test ✓ (**932 pass** + 2 skip, era 866) · cov ✓ (**71.58%** ≥ gate 70,
era 67.85%). Frontend no tocado → no aplica `frontend-lint`. No se arrancó gateway ni infra; sin
procesos residuales.

**Bloqueado/pendiente:**
- Routers `app/api/v1/*` aún a 0%: `calendar.py` (109 stmts), `dashboard.py` (75), `agents.py` (63),
  `budget.py` (34), `tunnel.py` (33), `sync.py` (30), `audit.py` (25) — mismo patrón, cubribles sin
  infra si se quiere seguir subiendo el gate (el DoD 70% ya está cumplido; margen actual +1.58 pts).
- Quirk `skills.py`: 503 de `_get_manager` → 500 en `list_skills`/`create_skill` por falta de
  `except HTTPException: raise` (pinado en test; candidato `fix(api)` de bajo riesgo).
- Frontend `middleware.ts`: `PUBLIC_PATHS = ['/login']` no incluye `/register` → navegar directo a
  `/register` sin cookie redirige a `/login`. **No se toca** (funnel APARCADO por Jessicache,
  Ciclo 16), pero queda anotado para cuando se retome la exposición pública del funnel.
- `osascript.py` (24%, macOS-only) y `cli.py`/`main.py` — el roadmap los marca "no testear"/E2E.
- Restantes del DoD v0.1 (además de cov ✓): revisar strings legado (`vale`: `vital-core/docs/` vacío
  en el árbol), QA frontend asistido (FASE 4) y release notes — ver checkboxes de `PLAN_MICELIA_v0.md`.

**DECISIÓN PENDIENTE:** ninguna nueva. Siguen abiertas las de Jessicache: hosting/DNS/TLS de
`*.idmmortality.com` (Hito 3) y eventual retorno del funnel público.

**Mañana (Ciclo 19):** con el hito de cobertura del DoD cumplido, pasar a cerrar el resto del DoD
v0.1 (prioridad roadmap): (1) repasar los checkboxes de `PLAN_MICELIA_v0.md` §DoD y marcar los ya
cumplidos con evidencia (cov ≥70% ✓ hoy); (2) FASE 5 T5.2/T5.3 — revisión independiente + borrador
de `docs/RELEASE_NOTES_MICELIA_v0.1.md` si no existe actualizado; (3) opcional si sobra
presupuesto: `fix(api)` del quirk 503→500 en `skills.py` (añadir `except HTTPException: raise` a
`list_skills`/`create_skill`, 2 líneas + ajustar el test pinado) o seguir con `calendar.py` (109
stmts) para ampliar margen del gate. Sin tocar infra ni `uv.lock`.

**Status: IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 17 (cobertura router routine 0%→99% · gate 65→67 · total 65.47→67.85%)

**Contexto:** Ciclo 16 (misma fecha) dejó `make verify` verde (846 pass, cov 65.47%, gate 65) y las
landings APARCADAS por decisión de Jessicache → foco en el núcleo de Micelia. Prioridad #1
(red→green) satisfecha (verify verde confirmado en baseline) → el día cae a prioridad #3
(cobertura hacia el 70%, cadencia de Ciclos 6–16). Siguiente router de mayor ganancia a 0%
recomendado ayer: `routine.py` (165 stmts, con su parser puro `_parse_routine_md`).

**Hecho (3 commits atómicos):**
- `test(api)`: nuevo `tests/test_api_routine_codex.py` (**+20 tests**). Monta `routine.router` sobre
  un `FastAPI()` local; redirige `routine.ROUTINE_FILE` a un fixture temporal (`tmp_path`) que
  ejercita **todas** las ramas del parser (frontmatter tipado: string / lista YAML `[..]` /
  `true`/`false` → bool / dígito → int; actividades con time citado y sin citar (regex), duración
  no-numérica → default 30, descripción inline y multilínea `>` con salto de párrafo). Cubre los
  3 helpers puros (`_parse_routine_md`, `_compute_event_times`, `_tz_offset_for` con tz DST-aware
  Madrid +02/+01, offset negativo y fallback `+00:00` para tz inválida) y los 2 endpoints:
  `GET /today` (200 / 404 file-not-found / 500 parse-error / 401 sin auth) y `POST /sync`
  (403 gcal desconectado / 3 eventos creados / errores por evento / `create_prompts` con y sin
  `prompt_store` / error al crear prompt / params `date`+`calendar_id` propagados / 404 / 500).
  `get_google_calendar` fakeado (`is_connected` sync + `create_event` `AsyncMock`) y `prompt_store`
  `AsyncMock` en `app.state`. Sin Google Calendar / DB / red / subprocess. `routine.py` **0%→99%**
  (165 stmts, 1 miss — línea 191 `raise ValueError("no utcoffset")`, inalcanzable: un `ZoneInfo`
  válido siempre devuelve offset).
- `chore(cov)`: sube `--cov-fail-under` 65→**67** (medido 67.85%) en `Makefile` + actualiza header
  de `docs/COVERAGE_ROADMAP.md` con la medición de hoy.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓ (mypy app/,
0 errores) · test ✓ (**866 pass** + 2 skip, era 846) · cov ✓ (**67.85%** ≥ gate 67, era 65.47%).
Frontend no tocado → no aplica `frontend-lint`. No se arrancó gateway ni infra; sin procesos
residuales.

**Bloqueado/pendiente:**
- Otros routers `app/api/v1/*` siguen a 0%: `calendar.py` (109 stmts), `skills.py` (125), `mcp.py`
  (133), `agents.py` (63), `dashboard.py` (75), `budget.py` (34), `audit.py` (25), `sync.py` (30),
  `tunnel.py` (33) — mismo patrón de DI por `app.state` / singleton de servicio, cubribles sin infra
  (prioridad #3 hacia el 70% del DoD). `mcp.py`/`skills.py` con servicio backing al 100%.
- `osascript.py` (24%, macOS-only) y `cli.py`/`main.py` — el roadmap los marca "no testear"/E2E.

**Mañana (Ciclo 18):** seguir prioridad #3 — cubrir el siguiente router de mayor ganancia a 0%.
Candidatos por statements: `mcp.py` (133, servicio `mcp_generator` 100%, con `_parse_prompt_to_spec`
puro heurístico) o `skills.py` (125, `skills_manager` 100%) o `calendar.py` (109). Mismo patrón
`FastAPI()` local + fake del singleton de servicio, sin tocar infra ni `uv.lock`. Emparejar con
ratchet del gate. Objetivo DoD: cov ≥ 70% (a ~2 pts, alcanzable en 1 router más).

**IMPLEMENTADO ✅**

---

## 2026-07-12 — Ciclo 16 (cobertura router prompts 0%→93% · fix ruta /prompts/lists oculta · landings APARCADAS)

**Contexto:** Ciclo 15 dejó `make verify` verde (788 pass, cov 61.87%, gate 61%). Prioridad #1
(red→green) satisfecha → el día cae a prioridad #3 (cobertura hacia el 70%, cadencia de los
Ciclos 6–14). **DECISIÓN ESTRATÉGICA de Jessicache (hoy): se aparcan las landings.** Los
subdominios `*.idmmortality.com` (register./login.) tienen hosting **estático en IONOS** con HTML
de prueba; la idea previa (triple home estática + Stripe micro-donaciones + acceso temporal a
Micelia vía login) se descarta esta iteración: conectar HTML estático+JS a un proxy es una
chapuza porque al desplegar Micelia "de verdad" habría que **sincronizar los usuarios ya
registrados**. Conclusión: *nos olvidamos de landings y preparamos Micelia bien por dentro*. El
funnel register→login→micelia **deja de ser el próximo hito** (aparcado, no diferido). El trabajo
`/register`+`/login` ya existente se **conserva** (no se borra), solo se despriorizada su
exposición pública.

**Hecho (4 commits atómicos):**
- `fix(api)` (`83e1c8d`): **bug latente encontrado** al escribir los tests — `GET /prompts/lists`
  (`list_all_lists`) se declaraba DESPUÉS de `GET /{prompt_id}`, así que Starlette hacía match de
  `"lists"` como `prompt_id` y la validación UUID devolvía **422** → el endpoint de colección era
  **inalcanzable por HTTP**. Se mueve la ruta estática antes de la dinámica. Sin cambio de lógica;
  `/lists/{slug}` (2 segmentos) no colisiona y permanece en su sección.
- `test(api)` (`360307b`): nuevo `tests/test_api_prompts_codex.py` (**+58 tests**). Monta el
  router sobre un `FastAPI()` local e inyecta un `AsyncMock` `prompt_store` (y agent/executor mock
  para pipeline) en `app.state`. Cubre CRUD, notes, retry, classify, stage/approve/archive,
  promote list/skill/mcp, lists CRUD, pipeline status/pause/resume (con y sin componentes),
  degradación 503 (store `None`) y auth 401. Sin DB/HTTP/subprocess. `prompts.py` **0%→93%**
  (267 stmts, 18 miss — los guards `if not store` repetidos por endpoint).
- `chore(cov)` (`6fcc42f`): sube `--cov-fail-under` 61→**65** (medido 65.47%) + nota informativa.
- `docs(log)`: esta entrada.

**Verify:** `make verify` **100% VERDE** — lint ✓ · typecheck ✓ (mypy app/, 0 errores) · test ✓
(**846 pass** + 2 skip, era 788) · cov ✓ (**65.47%** ≥ gate 65, era 61.87%). Frontend no tocado
→ no aplica `frontend-lint`. No se arrancó gateway ni infra; sin procesos residuales.

**Bloqueado/pendiente:**
- Otros routers `app/api/v1/*` siguen a 0%: `routine.py`, `mcp.py`, `skills.py`, `calendar.py`,
  `dashboard.py`, `agents.py`, `budget.py`, `tunnel.py`, `audit.py`, `sync.py` — mismo patrón de
  DI por `app.state`, cubribles sin infra (prioridad #3 hacia el 70% del DoD).
- `osascript.py` (24%, macOS-only) y `cli.py`/`main.py` — el roadmap los marca "no testear"/E2E.

**DECISIÓN REGISTRADA (Jessicache):**
- **APARCADO: landings + funnel estático.** No se construyen las home estáticas en IONOS ni la
  integración Stripe/proxy sobre HTML estático (problema de sincronización de usuarios). Foco:
  núcleo de Micelia.
- **`*.idmmortality.com`** como destino de despliegue **de Micelia** (no de landings) sigue siendo
  decisión futura de Jessicache (hosting + DNS + TLS); preparable, no ejecutable (guardarraíles).

**Mañana (Ciclo 17):** seguir prioridad #3 — cubrir el siguiente router de mayor ganancia a 0%
(`routine.py` 165 stmts, con su `_parse_routine_md` puro; o `mcp.py`/`skills.py`, ambos con
servicio backing al 100%), mismo patrón `app.state` + `AsyncMock`, sin tocar infra ni `uv.lock`.
Emparejar con ratchet del gate. Objetivo DoD: cov ≥ 70%.

**IMPLEMENTADO ✅**

---

## 2026-07-11 — Ciclo 15 (Opción A APROBADA: funnel register→login desbloqueado · bug bcrypt resuelto · frontend /register)

**Contexto:** Ciclo 14 dejó `make verify` 100% verde (784 pass, cov 61.87%, gate 61%) y marcó
**hoy = Opción A, APROBADA por Jessicache**: desbloquear el funnel register/login, con permiso
explícito para tocar `uv.lock`. El bug estaba **confirmado empíricamente** en `.venv`: bcrypt
**5.0.0** + passlib **1.7.4** → passlib sondea `bcrypt.__about__.__version__` (eliminado en
bcrypt ≥ 4.1) y el primer `pwd_context.hash()`/`verify()` lanza `ValueError: password cannot be
longer than 72 bytes`. Es decir `POST /auth/register` y el login de usuarios reales daban **500**
en runtime — oculto porque `tests/test_auth_endpoints_codex.py` **mockea `pwd_context`**. Riesgo
de wheel descartado: Python 3.13.5, y bcrypt 4.0.1 publica wheel `cp36-abi3-universal2` (ABI
estable → 3.13, arm64) → instala sin build desde fuente.

- **Hecho (5 commits atómicos):**
  - `fix(auth)` (`e68a428`): pin **`bcrypt==4.0.1`** en `pyproject.toml` (última 4.0.x compatible
    con passlib 1.7.4) + `uv lock` (`uv.lock` bcrypt 5.0.0→4.0.1) + `uv sync --extra dev`.
    Prueba puntual tras el fix: `pwd_context.hash('…')` → `$2b$12$…` (len 60) y `verify` True/False
    correctos, sin `ValueError`. **Efecto lateral del sync:** el venv estaba drift-eado por delante
    del lock (starlette/uvicorn/etc.); `uv sync` lo realineó al lockfile committeado (estado
    reproducible), verify siguió verde.
  - `test(auth)` (`e19bed6`): nuevo `tests/test_auth_funnel_integration_codex.py` (+4 tests) que
    corre **bcrypt de verdad** (sin stub) y drive el round-trip register→login: register almacena
    un hash `$2b$` real, login lo verifica. **Falla con bcrypt 5.0.0, pasa con 4.0.1** → prueba
    ejecutable del fix. Sin DB/red: fake stateful de `user_store` en memoria (UserModel usa
    `PGUUID`, no portable a SQLite; `aiosqlite` no instalado). El autouse `stub_crypto` del otro
    archivo es local a su módulo → no contamina.
  - `feat(frontend)` (`9459ec3`): `frontend/src/app/register/page.tsx` (clon de `login/page.tsx`
    con campo email `type=email`, password min 8 = validador backend, auto-login) + `authApi.register`
    en `lib/api.ts` (POST `/auth/register`, 409→"Email already registered") + enlaces cruzados
    login↔register con `next/link`.
  - `chore(frontend)` (`b51518d`): `frontend/.eslintrc.json` (`next/core-web-vitals`) — `next lint`
    no tenía config y **colgaba** `make frontend-lint` con un prompt interactivo. Escapadas las 2
    únicas incidencias preexistentes (comillas en `QuotaMonitor.tsx`). `make frontend-lint` ahora
    corre limpio por primera vez.
  - `docs(log)`: esta entrada.

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓ (mypy
  app/, 0 errores) · test ✓ (**788 pass** + 2 skip, era 784) · cov ✓ (**61.87%** ≥ gate 61%,
  sin cambio — los 4 tests nuevos ejercitan `auth.py` ya cubierto). **`make frontend-lint` VERDE**
  (lint ✓ + type-check ✓, antes irrunnable). No se arrancó gateway ni infra; sin procesos residuales.

- **DECISIÓN PENDIENTE (Jessicache):**
  (1) **bug bcrypt — RESUELTO ✅** este ciclo (pin 4.0.1 + prueba de integración real). Ya no es
  pendiente.
  (2) **hosting + DNS + TLS de `*.idmmortality.com`** (Hito 3 deploy) — sigue siendo decisión solo
  de Jessicache; preparable por la tarea, no ejecutable (guardarraíl: sin push/secretos/infra).

- **Bloqueado/pendiente:**
  - **QA visual humano del `/register`** — `frontend-lint` valida lint+tipos, no el render; falta
    prueba visual/e2e del formulario en navegador.
  - Funnel end-to-end real (register→login contra Postgres) **no** ejercitado aún: requiere
    `make docker-infra` + `run-local.sh` (Hito 1, mañana).
  - `UserModel` usa `PGUUID` (no portable a SQLite/CI). Un test de integración con DB real hermética
    exigiría UUID cross-dialect + `aiosqlite`. No hoy.
  - dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand). Ratchet mypy hacia `strict` vivo.

- **Mañana (Ciclo 16 = Hito 1, validación local del funnel):** (1) `make docker-infra` (postgres+
  redis+ollama) + `bash scripts/run-local.sh start`, ejercitar `POST /auth/register`→`/auth/login`
  reales contra Postgres con `curl`/httpie y confirmar 201→200 (parar todo al terminar). (2) QA
  visual del `/register` (arrancar `frontend` :3001, registrar un usuario de prueba, verificar
  auto-login→redirect a `/`). (3) si ambos verdes, empezar Hito 2 (contenedor podman del gateway).
  Estimación a idmmortality.com: Hito 1 (funnel local e2e) ~días; Hito 2 (podman) ~1-2 semanas;
  Hito 3 (deploy real) dominado por cuándo Jessicache decida hosting+DNS+TLS.

- **Estado:** **IMPLEMENTADO ✅** (Opción A ejecutada; bug bcrypt resuelto + probado; `make verify`
  y `make frontend-lint` verdes; 5 commits atómicos).

---

## 2026-07-11 — Ciclo 14 (user_store 88→100% + prompt_store 95→100% · cobertura 61.62→61.87% · gate 60→61)

**Contexto:** Ciclo 13 dejó `make verify` 100% verde (778 pass, cov 61.62%, gate 60%). Este ciclo
**Jessicache está presente** y toma dos decisiones que cambian el rumbo: (1) **nuevo protocolo** —
cada rutina debe cerrar IMPLEMENTADA (no solo un plan) + línea de estado `IMPLEMENTADO ✅`/`⛔` en
el log (añadido a `DAILY_MICELIA_PLANNING.md` §Definition of done); (2) **secuencia B→A**: hoy la
tarea segura de cobertura (Opción B) y el **próximo ciclo desbloquea el funnel (Opción A), con
aprobación explícita para tocar `uv.lock`** → la **DECISIÓN PENDIENTE #1 (bcrypt) queda
DESBLOQUEADA** para el Ciclo 15. Opción B de hoy: los dos gaps "limpios" pequeños que quedaban
(`user_store.py` 88%, `prompt_store.py` 95%) comparten el *mismo* hueco — su `initialize()` DB-setup
(`create_async_engine`+`async_sessionmaker`+`engine.begin().run_sync(create_all)`), `close()` y el
guard de sesión — cerrable con **una sola técnica de mock** sin Postgres real. Un commit de tests +
un ratchet de gate + log, verify-verde, reversible. Nada arrancado.

- **Hecho:**
  - `test(cov)`: +6 tests. En `tests/test_user_store_codex.py` (sección `initialize/close/_session
    guard`): `initialize` con `create_async_engine`/`async_sessionmaker` monkeypatched a fakes
    (engine con `begin()` async-CM que yield-ea un `conn` con `run_sync` `AsyncMock`) → asserta
    `store.engine`/`store.async_session` seteados, url propagada y `run_sync` llamado con
    `Base.metadata.create_all`; `close()` con engine (`dispose` awaited) y sin engine (no-op);
    guard `_session()` sin inicializar → `RuntimeError`. En `tests/test_prompt_store_codex.py`
    (`TestInitialize`): mismo happy-path + rama `except`→re-raise (`create_async_engine`
    `side_effect=RuntimeError`). Módulos: `user_store.py` **88%→100%** (64 stmts), `prompt_store.py`
    **95%→100%** (197 stmts).
  - `chore(cov)`: ratchet gate `make cov` **60%→61%** (medido **61.87%**, margen ~0.87 pt; suite
    determinista sin red/DB). Actualizado comentario+nota del target en `Makefile` y
    cabecera+histórico+filas de módulos (`prompt_*`, nueva `user_store`) de `docs/COVERAGE_ROADMAP.md`.
  - `docs(protocolo)`: `DAILY_MICELIA_PLANNING.md` §Definition of done — regla "IMPLEMENTADO" +
    línea de estado por entrada (petición de Jessicache).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**784 pass** + 2 skip; incluye sdk/python/tests/) · cov ✓
  (**61.87%** ≥ gate 61%, era 61.62%/gate 60). +0.25 pts. No se arrancó nada (ni gateway ni infra);
  sin procesos residuales.
  Nota: Pyright (IDE) marca args sin uso en los fakes (`*a/**k`, `**_kwargs`) — **no afecta al gate**
  (`make typecheck` = `mypy app/`, no toca `tests/`; ruff E/F/I/N/W no audita args sin uso). Patrón
  heredado de tests `_codex` previos.

- **DECISIÓN PENDIENTE (Jessicache):**
  (1) **bug bcrypt del funnel** — **DESBLOQUEADA hoy**: aprobado fijar `bcrypt<5` (`4.0.1`) + `uv
  lock`. Se ejecuta en Ciclo 15 (Opción A), no en este ciclo (que era la Opción B segura).
  (2) **hosting + DNS + TLS de `*.idmmortality.com`** (Hito 3 del deploy) — sigue siendo decisión
  solo de Jessicache; preparable por la tarea, no ejecutable (guardarraíl: sin push/secretos/infra).

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand). Gaps de
  cobertura restantes: `osascript.py` (24%, macOS-specific, no portable a CI Linux), `security.py`
  (rate limiter saltado en E2E), APIs `v1/prompts.py`/`v1/ai.py`. El ratchet mypy hacia `strict`
  (`disallow_untyped_defs`) sigue vivo.

- **Mañana (Ciclo 15 = Opción A, APROBADA):** desbloquear el funnel register/login →
  (1) fix bcrypt: fijar `bcrypt==4.0.1` en `pyproject.toml` + `uv lock` + confirmar que
  `pwd_context.hash()` deja de dar 500 en runtime; (2) test de integración real
  `POST /auth/register`→`POST /auth/login`; (3) frontend `register/page.tsx` (clon de
  `login/page.tsx`) + wire login↔register + `make frontend-lint` (QA humano posterior).
  Estimación a publicar en idmmortality.com: Hito 1 (funnel local) ~1 semana de ciclos, Hito 2
  (contenedor podman, ya instalado) ~1-2 semanas, Hito 3 (deploy real) ~3-5 semanas dominado por
  cuándo Jessicache decida hosting+DNS.

- **Estado:** **IMPLEMENTADO ✅** (Opción B ejecutada + `make verify` verde; 3 commits atómicos).

---

## 2026-07-11 — Ciclo 13 (workflow_engine 81→100% · cobertura 61.05→61.62% · gate 59→60)

**Contexto:** Ciclo 12 dejó `make verify` 100% verde (768 pass, cov 61.05%, gate 59%) con las
dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**: (1) bug
bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación), (2) frontend
`/register` (feature nueva + QA humano, no verificable por `make verify`). Con la prioridad #1
(rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la tarea de máximo valor
autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)" explícito de Ciclo 12.
`workflow_engine.py` (206 stmts, 81%, 40 líneas sin cubrir) era el mayor gap **limpio**
restante: el motor multi-agente que recorre el grafo de workflows, con **todos los
colaboradores constructor-injected** (frangels orchestrator, prompt_store, entire_service) →
100% aislable con `AsyncMock` + workflows custom, sin red/DB/subprocesos. Ya tenía andamiaje
(`test_workflow_engine_codex.py`, 279 líneas). Un commit de test + un ratchet de gate + log,
verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`b49bb66`): +10 tests en `tests/test_workflow_engine_codex.py` (20→30) para
    las 40 líneas restantes. Ramas del grafo con workflows a medida
    (`WorkflowDefinition`/`WorkflowStep` inyectados vía `monkeypatch.setitem(WORKFLOWS, ...)`,
    ya que el engine resuelve por `WORKFLOWS.get(...)`): **agente desconocido** (step con
    `agent` fuera de `AGENT_DEFINITIONS` → `status=failed` + `"error": "Unknown agent: ..."`,
    sin llamar a `chat`, líneas 115-125), **`next_on_success` a acción inexistente** (`nope` →
    `_find_step_index` None → failed, 219-224), **budget de retries agotado** (step que se
    reapunta a sí mismo con `max_retries=0` → `next_index<=step_index` con `retries<=0` → break
    tras 1 ejecución, 229-233), **camino de fallo** (`success=False` + `next_on_failure` + 1
    retry → reintenta por la rama de fallo y completa, 240-246). Rama **critic** (203) vía
    `full_pipeline` happy path (dos variantes: `requires_patch:false` y `severity:high`, ambas
    enrutan a patcher). **`except` tragados** de `checkpoint` (191-192) y `end_session`
    (259-260): `entire_service` `AsyncMock` con `side_effect=RuntimeError` → el run igualmente
    completa. **Trimming de `_runs`** (`_max_stored_runs=1`, 2 runs → conserva el más reciente,
    289). **`_build_messages` por acción** (357-445): llamadas directas por `critique`, `patch`,
    `classify`, `detect_pattern`, `detect_tool_need`, `generate_skill`, `generate_mcp_spec` y el
    `else` (acción desconocida → prompt crudo), con aserciones sobre marcadores del mensaje
    `user` e interpolación de `context`. Módulo: **81% → 100%** (206 stmts, 0 sin cubrir).
  - `chore(cov)` (`d3161e7`): ratchet gate `make cov` **59% → 60%** (medido 61.62%, margen
    ~1.6 pt; suite determinista). Actualizado comentario+nota del target en `Makefile` y
    cabecera+histórico+tabla de módulos de `docs/COVERAGE_ROADMAP.md` (61.05→61.62%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**778 pass** + 2 skip; incluye sdk/python/tests/) · cov ✓
  (**61.62%** ≥ gate 60%, era 61.05%/gate 59). +0.57 pts. No se arrancó nada (ni gateway ni
  infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature nueva +
  QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Gaps de cobertura restantes, cada vez menos "limpios": `osascript.py` (24%, 318 stmts,
  macOS-specific — poco portable a CI Linux), `user_store.py` (88%, 8 líneas), `prompt_store.py`
  (95%, solo `initialize` DB-setup). El ratchet de mypy hacia `strict=true`
  (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` + `uv lock`) +
  test de integración real register/login. (b) cobertura: cerrar `user_store.py` (88→100%, 8
  líneas) — es ahora el mayor gap **limpio** restante de superficie pequeña; alternativa
  `prompt_store.py` (95→100%, solo `initialize`, requiere mock de DB-setup). (c) arrancar el
  ratchet mypy activando `disallow_untyped_defs` en `app/services/frangels/` (ya al ~99% de
  cobertura).

---

## 2026-07-11 — Ciclo 12 (entire_session 0→100% · cobertura 59.90→61.05% · gate 57→59)

**Contexto:** Ciclo 11 dejó `make verify` 100% verde (740 pass, cov 59.90%, gate 57%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 11. `entire_session.py` (79 stmts, 0%) era el mayor gap **limpio**
restante: el wrapper del CLI `entire` (trazabilidad de sesiones de agente), con **dos
fronteras externas bien acotadas** — `shutil.which("entire")` (detección de binario) y
`asyncio.create_subprocess_exec` (dentro de `_run_entire`) → 100% aislable sin red/DB/
subprocesos reales. Los otros gaps son peores candidatos: `osascript.py` (24%, macOS-specific,
poco portable a CI Linux), `workflow_engine.py` (81%, solo ~40 líneas), `user_store.py` (88%,
8 líneas). Un commit de test + un ratchet de gate + log, verify-verde, reversible. No se tocó
ninguna DECISIÓN PENDIENTE ni infra; nada arrancado.

- **Hecho:**
  - `test(cov)`: `tests/test_entire_session_codex.py` (28 tests) para `EntireSessionService`.
    Aislamiento: fixture autouse resetea el singleton del módulo (`es._entire_service = None`)
    para independencia de orden; helper `_svc(available=...)` fuerza el cache
    `_entire_available` sin llamar a `shutil.which` (o se parchea `es.shutil.which` para
    ejercitar la rama de detección real); `_FakeProc` con `communicate` `AsyncMock`
    `(stdout, stderr)` y `returncode` scriptables + `_patch_subprocess` que sustituye
    `es.asyncio.create_subprocess_exec` por una factory que captura el argv (o lanza), de modo
    que `_run_entire` corre happy/error sin spawnear procesos. Cubre: `is_available`
    (detecta presente/ausente + cache tras la 1ª sonda), `start_session` (unavailable→solo
    in-memory sin spawnear / available happy→setea `entire_session_id` desde stdout.strip +
    argv `idm-<prompt[:8]>` / `_run_entire` lanza→`except` tragado, sesión igual creada /
    metadata custom preservada / `_trim_sessions` con cap bajado a 2), `checkpoint`
    (session_id inexistente→no-op / sin `entire_session_id`→solo append / con id+available→
    llama entire con `--message agent:action` / fallo→tragado, append igual / trunca
    `output_summary[:500]` / None), `end_session` (inexistente→no-op / happy sin id / status
    default `completed` / con id→llama `session end` / fallo→tragado), getters (`get_sessions`
    orden desc + limit/offset, `get_session` present/absent, `get_sessions_for_prompt` filtra
    + ordena, `get_status` cuenta active/total + `entire_available`), `_run_entire` (rc 0→
    stdout / rc≠0→`RuntimeError` con stderr), `_trim_sessions` (evicta las más antiguas por
    `started_at` / bajo cap→no-op) y el singleton `get_entire_service`. Módulo: **0% → 100%**
    (79 stmts, 0 sin cubrir).
  - `chore(cov)`: ratchet gate `make cov` **57% → 59%** (medido 61.05%, margen ~2.1 pt;
    suite determinista sin red/DB/subprocesos reales). Actualizado comentario+nota del target
    en `Makefile` y cabecera+histórico+tabla de módulos de `docs/COVERAGE_ROADMAP.md`
    (59.90→61.05%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**768 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**61.05%** ≥ gate 59%, era 59.90%/gate 57). +1.15 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.
  Nota: Pyright (IDE) marca args sin uso en fakes y un subscript de `get_session` (Optional)
  en el test — **no afecta al gate**: `make typecheck` es `mypy app/` (no toca `tests/`) y
  `make lint` (ruff E/F/I/N/W) no audita args sin uso. Patrón heredado de tests `_codex`
  previos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, cada vez menos "limpios": `osascript.py`
  (24%, 318 stmts, macOS-specific — poco portable a CI Linux), `workflow_engine.py`
  (81%, ~40 líneas sin cubrir, ya con andamiaje de tests existente), `user_store.py` (88%,
  8 líneas), `prompt_store.py` (95%, solo `initialize` DB-setup). El ratchet de mypy hacia
  `strict=true` (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: cerrar los ~40 huecos
  de `workflow_engine.py` (81%→~100%) — es ahora el mayor gap **limpio** restante y ya tiene
  andamiaje de tests (`test_workflow_engine_codex.py`); alternativa menor `user_store.py`
  (88%→100%, 8 líneas). (c) arrancar el ratchet mypy activando `disallow_untyped_defs` en
  `app/services/frangels/` (ya al ~99% de cobertura).

---

## 2026-07-11 — Ciclo 11 (mcp_generator 0→100% · cobertura 57.31→59.90% · gate 55→57)

**Contexto:** Ciclo 10 dejó `make verify` 100% verde (701 pass, cov 57.31%, gate 55%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 10. `mcp_generator.py` (179 stmts, 0%) era el mayor gap **limpio**
restante: el generador de servidores MCP (Python/FastMCP + TypeScript/@modelcontextprotocol),
con dos fronteras externas bien acotadas — file I/O (`output_dir` relativo a cwd) y
subprocess/signals (`Popen`/`os.killpg`) → 100% aislable sin red/DB. Un commit de test + un
ratchet de gate + log, verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni
infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`a5b5e70`): `tests/test_mcp_generator_codex.py` (39 tests) para
    `MCPGenerator`. Aislamiento: `_gen(tmp_path, monkeypatch)` hace `monkeypatch.chdir(tmp_path)`
    **antes** de construir, así el `mkdir` de `__init__` (`data/mcp-servers` relativo a cwd) y
    todas las escrituras caen en el sandbox de pytest (file I/O real, aserciones con
    `Path.read_text()`); `_FakeProc` sustituye a `subprocess.Popen` con `poll`/`wait`
    scriptables (lista de retornos + `wait` que lanza `TimeoutExpired` una vez); `_patch_popen`
    reemplaza `mg.subprocess.Popen` por una factory que captura `cmd`/`kwargs` (o lanza una
    excepción); `_patch_signals` parchea `os.getpgid`/`os.killpg` para registrar señales sin
    tocar procesos reales. Cubre: `generate` python (crea server.py/pyproject/README/metadata,
    type-map string→str/integer→int/boolean→bool, default con `repr`, tipo desconocido→str,
    claves de tool ausentes→`unnamed_tool`/`arg`/`No description`) y typescript (server.ts/
    package.json, zod-map + `.describe`, `json.loads` del package), `generate` unsupported→
    `ValueError`, metadata.json completo; `list_servers` (dir ausente→[] / sin servers→[] /
    lee metadata+running / ignora no-dirs / dir sin metadata→skip / metadata ilegible→
    fallback+warning); `get_server` (not-found→`FileNotFoundError` / metadata+source+files /
    running=True / lee server.ts en ts / sin metadata→dict mínimo); `delete_server` (ok /
    not-found / corriendo→`RuntimeError`); `start_server` (spawn+track python cmd / ts→npx /
    not-found / ya corriendo (poll None)→error / proceso muerto (poll 0)→cleanup+restart /
    sin metadata→python / `Popen` lanza→`RuntimeError` + no queda en `_running_processes`);
    `stop_server` (not-running→error / ya muerto (poll≠None)→`already_stopped` / SIGTERM
    grácil / `TimeoutExpired`→escalada SIGKILL con 2 waits / `ProcessLookupError` tragado);
    y el singleton `get_mcp_generator`. Módulo: **0% → 100%** (179 stmts, 0 sin cubrir).
  - `chore(cov)` (`57e5713`): ratchet gate `make cov` **55% → 57%** (medido 59.90%, margen
    ~2.9 pt; suite determinista sin red/DB/subprocesos reales). Actualizado comentario+nota del
    target en `Makefile` y cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (57.31→59.90%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**740 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**59.90%** ≥ gate 57%, era 57.31%/gate 55). +2.59 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.
  Nota: Pyright (IDE) marca `_FakeProc` no asignable a `Popen` en el test — **no afecta al
  gate**: `make typecheck` es `mypy app/` (no toca `tests/`) y `make lint` (ruff E/F/I/N/W) no
  audita args sin uso. Patrón heredado de tests previos que asignan `MagicMock` (tipo `Any`).

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, todos aún limpios/mockeables: `entire_session.py`
  (0%, 79 stmts), `osascript.py` (24%, 318 stmts, macOS-specific — poco portable a CI Linux),
  `workflow_engine.py` (81%, 40 líneas sin cubrir). El ratchet de mypy hacia `strict=true`
  (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `entire_session.py`
  (0%, 79 stmts) — es ahora el mayor gap **limpio** restante; alternativa cerrar los 40
  huecos de `workflow_engine.py` (81%→~100%, ya con andamiaje de tests existente). (c) arrancar
  el ratchet mypy activando `disallow_untyped_defs` en `app/services/frangels/` (ya al ~99%).

---

## 2026-07-11 — Ciclo 10 (markdown_sync 0→100% · cobertura 53.31→57.31% · gate 51→55)

**Contexto:** Ciclo 9 dejó `make verify` 100% verde (668 pass, cov 53.31%, gate 51%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 9. `markdown_sync.py` (276 stmts, 0%) era el mayor gap **limpio**
restante: el sync bidireccional DB↔Markdown del orquestador, con una **única frontera
externa** (`PromptStore`) + file I/O → 100% aislable sin red/DB (los dirs son atributos
string públicos, redirigibles a `tmp_path`; `utcnow_naive` parcheable). Un commit de test +
un ratchet de gate + log, verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni
infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`0296e69`): `tests/test_markdown_sync_codex.py` (33 tests) para
    `MarkdownSyncService`. Aislamiento: `_store(**overrides)` arma un `MagicMock` con los 6
    métodos usados como `AsyncMock` (`list_all_lists`, `get_captured_prompts`,
    `get_archived_prompts`→`{"prompts":[...]}`, `get_list`, `update_list`, `create_list`);
    `_svc(tmp_path, store)` construye el servicio y **redirige** `lists_dir/inbox_dir/
    archive_dir` a subdirs de `tmp_path` (file I/O real contra el sandbox, aserciones con
    `Path.read_text()`); `utcnow_naive` parcheado a `datetime(2026,7,11,9,30)` para rutas
    `YYYY/MM/YYYY-MM-DD` deterministas. `_run_loop` se ejercita **directo** (no vía la task
    de fondo) parcheando `asyncio.sleep` para cortar el bucle. Cubre: `start`
    (crea dirs + task; no re-arranca si task viva), `stop` (cancel + swallow; sin task
    no-op), `_run_loop` (happy / `CancelledError`→break / `Exception`→log+sleep),
    `sync_lists_to_md` (escribe nuevo con frontmatter / skip sin slug / skip si file existe→MD
    gana), `sync_inbox_to_md` (vacío / ninguno de hoy / escribe hoy con formato time+tags+
    priority, con y sin `T` y sin tags), `sync_archives_to_md` (vacío / agrupa por `YYYY-MM`
    con fallback `archived_at`/`created_at` / bucket `unknown`→skip / `year_month`
    malformado→skip), `sync_md_to_lists` (dir inexistente→0 / ignora no-`.md` y vacíos /
    crea nuevo con slug+name desde filename / actualiza existente con campos opcionales +
    `is_active` / read-error→warning+continue), `full_sync` (agrega los 4 contadores +
    `sync_count`+`last_sync`; cada sub-sync que lanza→capturada en `errors` sin abortar),
    `_parse_frontmatter` (sin `---` / sin 2º marcador / bool yes-no-true-false / listas / quotes
    / comentarios y líneas sin `:`), `_build_frontmatter` (bool/list/None/str + roundtrip),
    `_parse_bool`, `_ensure_dirs`, `_write_file`/`_read_file` (crea dirs intermedios),
    `get_status`, `get_today_inbox_md` (presente/ausente). Módulo: **0% → 100%** (276 stmts,
    0 sin cubrir).
  - `chore(cov)` (`c22d7ec`): ratchet gate `make cov` **51% → 55%** (medido 57.31%, margen
    ~2.3 pt; suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target en
    `Makefile` y cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (53.31→57.31%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**701 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**57.31%** ≥ gate 55%, era 53.31%/gate 51). +4.00 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, todos aún limpios/mockeables: `mcp_generator.py`
  (0%, 554 líneas, codegen — puro string/template, sin fronteras externas), `entire_session.py`
  (0%, 164 líneas), `osascript.py` (24%, 318 stmts, macOS-specific — poco portable a CI
  Linux). El ratchet de mypy hacia `strict=true` (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `mcp_generator.py`
  (0%, 554 líneas) — es el mayor gap **limpio** restante (generación de código, puro
  string/template sin red/DB, 100% determinista); alternativa más pequeña `entire_session.py`
  (0%, 164 líneas). (c) arrancar el ratchet mypy activando `disallow_untyped_defs` en
  `app/services/frangels/` (ya al ~99% de cobertura).

---

## 2026-07-11 — Ciclo 9 (event_bus 0→100% · cobertura 51.93→53.31% · gate 49→51)

**Contexto:** Ciclo 8 dejó `make verify` 100% verde (644 pass, cov 51.93%, gate 49%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 8. `event_bus.py` (96 stmts, 0%) era el mayor gap **limpio** restante:
el bus Redis Pub/Sub del orquestador, con una única frontera externa (`redis.asyncio`) →
100% aislable sin red/DB. Un commit de test + un ratchet de gate + log, verify-verde,
reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`6b3908c`): `tests/test_event_bus_codex.py` (24 tests) para `EventBus`.
    Aislamiento: helper `_make_client()` arma un cliente `MagicMock` con `AsyncMock`
    ping/publish/close y `pubsub()` → PubSub mock (subscribe/unsubscribe/close `AsyncMock`,
    `listen` scriptable); `_connected_bus()` parchea `event_bus.redis.from_url` y corre
    `connect`. `_listen` se ejercita **directo** (no vía la task de fondo) apuntando
    `pubsub.listen()` a un async generator (`_aiter`/`_araise`) de mensajes escritos, así
    el `async for` termina determinista sin bucle real. Cubre: `connect` (happy + ping
    falla→not connected), `disconnect` (con task viva cancel+CancelledError tragada +
    pubsub/redis close; y todo-None no-op), `publish` (desconectado→descarta / happy con
    metadata timestamp+channel+data / except tragado), `subscribe` (canal nuevo suscribe +
    arranca listener / canal existente añade sin re-suscribir / task viva no se re-arranca),
    `unsubscribe` (callback específico mantiene otros / último→del+unsubscribe / todos
    (`callback=None`) / canal desconocido no-op), `_listen` (JSON válido→callbacks async y
    sync vía `iscoroutinefunction`, JSON inválido→`{"raw":...}`, tipo != message ignorado,
    callback que lanza→logueado y sigue, `CancelledError`→salida limpia, excepción
    genérica→logueada), los 4 publishers de conveniencia (health/education/security/system
    delegan en `publish` con `CHANNELS[...]` y mezclan `{"type",**data}`), y forma de
    `CHANNELS`. Módulo: **0% → 100%** (96 stmts, 0 sin cubrir).
  - `chore(cov)` (`b5ada8b`): ratchet gate `make cov` **49% → 51%** (medido 53.31%, margen
    ~2.3 pt; suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target
    en `Makefile` y cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (51.93→53.31%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**668 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**53.31%** ≥ gate 51%, era 51.93%/gate 49). +1.38 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, todos aún limpios/mockeables: `markdown_sync.py`
  (0%, 276 stmts, file I/O + parsing), `mcp_generator.py` (0%, 179 stmts, codegen),
  `entire_session.py` (0%, 79 stmts), `osascript.py` (24%, 318 stmts, macOS-specific —
  poco portable a CI Linux). El ratchet de mypy hacia `strict=true`
  (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `markdown_sync.py`
  (0%, 276 stmts) — es el mayor gap **limpio** restante (file I/O + parsing de markdown,
  aislable con `tmp_path` + mocks del store, patrón ya probado en google_calendar). (c)
  arrancar el ratchet mypy activando `disallow_untyped_defs` en `app/services/frangels/`
  (ya al ~99% de cobertura).

---

## 2026-07-10 — Ciclo 8 (google_calendar 13→98% · cobertura 48.99→51.93% · gate 47→49)

**Contexto:** Ciclo 7 dejó `make verify` 100% verde (599 pass, cov 48.99%, gate 47%)
con las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha y ambos unblocks pendientes, la tarea de
máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 7. `google_calendar.py` (240 stmts, 13%) era el mayor gap restante:
frontera externa doble pero 100% aislable — las libs de Google (`Flow`/`Credentials`/
`build`) importadas bajo `try/except`+flag, `TOKEN_PATH` (file I/O) y `PromptStore`
(import lazy en los sync). Un commit de test + un ratchet de gate + log, verify-verde,
reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra.

- **Hecho:**
  - `test(cov)`: `tests/test_google_calendar_codex.py` (45 tests) para
    `GoogleCalendarService`. Aislamiento: fixture autouse redirige `gc.TOKEN_PATH` a
    `tmp_path` y resetea el singleton `gc._google_calendar` (order-independence); helper
    `_svc(...)` arma un `MagicMock` con las cadenas `calendarList()/events().list()/
    insert().execute` preconfiguradas (`asyncio.to_thread(fn)` ejecuta el mock y devuelve
    su valor); `_FakeCreds` para los happy-paths de auth (con sentinel `_UNSET` para poder
    testear el fallback `scopes → SCOPES`); `_patched_store()` parchea
    `app.services.prompt_store.PromptStore` con métodos `AsyncMock`. Cubre: `authenticate`
    (guard libs-off/creds-missing/happy/except), `handle_callback` (libs-off/happy con
    escritura de token+build/expiry None y set/except), `is_connected` (creds cacheadas/
    sin file/file→_load/_load raises→False), `_load_credentials` (libs-off/no-file/happy/
    rama refresh — google-auth SÍ está instalado en el venv, `Request` real/error→reset),
    `_save_credentials` (no-creds/happy/write-error), `_ensure_service`, `list_calendars`,
    `get_events` (ventana default/explícita, `dateTime` vs `date`, except), `create_event`
    (validaciones/happy/except), `sync_prompts_from_calendar` (crea/skip-sin-tag/
    skip-ya-synced/content-vacío→description/parse scheduled_at ok+malo/except+close),
    `sync_results_to_calendar` (crea+marca/skip sin output+ya-synced+sin completed_at/
    completed_at malo→now/except+close), `disconnect` (con/sin file/unlink-error),
    `get_status`, singleton. Módulo: **13% → 98%** (240 stmts; única franja sin cubrir:
    24-28, el `except ImportError` de import de las libs de Google — inalcanzable con las
    libs instaladas, sin valor mockear).
  - `chore(cov)`: ratchet gate `make cov` **47% → 49%** (medido 51.93%, margen ~2.9 pt;
    suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target en
    `Makefile` y cabecera+histórico+fila `google_calendar` de `docs/COVERAGE_ROADMAP.md`
    (48.99→51.93%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**644 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**51.93%** ≥ gate 49%, era 48.99%/gate 47). +2.94 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7
  rebrand). Mayores gaps de cobertura restantes: `osascript.py` (24%, 318 stmts,
  macOS-specific — poco portable a CI Linux), `event_bus.py` (0%, 96 stmts, requiere
  mock de Redis pub/sub), `markdown_sync.py` / `mcp_generator.py` (0%, file I/O + gen de
  código). El ratchet de mypy hacia `strict=true` (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `event_bus.py`
  (0%, 96 stmts) con mock de Redis (`redis.asyncio` stubbeado) — salto limpio y de valor
  operativo (es el bus de eventos del orquestador). (c) arrancar el ratchet mypy activando
  `disallow_untyped_defs` en `app/services/frangels/` (ya al ~99% de cobertura).

---

## 2026-07-10 — Ciclo 7 (frangels/orchestrator 17→100% · cobertura 45.51→48.99% · gate 44→47)

**Contexto:** Ciclo 6 dejó `make verify` 100% verde (537 pass en tests/, cov 45.51%,
hito v0.2=45% alcanzado en medición real) con dos DECISIONES PENDIENTES para Jessicache,
**ambas bloqueadas para trabajo autónomo**: (1) bug bcrypt del funnel (tocar `uv.lock` =
riesgo de arrastre, requiere aprobación), (2) frontend `/register` (feature nueva + QA
humano, no verificable por `make verify`). Con la prioridad #1 (rojo→verde) satisfecha y
ambos unblocks pendientes, la tarea de máximo valor autónomo-segura es la prioridad #3
(cobertura) — y era el "Mañana (b)" explícito de Ciclo 6. `frangels/orchestrator.py`
(289 stmts, 17%) era el mayor gap restante en frangels/ y uno de los dos mayores del
proyecto; frontera externa **única** (`httpx.AsyncClient`), colaboradores
(`provider_store`, `quota_manager`) inyectables → 100% mockeable sin red/DB. Se descartó
`google_calendar.py` (13%) por depender de las librerías cliente de Google (frontera más
frágil). Un commit de test + un ratchet de gate, verify-verde, reversible. No se tocó
ninguna DECISIÓN PENDIENTE ni infra.

- **Hecho:**
  - `test(cov)`: `tests/test_frangels_orchestrator_codex.py` (62 tests) para
    `FrangelsOrchestrator`. Aislamiento: `_make_orch()` sustituye `provider_store` y
    `quota_manager` por `MagicMock`; `_get_client` parcheado con `AsyncMock` que devuelve
    un cliente falso cuyos `get/post/head` son `AsyncMock` → `_FakeResponse(status_code,
    json())`. `select_angel` (núcleo de lógica pura) se ejercita contra un `ANGEL_REGISTRY`
    reducido y determinista (`_patch_registry`) para aseverar filtros
    categoría/key/cuota/privacidad/vision/tools/min_context, orden tier→salud→latencia,
    `reasoning` y `fallbacks[1:4]` sin depender del registro real. Rutas HTTP
    (`test_provider` + `_test_*`, `chat` + `_chat_*`, paid providers openai/anthropic con
    split de system-message y cálculo de coste, singleton) con los ids reales
    (groq/gemini/deepseek/cohere/mistral/openrouter + genérico huggingface). Fixture
    autouse resetea el singleton del módulo y restaura `angel.health` del registro real
    (que `test_provider` muta) → tests order-independent. Módulo: **17% → 100%**
    (289 stmts, 0 sin cubrir).
  - `chore(cov)`: ratchet gate `make cov` **44% → 47%** (medido 48.99%, margen ~2 pt;
    suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target en
    `Makefile` y cabecera+histórico+fila `frangels/` de `docs/COVERAGE_ROADMAP.md`
    (45.51→48.99%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**599 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**48.99%** ≥ gate 47%, era 45.51%/gate 44). +3.48 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7
  rebrand). Mayores gaps de cobertura restantes: `google_calendar.py` (13%, 240 stmts),
  `osascript.py` (24%, macOS-specific), `frangels/orchestrator` ya cerrado. El ratchet de
  mypy hacia `strict=true` sigue vivo (mejora, no bloquea).

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura del mayor gap
  restante: `google_calendar.py` (13%) con mock de la Google API (googleapiclient /
  flujo OAuth stubbeado) — 208 stmts sin cubrir, el mayor salto disponible. (c) arrancar
  el ratchet mypy activando `disallow_untyped_defs` en un subpaquete pequeño (p.ej.
  `app/services/frangels/`, ya al ~99% de cobertura).

---

## 2026-07-10 — Ciclo 6 (prompt_store 63→95% · cobertura 44.60→45.51% · **hito v0.2 = 45% ALCANZADO en medición real** · gate 43→44)

**Contexto:** Ciclo 5 dejó `make verify` 100% verde (512 pass, cov 44.60%) con dos
DECISIONES PENDIENTES para Jessicache, **ambas bloqueadas para trabajo autónomo**: (1)
bug bcrypt del funnel (tocar `uv.lock` = cambio con riesgo de arrastre, requiere
aprobación), (2) frontend `/register` (feature nueva + QA humano, no verificable por
`make verify`). Con la prioridad #1 (rojo→verde) ya satisfecha y ambos unblocks
pendientes, la tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) —
además es el "Mañana" explícito de Ciclo 5: cerrar `app/services/prompt_store.py` (63%,
~72 stmts sin cubrir) para cruzar el hito v0.2 = 45.00% **en medición real** (Ciclo 5
lo alcanzó sólo en display, medido 44.60%). Reconocimiento confirmó el hueco: el
`test_prompt_store_codex.py` existente (714 líneas) cubría prompts CRUD/notes/list/stats/
lifecycle/serialización pero NO los métodos de prompt-lists, promoción ni inbox — todos
CRUD puro con el mismo patrón mock-session ya probado. Un solo commit de test,
verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra.

- **Hecho:**
  - `test(cov)` (`e564043`): +25 tests en `tests/test_prompt_store_codex.py` para los
    métodos sin cubrir de `prompt_store.py`, reutilizando helpers/fixtures existentes
    (`_make_prompt_model`, `_make_list_model` —antes sin uso—, `_mock_session_ctx`,
    `store`/`mock_session`). Clases nuevas: `TestScheduledPrompts` (get_scheduled_prompts),
    `TestPromptLists` (create/get/update/delete/list_all_lists + `_list_to_dict` con y sin
    `updated_at`), `TestPromote` (promote_to_list happy + ramas prompt/list ausentes;
    promote_to_skill happy + prompt ausente; promote_to_mcp — los promote encadenan
    llamadas internas stubbeadas con AsyncMock para aislar ramas), `TestApproveStaged`,
    `TestInboxQueries` (captured/staged/archived con forma `{prompts,total,limit,offset}`)
    y `TestClose` (dispose + rama engine=None). Módulo: **63% → 95%** (única franja sin
    cubrir: `initialize()` 39-59, setup real de engine DB — omitido por brittleness, no
    aporta valor con mocks).
  - `chore(cov)` (`56ec0b6`): ratchet gate `make cov` **43% → 44%** (medido 45.51%,
    margen 1.51 pt; suites deterministas sin red/DB/tiempo). Actualizado comentario+nota
    del target en `Makefile` y cabecera+histórico+fila `prompt_*` de
    `docs/COVERAGE_ROADMAP.md` (44.60→45.51%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ · typecheck ✓ (0 errores) · test ✓
  (**537 pass** + 2 skip; eran 512) · cov ✓ (**45.51%** ≥ gate 44%, era 44.60%/gate 43).
  +0.91 pts. **Hito v0.2 = 45% alcanzado en medición real** (no sólo display). No se
  arrancó nada (ni gateway ni infra); sin procesos residuales; árbol limpio (3 commits
  atómicos).

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login de usuario registrado darían 500 en runtime). Recomendación
  intacta: fijar `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin
  aprobación (cambio de lockfile). (2) **frontend del funnel** (`/register` inexistente en
  `micelia/frontend`). Feature nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** el ratchet de mypy hacia `strict=true` sigue vivo (mejora, no
  bloquea). Dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand). Mayor gap
  restante de cobertura: `frangels/orchestrator.py` (17%, 289 stmts) y
  `google_calendar.py` (13%, 240 stmts).

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login que ejercite `pwd_context` de
  verdad (cierra el funnel de punta a punta); (b) alternativa de cobertura de máximo gap:
  empezar `frangels/orchestrator.py` (17%) con mocks httpx de providers — es el mayor
  hueco restante en frangels/; o `google_calendar.py` con mock de la Google API. (c)
  arrancar el ratchet mypy activando `disallow_untyped_defs` en un subpaquete.

---

## 2026-07-10 — Ciclo 5 (funnel register→login testeado · auth.py 0→100% · cobertura 43.11→44.60% · gate 41→43)

**Contexto:** Ciclo 4 dejó `make verify` 100% verde con siguiente paso subir cobertura
hacia el hito v0.2 = 45%. La tarea reitera el objetivo #5 (funnel **register → login →
micelia**, subdominios de idmmortality.com, para la iteración inicial de marketing).
Reconocimiento encontró una convergencia fuerte entre prioridad #3 (cobertura) y ese
objetivo: el **backend del funnel está completo** (`POST /auth/register`, `/login`,
`/refresh`, `/me`, `/setup` en `app/api/v1/auth.py`; `UserModel`; `UserStore`) pero el
router del funnel tenía **cero tests de endpoint** — el `test_app` compartido en
`tests/conftest.py` ni siquiera monta `auth.router` ni fija `app.state.user_store`, y
`tests/test_auth.py` sólo cubre la auth por API-key de endpoints protegidos, no el
funnel. Testear ese router sube cobertura Y verifica el camino register→login del que
depende el marketing. Un solo commit de test, verify-verde, reversible. El hueco del
**frontend** (no hay página `/register`) queda como DECISIÓN PENDIENTE (fuera de alcance
autónomo seguro: feature nueva, QA humano, no verificable por `make verify`).

- **Hecho:**
  - `test(cov)`: `tests/test_auth_endpoints_codex.py` (17 tests) para el router funnel
    `app/api/v1/auth.py`. App mínima aislada que monta sólo `auth.router` e inyecta un
    `user_store` fake (AsyncMock); `httpx.AsyncClient` + `ASGITransport`. Cubre TODAS las
    ramas: register (201 auto-login, 409 duplicado, 503 sin store, 422 validadores
    email/password, normalización email), login (usuario registrado OK + `touch_last_login`,
    403 cuenta inactiva, fallback admin `.env`, 401 inválido, rama sin store), refresh
    (par válido, 401 tipo incorrecto, 401 JWTError), `/me` (parseo identidad con/sin `:`),
    `/setup` (403 ya configurado, 200 primera vez + mutación de settings). `jwt_auth`
    (jose) corre real; `audit_logger` no-op (event_store=None). Frontera cripto
    (`pwd_context.hash/verify`) stubbeada de forma determinista — obligatorio, ver
    DECISIÓN PENDIENTE bcrypt. Módulo: **0% → 100%** (91 statements, 0 sin cubrir).
  - `chore(cov)`: ratchet gate `make cov` **41% → 43%** (medido 44.60%, margen 1.60 pt;
    suites deterministas sin red/DB/tiempo). Actualizado el comentario+nota del target en
    `Makefile` y la cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (43.11→44.60%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ · typecheck ✓ (0 errores) · test ✓
  (**512 pass** + 2 skip; eran 495) · cov ✓ (**44.60%** ≥ gate 43%, era 43.11%/gate 41).
  +1.49 pts. Hito v0.2 = 45% alcanzado en display (medido 44.60%, redondea a 45%). No se
  arrancó nada (ni gateway ni infra); sin procesos residuales; árbol limpio (2 commits
  atómicos).

- **DECISIÓN PENDIENTE (Jessicache) — bug real del funnel (bcrypt):** el venv actual trae
  **bcrypt 5.0.0 con passlib 1.7.4**, incompatibles: `pwd_context.hash()/verify()` lanzan
  `ValueError: password cannot be longer than 72 bytes` en la primera llamada (la sonda
  `detect_wrap_bug` de passlib peta con bcrypt ≥5). Consecuencia: **`POST /auth/register` y
  el login de usuario registrado darían 500 en runtime** en este entorno — el funnel de
  registro está roto. Ningún test lo ejercía antes, por eso pasó inadvertido. No lo arreglo
  autónomamente (bajar dependencia = cambio de `uv.lock` con riesgo de arrastre, sin
  supervisión). Recomendación: fijar `bcrypt<5` (p.ej. `bcrypt==4.0.1`, compatible con
  passlib 1.7.4) o migrar a `bcrypt` directo. Los tests de este ciclo stubbean la frontera
  cripto para probar la lógica del endpoint con independencia de este bug.

- **DECISIÓN PENDIENTE (Jessicache) — frontend del funnel:** backend del funnel completo,
  pero el frontend Next.js (`micelia/frontend`) NO tiene página `/register` ni método
  `authApi.register` (`src/lib/api.ts`); el formulario de login usa **username** mientras el
  modelo indexa por **email** (elección de contrato UX); `/register` habría que añadirlo a
  `PUBLIC_PATHS` en `src/middleware.ts`. Es feature nueva, con QA humano y no verificable por
  `make verify` → no se construye autónomamente; se decide cuándo abordarla.

- **Bloqueado/pendiente:** viva aún el ratchet de mypy (rearmar flags relajados uno a uno
  hacia `strict=true`; no bloquea, es mejora). Dir legacy `vital-core/docs/` sigue en el
  árbol (DoD §7 rebrand). Cobertura a 0.40 pts del 45.00% literal.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` + `uv lock`)
  y añadir un test de integración real de register/login que ejercite `pwd_context` de
  verdad — cierra el funnel de punta a punta; (b) alternativa de cobertura: `prompt_store.py`
  (63%, ~72 stmts sin cubrir, patrón CRUD ya probado) para pasar el 45.00% literal, o empezar
  `frangels/orchestrator.py` (17%, 289 stmts) con mocks httpx.

---

## 2026-07-10 — Ciclo 4 (cobertura 39% → 43% · dos módulos puros a ~100% · gate 37→41)

**Contexto:** Ciclo 3 dejó `make verify` 100% verde y como siguiente paso subir
cobertura hacia el objetivo v0.2 = 45%. Al orientarme encontré un test SIN commitear
en el árbol (`tests/test_prompt_os_agents_codex.py`, 23 tests) que cubría justo el
pendiente `prompt_os_agents` del COVERAGE_ROADMAP para `agents/`. Se validó (pasa,
0%→98%) y se commiteó. Prioridad #1 (rojo→verde) ya satisfecha; la tarea de máximo
valor desbloqueada es la #3 (cobertura). Reconocimiento eligió el siguiente módulo
más puro sin cubrir: `frangels/provider_store.py` (33%, misma frontera JSON/tmp_path
que quota_manager ya testeado). No se tocó ninguna decisión pendiente ni infra.

- **Hecho:**
  - `test(cov)` (`0ecd270`): `tests/test_prompt_os_agents_codex.py` (23 tests) —
    valida y committea el test que estaba en el working tree para
    `app/services/agents/prompt_os_agents.py`. Cubre los 4 agentes de Prompt OS
    (ingest/taxonomy/archivist/builder) + `_extract_json`; única frontera =
    `FrangelsOrchestrator` inyectado como `AsyncMock`. Módulo: **0% → 98%**.
  - `test(cov)` (`5f7a8a8`): `tests/test_provider_store_codex.py` (30 tests) para
    `app/services/frangels/provider_store.py`. Frontera = fichero encriptado
    `providers.enc` bajo `tmp_path` con Fernet real (round-trip genuino, no mock de
    cripto). Cubre `ProviderCredential.__post_init__`, `_load` (missing/round-trip/
    corrupt), rama de excepción de `_save` (write_bytes → OSError tragado),
    get/get_api_key, set (create+update), delete/enable/disable/mark_used
    (present+absent), list_configured/get_all_status, export_to_env y sync_from_env
    (ANGEL_REGISTRY real: groq + kaggle con extra_key) y el singleton.
    Módulo: **33% → 100%**.
  - `chore(cov)` (`73f6a57`): ratchet gate `make cov` **37% → 41%** (medido 43.11%,
    ~2 pts de margen, mismo criterio que Ciclo 3). Actualizada la nota del target,
    la cabecera de COVERAGE_ROADMAP.md (29.37%→43.11%) y la tabla de módulos:
    `agents/` cubierto, `frangels/provider_store` hecho; queda `frangels/orchestrator`
    (17%) como pendiente.

- **Verify:** **`make verify` VERDE COMPLETO** — lint ✓ · typecheck ✓ (0 errores) ·
  test ✓ (**495 pass** + 2 skip; eran 465) · cov ✓ (**43.11%** ≥ gate 41%, era
  39.06%/gate 37). +4.05 pts de cobertura. Nada arrancado (ni gateway ni infra);
  sin procesos residuales; árbol limpio (3 commits atómicos).

- **DECISIÓN PENDIENTE:** ninguna nueva. Sigue viva la del ratchet mypy (re-endurecer
  flags relajados de uno en uno hacia `strict=true`) — no bloquea nada, es mejora.

- **Bloqueado/pendiente:** falta ~1.9 pts para el objetivo v0.2 = 45%. Siguiente mejor
  objetivo por pureza/tamaño: `frangels/orchestrator.py` (17%, 289 stmts — el mayor
  gap restante en frangels/, pero requiere mockear providers httpx) o
  `prompt_store.py` (63%, 72 stmts sin cubrir, patrón CRUD ya conocido). Directorio
  legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand, sin resolver).

- **Mañana:** cerrar el objetivo v0.2 = 45% con `prompt_store.py` (patrón CRUD ya
  probado en skills_manager/quota_manager, sube ~1 pt limpio) y/o empezar
  `frangels/orchestrator.py` con mocks de providers. Alternativa de igual valor:
  arrancar el ratchet mypy activando `disallow_untyped_defs` en un subpaquete.

---

## 2026-07-07 — Ciclo 3 (verify 100% VERDE por primera vez · 3 decisiones desbloqueadas)

**Contexto:** Jessicache autorizó las 3 DECISIONES PENDIENTES ("adelante los tres").
Con ellas desbloqueadas, la tarea del día es la prioridad #1 del protocolo: rojo→verde
en `make verify`, que nunca había estado verde (paraba en typecheck). Se aplicó el
baseline mypy pragmático (ya presente en pyproject) y se resolvieron los 128 errores
restantes; se cableó `calendar_name`; el commit raíz ya existía (aecb0ea/fd1ba50).

- **Hecho:**
  - `fix(types)`: 128 errores mypy resueltos en 23 ficheros (5 agentes paralelos,
    verificados centralmente). Patrones: `param: T = None`→`Optional[T]`; atributos de
    recurso None-init anotados a tipo concreto + `# type: ignore[assignment]` (contrato
    "initialize()/connect() primero"); var-annotated explícitas. **Bugs reales
    corregidos:** `google_calendar` llamaba `prompt_store.get_prompt_store()` (no existe)
    → usa `PromptStore()` con `initialize()/close()`; `frangels` leía
    `InferenceResult.cached` (no hay cache) → `False`; dicts inferidos demasiado
    estrechos (ai/routine/tunnel/service_registry/markdown_sync/prompt_agent/cli) →
    `dict[str, Any]`. Sin bare ignores.
  - `fix(osascript)`: `get_today_events` ahora honra `calendar_name` (antes recorría
    TODOS los calendarios ignorando el parámetro) — bug latente #2 resuelto.
  - `style(lint)`: 14 residuales ruff (SQLAlchemy `.isnot()/.is_()`, E402 noqa
    justificado en imports seccionales, E741, F841); `[tool.ruff]`→`[tool.ruff.lint]`.
  - `fix(deps)` + `test(cov)` (ya commiteados en ciclos previos de hoy): `coverage[toml]`
    para desbloquear `make cov`; `conftest` inserta `sdk/python` en sys.path (idm_sdk sin
    editable install); `tests/test_agents_crew.py` (agent_definitions/workflows/crew_manager).
  - `test(cov)`: `tests/test_service_registry_codex.py` (17 tests, httpx mockeado con
    AsyncMock — sin red ni infra) para `app/services/service_registry.py`. Cubre
    `_check_health` (200+versión, non-200, JSON inválido, timeout, connect-error, excepción
    genérica, servicio desconocido, recuperación), `_log_failure` (3 ramas de nivel),
    `check_service` (found/not-found), getters, `discover_services` (registro + hint) y
    `_continuous_monitoring` (un ciclo + cancelación, sleep monkeypatcheado). Módulo:
    **0% → 97%**.
  - `test(cov)`: `tests/test_context_assembler_codex.py` (21 tests) para
    `app/services/context_assembler.py` — deps inyectadas (prompt_store/skills_manager
    mockeadas), capas de filesystem con `tmp_path` + settings/cwd monkeypatcheados, capa
    temporal con datetime fijado (5 franjas horarias). Cubre `assemble` (todas/subset/vacío),
    las 5 capas y sus ramas de error, y el singleton. Módulo: **0% → 97%**.
  - `test(cov)`: `tests/test_prompt_agent_codex.py` (29 tests) para
    `app/services/prompt_agent.py` — helpers puros `_calculate_priority` (boosts de
    categoría/tags/programación/antigüedad + clamp) y `_find_group` (correlación/tags
    compartidos) probados directamente; pipeline async (`_classify_captured`,
    `_process_pending`, `_run_loop`, start/stop) con store/event_bus/taxonomy-runner
    mockeados y sleep monkeypatcheado. Módulo: **0% → 98%**.
  - `test(cov)`: `tests/test_scheduler_codex.py` (14 tests) para
    `app/services/scheduler.py` — `_process_scheduled` (sin store, vacío, mueve+publica,
    error de evento/store tragado), `_sync_calendar` (deshabilitado, conectado+sync, no
    conectado, error tragado; `get_google_calendar` parcheado), `get_status`, singleton,
    start/stop y `_run_loop` (ciclo + cancelación + rama de error). Módulo: **0% → 99%**.
  - `test(cov)`: `tests/test_prompt_executor_codex.py` (17 tests) para
    `app/services/prompt_executor.py` — `_reset_daily_counters`, `_call_model` (sin
    orchestrator, auto-upgrade paid en work/plan, excepción), `_review_output` (parse+clamp,
    número inválido, excepción), `_execute_prompt` (happy path + eventos, review en work,
    fallo de modelo, excepción→failed, errores de evento tragados), start/stop y `_run_loop`.
    Módulo: **0% → 100%**.
  - `chore(cov)`: gate de cobertura **28% → 37%** en `make cov` (ratchet; medido 39%).

- **Verify:** **`make verify` VERDE COMPLETO por primera vez** — lint ✓ · typecheck ✓
  (66 ficheros, 0 errores; eran 671) · test ✓ (413 pass + 20 SDK, 2 skip) · cov ✓
  (**39.06%** ≥ gate 37%, era 29.82%/gate 28). Nada arrancado (ni gateway ni infra); sin
  procesos residuales.

- **DECISIÓN PENDIENTE:** ninguna nueva. Las 3 de Ciclo 1 quedan **RESUELTAS**
  (autorizadas por Jessicache). Ratchet mypy: re-endurecer los flags relajados de uno en
  uno (`disallow_untyped_defs` → `disallow_untyped_calls` → `disallow_any_generics` → …)
  hacia `strict=true`.
- **Pendiente menor:** `app/models/user.py`, `app/services/user_store.py`,
  `tests/test_user_store_codex.py` (feature UserStore en curso de Jessicache) quedan SIN
  commitear en este ciclo (no son trabajo de la tarea diaria). Directorio legacy
  `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
- **Mañana:** arrancar el ratchet mypy (activar `disallow_untyped_defs` en un subpaquete
  y anotarlo) o subir cobertura hacia el objetivo v0.2 = 45%.

---

## 2026-07-07 — Ciclo 2 (cobertura +4.1 pts con módulos puros)

**Contexto:** las prioridades #1 (rojo→verde en verify) y #2 (roadmap) siguen
bloqueadas por decisiones humanas — typecheck mypy `strict=true` (671 errores) es
DECISIÓN PENDIENTE #1, y el commit raíz es DECISIÓN PENDIENTE #3. Con ellas
bloqueadas, la tarea de máximo valor **desbloqueada** es la prioridad #3: subir
cobertura (`docs/COVERAGE_ROADMAP.md`, objetivo v0.2 = 45%). Segura, reversible, no
toca ninguna decisión pendiente. Reconocimiento (Explore) eligió los dos módulos
sin cubrir más grandes y más puros (deps inyectadas → mockeables sin infra).

- **Hecho** (working tree, sin commitear — ver DECISIÓN PENDIENTE #3):
  - `test(cov)`: nuevo `tests/test_workflow_engine_codex.py` (24 tests) para
    `app/services/agents/workflow_engine.py`. Cubre helpers puros (`_reviewer_passed`,
    `_critic_requires_patch`, `_find_step_index`, `_update_context`, `get_runs/get_run`)
    y `execute_workflow` async con `AsyncMock` (workflow desconocido, prompt-not-found,
    happy path objeto+dict, retry reviewer-falla→pasa, excepción del orchestrator,
    ciclo de auditoría `entire_service` + tolerancia a fallo de `start_session`).
    Módulo: 0% → **80%**.
  - `test(cov)`: nuevo `tests/test_quota_manager_codex.py` (21 tests) para
    `app/services/frangels/quota_manager.py` usando `tmp_path` (única frontera = JSON)
    y el `ANGEL_REGISTRY` real. Cubre `record_usage`/`_check_reset` (reset diario/minuto
    + persistencia), `can_use` (4 ramas de límite + paid special-case + desconocido),
    `get_quota_status` (4 ramas + cap de % + is_exhausted + None), `get_usage_stats`
    (agregación hoy/mes robusta a fecha), `get_best_provider` (filtros capacidad +
    exclusión por cuota + orden por tier + fallback categoría), `_load/_save` round-trip
    y singleton cacheado. Módulo: 0% → **96%** (angels.py de paso a 97%).
  - `chore(cov)`: gate `make cov` `--cov-fail-under` 25 → **28** (Makefile:230) +
    textos del target actualizados. Roadmap actualizado: medición 29.37%, tabla de
    prioridades marca agents/ y frangels/ como cubiertos, historial de deltas.

- **Verify:** `make lint` VERDE · `make test` VERDE (305 pass + 20 SDK) ·
  `make cov` VERDE (**29.37%** ≥ 28%, era 25.28%) · `make typecheck` **ROJO**
  (mismos 671 errores; los tests NO se type-checkean → 0 errores nuevos, NO es
  regresión). `make verify` sigue parando en typecheck (etapa 2), igual que Ciclo 1.
  Cobertura +4.09 pts (25.28% → 29.37%). Nada arrancado (ni gateway ni infra);
  sin procesos residuales.

- **Bloqueado/pendiente:** verify 100% verde sigue bloqueado SOLO por typecheck
  (DECISIÓN PENDIENTE #1). Las 3 DECISIONES PENDIENTES de Ciclo 1 siguen abiertas
  sin cambios (no se tocaron hoy por guardarraíles).

- **Mañana:** seguir subiendo cobertura por el ranking del reconocimiento — siguiente
  mejor objetivo puro: `app/services/context_assembler.py` (0%, deps inyectables) o
  `app/services/skills_manager.py` (helpers puros + patrón CRUD de prompt_store).
  Recordar a Jessicache las 3 DECISIONES PENDIENTES: sin (1) no hay verify 100% verde;
  sin (3) la historia atómica no arranca (2 ciclos ya acumulados en working tree).

---

## 2026-07-07 — Ciclo 1 (rojo → verde en verify: 3 de 4 etapas)

**Contexto:** primera ejecución real del protocolo. Descubierto que `make verify`
**nunca había estado en verde** (repo en `master` con 0 commits) y estaba rojo en 3
de sus 4 etapas. Prioridad #1 del protocolo (rojo→verde) aplicada.

- **Hecho** (cambios en working tree — ver DECISIÓN PENDIENTE 3 sobre commits):
  - `fix(deps)`: añadido `coverage[toml]>=7.5` a extras `dev` en `pyproject.toml` +
    `uv lock`/`uv sync`. Además, la dep `coverage` estaba **rota** en el venv
    (dist-info presente, paquete ausente) → `uv pip install --reinstall coverage`.
    El `uv sync` reconcilió el venv a `uv.lock` (estaba drifteado: redis 5→7,
    starlette/uvicorn/sqlalchemy realineados, torch eliminado — ya declarado fuera).
  - `fix(cov)`: `make cov` tenía 2 bugs además de la dep: (a) `ModuleNotFoundError`
    de coverage; (b) corría `tests/ sdk/python/tests/` en una pasada y el import
    `idm_sdk` reventaba (la suite dependía de un editable install que `uv sync`
    quitó). Solución reproducible: `tests/conftest.py` inserta `sdk/python` en
    `sys.path`. Con eso la pasada combinada funciona (importlib evita la colisión).
  - `test`: nuevo `tests/test_agents_crew.py` (26 tests) para módulos puros sin infra
    (`agent_definitions`, `workflows`, `CrewManager` con engine mockeado). Sube
    cobertura 23.97% → **25.28%**, cruzando el gate de 25% con tests de valor real
    (opción (a) del plan, no bajar el gate).
  - `style(lint)`: `ruff --fix` (151 auto) + 14 residuales a mano. Destacado: los
    `!= None`/`== True` en `prompt_store.py`/`skills_manager.py` eran filtros
    SQLAlchemy → corregidos a `.isnot(None)`/`.is_(True)` (preservan el SQL, no
    `is`). E402 en `security.py` (imports seccionales) con `# noqa` justificado.
    Movida config ruff a `[tool.ruff.lint]` (quita warning de deprecación).
  - `chore(gitignore)`: endurecido antes de cualquier commit — `*token*.json`,
    `*credential*.json`, `secrets/`, `*.pid`, `data/frangels/`, `data/credentials/`.
    Auditoría `git status`: ningún fichero sensible quedaría stageado (`.env`,
    `data/frangels`, `google_token.json`, pids ya ignorados). Los `frangels/*.py`
    que matchean el grep son CÓDIGO fuente, no secretos → se trackean.

- **Verify:** `make lint` VERDE · `make test` VERDE (260 pass, 2 skip) ·
  `make cov` VERDE (**25.28%** ≥ 25%) · `make typecheck` **ROJO** (mypy `strict=true`,
  671 errores). `make verify` para en typecheck (2ª etapa). Progreso: 3/4 etapas
  rojas→verdes. Nada arrancado (ni gateway ni infra); sin procesos residuales.

- **Bloqueado/pendiente:** typecheck no puede ir a verde sin decidir política de tipado.

- **DECISIÓN PENDIENTE (Jessicache):**
  1. **mypy `strict=true` → 671 errores** (pyproject.toml:113). ~518 son completitud
     de anotaciones (no-untyped-def/type-arg/no-untyped-call), ~120 categorías de bug
     real. Recomendado: baseline pragmático + ratchet (aflojar completitud, mantener
     detección de bugs, arreglar los ~120, documentar re-endurecimiento). Alternativa:
     anotar incremental (semanas). Sin esto, verify no llega a 100% verde.
  2. **Bug latente encontrado**: `osascript.py` construía `calendar_filter` desde
     `calendar_name` pero NUNCA lo interpolaba en el AppleScript (el filtro por
     calendario no funcionaba). Eliminé el código muerto para el lint; **el filtrado
     por calendario sigue sin implementarse** — decidir si se cablea o se retira el
     parámetro `calendar_name` de la API.
  3. **Primer commit del repo (0 commits).** Los cambios de hoy están en el working
     tree SIN commitear: crear el commit raíz del orquestador (qué incluir: docs
     legales, dir legacy `vital-core/`, `.github/`, estrategia de atomicidad) es una
     decisión fundacional/irreversible → no la tomo autónomamente. Todo listo para
     commitear cuando se decida el alcance del baseline.

- **Mañana:** si Jessicache aprueba (1) baseline mypy pragmático → aplicarlo, arreglar
  los ~120 errores de bug real hasta typecheck verde → primer `make verify` 100% verde.
  En paralelo, decidir (3) el commit raíz para empezar a acumular historia atómica.

---

## 2026-07-07 — Baseline (entrada inicial, escrita por Claude al crear el protocolo)

- Estado: gateway arranca en local vía `scripts/run-local.sh` (:8888, Python 3.13,
  degradación elegante sin Postgres). Frontend Next.js en :3001.
- Verify: cobertura ~24% con gate en 25% (`docs/COVERAGE_ROADMAP.md`; objetivo v0.2 = 70%).
- Pendiente heredado de `docs/DEPLOY_LOCAL_2026-06-09.md`: OAuth propio de calendar
  (`data/google_token.json`), `make docker-infra` para event sourcing + AI local,
  arrancar biohack-app (:8080) para cerrar bucle HRV/sueño, integrar canela-molida e
  ideacursi-tool (ya descomprimidos como carpetas hermanas) al perfil `full`.
- Roadmap: continuar por la siguiente fase pendiente de `docs/PLAN_MICELIA_v0.md`.
- Mañana: ejecutar el ciclo del protocolo `DAILY_MICELIA_PLANNING.md` (raíz de projects/).
