# Cobertura de tests — roadmap

**Versión**: v0.1
**Última medición**: 2026-07-12 — **75.17%** sobre 6.912 statements en `app/`. Gate `make cov` = **74%** — **hito DoD v0.1 (≥70%) ALCANZADO** (margen +5.17). Histórico: 24.09% (2026-05-24) → 25.28% (Ciclo 1) → 29.37% (Ciclo 2) → 39.06% (Ciclo 3, gate 37%) → 43.11% (Ciclo 4, gate 41%) → 44.60% (Ciclo 5, gate 43%) → 45.51% (Ciclo 6, gate 44%) → 48.99% (Ciclo 7, gate 47%) → 51.93% (Ciclo 8, gate 49%: `google_calendar.py` 13→98%) → 53.31% (Ciclo 9, gate 51%: `event_bus.py` 0→100%) → 57.31% (Ciclo 10, gate 55%: `markdown_sync.py` 0→100%) → 59.90% (Ciclo 11, gate 57%: `mcp_generator.py` 0→100%) → 61.05% (Ciclo 12, gate 59%: `entire_session.py` 0→100% — wrapper del CLI `entire`) → 61.62% (Ciclo 13, gate 60%: `workflow_engine.py` 81→100% — aristas del grafo (agente/acción desconocidos), budget de retries en bucle, camino de fallo con `next_on_failure`, `except` tragados de checkpoint/end_session, trimming de `_runs`, y `_build_messages` por acción; workflows custom vía `monkeypatch.setitem(WORKFLOWS, ...)`) → 61.87% (Ciclo 14, gate 61%: `user_store.py` 88→100% + `prompt_store.py` 95→100% — método `initialize()` DB-setup (`create_async_engine`/`async_sessionmaker`/`create_all`), `close()` y guard de `_session()`; fake de engine con `begin()` async-CM + `run_sync` AsyncMock, sin Postgres real) → 65.47% (Ciclo 16, gate 65%: `api/v1/prompts.py` 0→93% — router CRUD/notes/retry/classify/stage/promote/lists/pipeline sobre `FastAPI()` local + `AsyncMock` `prompt_store` en `app.state`; incluye fix de ruta `/prompts/lists` oculta por `/{prompt_id}`) → **67.85%** (Ciclo 17, gate 67%: `api/v1/routine.py` 0→99% — helpers puros `_parse_routine_md`/`_compute_event_times`/`_tz_offset_for` (frontmatter tipado, descripción multilínea, tz DST-aware + fallback) + endpoints `GET /today` y `POST /sync` con `ROUTINE_FILE` redirigido a fixture temporal, `get_google_calendar` fakeado y `prompt_store` `AsyncMock`; sin Google Calendar/DB/red reales) → **71.58%** (Ciclo 18, gate 70: `api/v1/mcp.py` 0→100% + `api/v1/skills.py` 0→100% — MCP: `get_mcp_generator` monkeypatcheado a `MagicMock` síncrono (singleton real nunca construido, sin disco) + `_parse_prompt_to_spec` puro directo; Skills: `AsyncMock` de manager en `app.state` + ramas fallback de `_get_manager` (503 sin prompt_store, cache de singleton, RuntimeError→503) vía `GET /skills/{slug}`; quirk fijado: `list_skills`/`create_skill` afloran el 503 como 500 por falta de `except HTTPException: raise` — **hito DoD v0.1 ≥70% ALCANZADO**) → **73.18%** (Ciclo 20, gate 72: `api/v1/calendar.py` 0→100% — router Google Calendar (auth OAuth/callback/status/calendars/events GET+POST/sync/disconnect) sobre `FastAPI()` local con `get_google_calendar` monkeypatcheado a `MagicMock` (métodos async = `AsyncMock`, síncronos `get_status`/`is_connected` = returns planos); todas las ramas 200/400/403/500/501 + 422 de validación + propagación del 400 de fecha inválida vía `except HTTPException: raise`; singleton real nunca construido, sin OAuth/token/red) → **74.26%** (Ciclo 21, gate 73: `api/v1/dashboard.py` 0→100% — endpoint agregador `GET /dashboard/summary` sobre `FastAPI()` local con `app.state` (prompt_store/executor/agent/scheduler/google_calendar) fijado a `AsyncMock`/`MagicMock` y `get_policy_engine` monkeypatcheado; cubiertas las 6 sub-agregaciones y sus ramas: dependencia ausente (defaults/[]), store con dicts vs no-dict vs `Exception`, budget del engine vs `except`→ceros, agentes presentes/ausentes, calendario conectado/no-conectado/`Exception`/eventos vacíos; sin infra, red ni `.env`) → **75.17%** (Ciclo 22, gate 74: `api/v1/agents.py` 0→100% — router multi-agente (crews list/create, workflows, execute, runs list+detalle) sobre `FastAPI()` local con `app.state.crew_manager`/`workflow_engine` fijados a `MagicMock`/`AsyncMock`; cubiertos ambos helpers `_get_*`→503 por dependencia ausente, `create_crew` ValueError→400 + validación 422, rama `status=="failed"`→`log.warning` de `execute`, proyección de campos de `list_runs` con eco de `limit`/`offset` + validación `le=200`→422, `get_run` 404, y auth 401/403; `WORKFLOWS` real (5 defs) ejercitado sin mock; sin infra, red ni `.env`)

