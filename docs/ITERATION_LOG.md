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