---

## Decisión

El gate de `make cov` en v0.1 es **25%** (baseline conservador justo por encima de la medición actual). Esto es intencionalmente bajo y honestamente reconocido.

**Por qué NO forzamos 70% en v0.1**:

- Subir de 24% → 70% requiere ejercitar ~4.700 statements adicionales con tests
- Eso es trabajo de 1-2 semanas dedicadas a escribir tests por encima de una superficie de código que aún está evolucionando
- Forzar el threshold ahora produciría dos malos resultados: (a) bloquear la release indefinidamente, o (b) inflar la cobertura con tests "de paso" sin valor real
- El estado real del proyecto se describe mejor publicando un baseline bajo y un compromiso explícito de subida progresiva

**Por qué 25% y no menos**:

- Asegura que la cobertura no retroceda accidentalmente respecto a lo que ya existe
- Es 0.91 puntos por encima de la medición actual (24.09%) — pasa hoy con margen pero detecta regresiones futuras

---

## Estado actual por módulo (orden de prioridad para subir cobertura)

Módulos críticos del orquestador identificados con baja cobertura. Cada uno representa una oportunidad de progreso medible hacia el objetivo v0.2.

### Alta prioridad (core funcional, alta superficie sin tests)

| Módulo | Razón | Plan v0.2 |
|---|---|---|
| `app/services/agents/` | Sistema multi-agente. Crítico operativamente, suite E2E no lo toca | ✅ crew_manager + agent_definitions + workflows (Ciclo 1), workflow_engine 81→**100%** (Ciclo 13: aristas de grafo + retries + audit except + `_build_messages`), prompt_os_agents 98% (Ciclo 4). Módulo cubierto |
| `app/services/frangels/` | Orquestación de providers IA. Crítico para AI sovereignty | ✅ policy_engine 100%, quota_manager 97%, angels 97% (Ciclo 2), provider_store 100% (Ciclo 4), orchestrator 100% (Ciclo 7: select_angel + rutas HTTP de todos los providers, mocks httpx). Módulo cubierto |
| `app/services/prompt_*` | Pipeline completo de prompts (store, agent, executor, scheduler) | ✅ executor 100%, scheduler 99%, agent 98% (Ciclos previos), store **100%** (Ciclo 6: lists/promote/inbox/close; `initialize` DB-setup cerrado en Ciclo 14). Pipeline cubierto |
| `app/services/user_store.py` | Capa de datos del funnel register/login | ✅ **100%** (Ciclo 4/14: CRUD email único + normalización + `initialize`/`close`/guard de sesión, mocks async-session sin Postgres) |
| `app/api/v1/ai.py` | Endpoint integración modelos. Tocado tangencialmente por T3.1 | Tests directos de cada endpoint con mocks de proveedor |
| `app/api/v1/prompts.py` | API de prompts. No cubierta por E2E | Tests CRUD básicos |

### Media prioridad

| Módulo | Razón | Plan v0.2 |
|---|---|---|
| ~~`app/api/v1/skills.py`, `mcp.py`, `agents.py`~~ | APIs especializadas | ✅ skills.py + mcp.py 0→100% (Ciclo 18), agents.py 0→100% (Ciclo 22: crews/workflows/execute/runs sobre `FastAPI()` local, `crew_manager`/`workflow_engine` mockeados). Cubiertas |
| `app/services/skills_manager.py` | Gestión dinámica de skills | Tests CRUD + activación |
| ~~`app/services/google_calendar.py`~~ | Integración externa | ✅ 13→98% (Ciclo 8: auth OAuth + load/save creds + calendars/events CRUD + sync bidireccional; mocks Flow/Credentials/build + PromptStore). Solo el fallback `except ImportError` de import queda sin cubrir |
| `app/services/tunnel.py` | ngrok wrapper | Tests con mock pyngrok |
| ~~`app/services/entire_session.py`~~ | Wrapper del CLI `entire` (trazabilidad de sesiones) | ✅ 0→100% (Ciclo 12: start/checkpoint/end_session con available on/off + `except`, getters, `_run_entire` rc 0/≠0, `_trim_sessions`, singleton; fake de `create_subprocess_exec` + `shutil.which` parcheado, sin subprocesos reales) |
| `app/core/security.py` | API key + rate limiting | Tests del rate limiter aún saltados en E2E (T3.2) |

### Baja prioridad (cobertura indirecta o intencionalmente no testeada)

| Módulo | Razón |
|---|---|
| `app/cli.py` | CLI; sólo se ejercita en startup via `micelia start`. Tests requerirían subprocess + colaboración con uvicorn |
| `app/services/osascript.py` | macOS-specific, no portable a CI Linux |
| `app/main.py` lifespan | Ya cubierto por arranque de la suite E2E vía `_build_test_app` |

---

## Hoja de ruta cuantitativa

| Release | Threshold | Plan |
|---|---|---|
| **v0.1** | **25%** | Baseline honesto. Garantiza no regresión. (HOY) |
| **v0.2** | **45%** | Tests alta prioridad: agents/, frangels/, prompt_* |
| **v0.3** | **60%** | Tests media prioridad: APIs v1 + skills + integraciones externas con mocks |
| **v0.4** | **70%** | Subir prioridad baja + eliminar gaps residuales |
| **v1.0** | **80%** | Auditoría completa antes de release marca registrada |

Cada salto exige unos 5-10 PRs de tests específicos. El roadmap es honesto: 70% en v0.1 era objetivo aspiracional; 70% en v0.4 (con plan medible) es objetivo realista.

---

## Cómo contribuir tests para subir el baseline

1. Elegir un módulo de la sección "Alta prioridad" sin asignar
2. Abrir issue con el módulo elegido para evitar duplicidad de trabajo
3. Escribir tests que mockeen las fronteras externas (BD, HTTP, providers IA)
4. PR con un commit de tests + un commit que suba el `--cov-fail-under` del Makefile en el delta alcanzado
5. Revisión sigue el patrón de `docs/CLA.md` + `.github/PULL_REQUEST_TEMPLATE.md`

---

## Métricas de seguimiento

Cada PR debe reportar el delta de cobertura. Cuando se llegue a uno de los hitos del roadmap, actualizar este documento y el threshold del Makefile en el mismo PR.

Comando para medir local:

```bash
make cov     # corre con threshold actual
make cov --cov-fail-under=0   # corre sin gate (info-only)
```

Reporte HTML granular en `htmlcov/index.html` tras cualquier ejecución de `make cov`.
