# Plan de Rebrand — vital-core / IDM-CORE → Micelia (T1.1)

> Documento operativo, deferente a `docs/PLAN_MICELIA_v0.md`. Cubre exclusivamente el rebrand textual del orquestador FastAPI. Los 5 dominios funcionales (`biohack`, `canela`, `ideacursi`, `cybertools`, `auto-mat-ion`) NO se renombran.
>
> Documento de referencia: `../../Micelia_Nodo1_Impacto_Socioeconomico.md` (no accesible en esta sesión — revalidar al cerrar v0.1).

## 0. Hallazgos críticos previos al inventario

1. **`source` NO está restringido en BD ni Pydantic.** `scripts/init-db.sql:53-69` define `source VARCHAR(50) NOT NULL` sin CHECK constraint. `app/api/v1/events.py:37` declara `source: str` sin Literal. Los "5 sources válidos" son sólo un **comentario** en `app/sdk/models.py:47`. Añadir `"micelia"` es trivial; el riesgo real es que ya hay un `INSERT` en `init-db.sql:249` con `source='idm-core'` (precedente: el orquestador ya emite eventos con su propio source-id). Esto refuerza la decisión de T1.4.
2. **No existe ninguna ocurrencia de `source="micelia"` en código** (sólo en `docs/PLAN_MICELIA_v0.md` y `tests/e2e/README.md`/`conftest.py` que prevén el rebrand). El rebrand no entra en conflicto con código existente.
3. **`idm-automation` es ambiguo.** `docker-compose.yml:356` lo define como `container_name` del servicio `auto-mat-ion` (línea 352, dominio funcional). `configs/prometheus.yml:90-93` lo confirma como target del job `auto-mat-ion`. **No es el orquestador en su rol de automatización; es el dominio auto-mat-ion al que se le puso un prefijo `idm-` por convención de docker.** Por tanto entra en categoría C (no tocar el rol de dominio) pero el **prefijo `idm-` del container_name** entra en categoría D (decisión sobre coherencia de nomenclatura de contenedores).
4. **El frontend tiene 422 ocurrencias de `idm-*` en 49 archivos**, pero la inmensa mayoría son **design tokens Tailwind** (`bg-idm-surface`, `text-idm-primary`, `border-idm-border`, paleta de colores en `frontend/tailwind.config.js:13-22`). PLAN_MICELIA_v0.md §1.3 dice "fase 1 = sólo strings y copy; sin identidad visual". Estos tokens van a categoría D, recomendación: NO renombrar en v0.1.
5. **`vital_core-0.1.0.dist-info`** en `.venv/lib/python3.13/site-packages/` indica que el paquete fue instalado como `vital-core` (no como `idm-core`) — hay inconsistencia entre el `name` en `pyproject.toml:6` (`idm-core`) y el directorio del repo (`vital-core/`). Es un nombre que ya viene heredando capas de rebrand previo.

## 1. Resumen ejecutivo

El rebrand del orquestador `vital-core` (alias internos `IDM-CORE`, `idm-core`, `IDMMORTALITY`) a `Micelia` afecta aproximadamente **~110 ocurrencias en ~45 archivos** (excluyendo design tokens Tailwind del frontend y el campo `source` de los 5 dominios funcionales). La operación se descompone en cuatro tipos: (A) **renames directos** de copy, títulos y banners; (B) **renames con alias retrocompat** del CLI `idm` y del package Python `idm-core`/`idm_sdk`; (C) **strings que NO se tocan** porque pertenecen a los 5 dominios funcionales (`biohack`, `canela`, `ideacursi`, `cybertools`, `auto-mat-ion`); (D) **decisiones pendientes** sobre nombres de infraestructura (DB `idm_core`, container_names `idm-*`, variables de entorno `IDM_CORE_URL`, design tokens Tailwind `idm-*`). En T1.4 se decide **AÑADIR** `"micelia"` como 6º source para eventos internos emitidos por el propio orquestador, sin tocar los 5 dominios. La migración mantiene un alias `idm ↔ micelia` (CLI y package Python) con `DeprecationWarning` durante v0.1, removible en v0.2.

## 2. Alcance — qué se renombra y qué no

| Pieza | Estado actual | Acción en v0.1 |
|---|---|---|
| Orquestador FastAPI (este repo) | `vital-core` / `IDM-CORE` / `IDMMORTALITY` | **RENAME → Micelia** |
| CLI `idm` (entrypoint) | `pyproject.toml:90` `idm = "app.cli:main"` | **RENAME → `micelia` con alias retrocompat `idm`** |
| Package Python | `pyproject.toml:6` `name = "idm-core"` | **RENAME → `micelia` con alias retrocompat `idm-core`** |
| SDK Python `idm_sdk` y `IdmClient` / `IdmServiceClient` | `sdk/python/idm_sdk/`, `app/sdk/client.py` | **RENAME → `micelia_sdk` / `MiceliaClient` con alias retrocompat** |
| Dominio salud `biohack` (source-id) | `app/sdk/models.py:47`, `scripts/init-db.sql:134` | **NO TOCAR** (dominio funcional, no orquestador) |
| Dominio investigación `canela` | idem | **NO TOCAR** |
| Dominio educación `ideacursi` | idem | **NO TOCAR** |
| Dominio seguridad `cybertools` | idem | **NO TOCAR** |
| Dominio automatización `auto-mat-ion` | idem; container `idm-automation` | **NO TOCAR el source-id**; debate container_name en categoría D |
| Identidad visual Tailwind (`idm-primary`, `idm-surface`...) | `frontend/tailwind.config.js:13-22` + 49 archivos | **DIFERIR a v0.2** (PLAN §1.3 lo excluye explícitamente) |
| DB Postgres `idm_core` + user `idm` + tabla `idm_events` | `docker-compose.yml:37,44,123`, `init-db.sql:42,53,249` | **DIFERIR a v0.2** (rename implica migración Alembic) |

## 3. Inventario por categoría

### Categoría A — Rename directo (copy, marca, títulos, logs, comentarios)

Cada hallazgo: `archivo:línea` — valor actual → valor propuesto.

**A.1 — FastAPI app metadata y root endpoint (alto impacto, user-facing)**
- `app/main.py:2` — `IDM-CORE: Punto de entrada principal` → `Micelia: Punto de entrada principal`
- `app/main.py:60` — `log.info("IDM-CORE: Iniciando IDMMORTALITY System")` → `log.info("Micelia: Iniciando orquestador")`
- `app/main.py:157` — `"IDM-CORE: Sistema inicializado correctamente"` → `"Micelia: Sistema inicializado correctamente"`
- `app/main.py:165` — `"IDM-CORE: Cerrando sistema..."` → `"Micelia: Cerrando sistema..."`
- `app/main.py:188` — `"IDM-CORE: Sistema cerrado correctamente"` → idem
- `app/main.py:193` — `title="IDM-CORE"` → `title="Micelia"` (FastAPI OpenAPI title)
- `app/main.py:195` — `## IDMMORTALITY System - Orquestador Central` → `## Micelia — Orquestador Central`
- `app/main.py:268` — `"name": "IDM-CORE"` → `"name": "Micelia"` (root JSON response — rompe `tests/test_root.py:13` y `tests/conftest.py:74`)
- `app/main.py:270` — `"description": "IDMMORTALITY System - Orquestador Central"` → `"description": "Micelia — Orquestador del ecosistema UTOP.IA"`

**A.2 — CLI banners (rich/click)**
- `app/cli.py:1` — docstring `CLI de administración de IDM-Core` → `CLI de administración de Micelia`
- `app/cli.py:37` — `prog_name="idm-core"` → `prog_name="micelia"`
- `app/cli.py:40` — docstring `IDM-CORE: CLI del IDMMORTALITY System` → `Micelia: CLI del orquestador`
- `app/cli.py:56` — panel `[bold blue]IDM-CORE[/bold blue] - IDMMORTALITY System` → `[bold blue]Micelia[/bold blue] — Orquestador`
- `app/cli.py:109` — `"Asegúrate de que idm-core está ejecutándose."` → `"Asegúrate de que Micelia está ejecutándose."`
- `app/cli.py:163` — docstring `Iniciar el gateway de IDM-Core` → `Iniciar el gateway de Micelia`
- `app/cli.py:167` — panel `[bold blue]Iniciando IDM-CORE[/bold blue]` → `[bold blue]Iniciando Micelia[/bold blue]`

**A.3 — Comentarios y docstrings del paquete `app/`**
- `app/__init__.py:2` — `IDM-CORE: Orquestador Central del IDMMORTALITY System` → `Micelia: Orquestador central`
- `app/api/__init__.py:1` — `"""API routers for idm-core"""` → `"""API routers for Micelia"""`
- `app/api/v1/auth.py:2` — `Authentication endpoints for IDM-CORE.` → `Authentication endpoints for Micelia.`
- `app/api/v1/prompts.py:2`, `app/api/v1/skills.py:2`, `app/api/v1/mcp.py:2` — `API Router para ... de IDM-CORE.` → `... de Micelia.`
- `app/core/__init__.py:1` — `"""Core module for idm-core"""` → `"""Core module for Micelia"""`
- `app/core/security.py:2` — `Security module for IDM-CORE.` → `Security module for Micelia.`
- `app/events/__init__.py:1` — `"""Event sourcing for idm-core"""` → `"""Event sourcing for Micelia"""`
- `app/services/__init__.py:1` — `"""Services for idm-core"""` → `"""Services for Micelia"""`
- `app/services/tunnel.py:4,17` — `Expone idm-core al mundo`, `Gestiona tunnels ngrok para exposición pública de idm-core` → reemplazar `idm-core` por `Micelia`
- `app/services/osascript.py:4` — `Este módulo permite a idm-core interactuar con aplicaciones nativas` → idem
- `app/services/google_calendar.py:4,46` — `idm-core prompts` (x2) → `prompts de Micelia`
- `app/services/mcp_generator.py:143,203,269,348` — `IDM-CORE MCP Generator` (x4) → `Micelia MCP Generator`
- `app/services/agents/__init__.py:2` — `Multi-Agent Orchestration system for IDM-CORE (Phase 6).` → idem
- `app/services/agents/{agent_definitions,workflows,crew_manager,workflow_engine,prompt_os_agents}.py:2` — `... for IDM-CORE Multi-Agent Orchestration.` → `... for Micelia Multi-Agent Orchestration.`
- `app/models/__init__.py:2` — `Modelos SQLAlchemy compartidos para IDM-CORE.` → `... para Micelia.`
- `app/models/prompt.py:2` — `Modelos de datos para el sistema de prompts de IDM-CORE.` → idem
- `app/core/logging.py:35` — `"logs/idm-core.log"` → `"logs/micelia.log"` (path de archivo de log; cambio de path, documentar en release notes).

**A.4 — Tests (deben actualizarse en lockstep con A.1)**
- `tests/test_root.py:13` — `assert data["name"] == "IDM-CORE"` → `"Micelia"`
- `tests/conftest.py:2` — `Shared fixtures for idm-core tests.` → `Micelia tests.`
- `tests/conftest.py:74` — `return {"name": "IDM-CORE", "version": "0.1.0", ...}` → `"Micelia"`

**A.5 — Documentación raíz y de operación**
- `README.md:1,3,9,41,59,186,244,279,362` — todas las apariciones de `IDM-CORE`/`IDMMORTALITY`/`idm-core` reemplazar por `Micelia`. Línea 203 (`"source": "biohack|canela|ideacursi|cybertools|idm-core"`) → `"source": "biohack|canela|ideacursi|cybertools|auto-mat-ion|micelia"`.
- `SAAS_BLUEPRINT.md:1,5,43,54` — idem
- `PROMPTS.md:5` — `idm-core` → `Micelia`
- `cowork.md:3,5,9` — idem
- `claude-sync.md` — 41 ocurrencias de `idm-core` distribuidas. Reemplazar globalmente excepto los paths absolutos `/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core/` literales (esos pertenecen a D.1, futura migración).
- `data/prompt-lists/proyectos.md:12,20`, `data/prompt-lists/plan-corto-plazo.md:13` — referencias narrativas → `Micelia`
- `Dockerfile:2,9` — comentario header + `LABEL description="IDMMORTALITY System - Orquestador Central"` → `Micelia`
- `scripts/entrypoint.sh:3,11,55` — banner y log start
- `scripts/init-db.sql:2,250,257` — comentario header, payload del INSERT inicial, RAISE NOTICE
- `scripts/deploy-landings.sh:3,141,198,247` — todos `IDMMORTALITY` → `Micelia`
- `configs/prometheus.yml:2,9,25` — comentario header, `external_labels.monitor: 'idm-core'` → `'micelia'`
- `tests/e2e/README.md:6` — alinear con texto final
- `CLAUDE.md:1` — `# vital-core` → `# Micelia (orquestador, ex-vital-core)`

**A.6 — Landing pages HTML**
- `frontend/landing-pages/index.html` (2 occ), `blog.html` (4 occ: incl. línea 744 `From IDM-CORE to Vital Core`, 915 título de terminal), `playground.html` (3 occ: línea 507 título de terminal), `lab.html` (1 occ). Texto user-facing → `Micelia`.

**A.7 — Frontend Next.js (sólo texto visible, NO design tokens)**
- `frontend/src/app/layout.tsx:6` — `title: 'Panel IDM - Sistema de Longevidad'` → `'Micelia — Orquestador del ecosistema'`
- `frontend/src/app/layout.tsx:7` — `description: 'Panel de control IDM para el sistema de supervivencia digital'` → equivalente con `Micelia`
- `frontend/src/components/layout/Header.tsx:58` — `IDM PANEL` → `MICELIA`
- `frontend/src/lib/api.ts:1`, `frontend/src/types/api.ts:1` — comentarios `// API Client for idm-core` → `// API Client for Micelia`
- `frontend/src/hooks/useSystemStatus.ts:25,27,89` — `name: 'idm-core'` (visible en UI) → `'micelia'` (acoplado a A.1)
- `frontend/src/components/panel-idm/SystemStatus.tsx:12` — `{ name: 'idm-core', ... }` → `'micelia'`
- `frontend/src/components/panel-idm/MetricsLinks.tsx:35` — `description: 'Swagger UI de idm-core'` → `'Swagger UI de Micelia'`
- `frontend/src/app/calendar/page.tsx:134` — copy visible `idm-core` → `Micelia`
- `frontend/next.config.js:5` — comentario
- `frontend/Dockerfile:21` — comentario; var `NEXT_PUBLIC_IDM_CORE_URL` se discute en D.

**Resumen categoría A**: ~80 ocurrencias en ~32 archivos.

### Categoría B — Rename con alias retrocompat

**B.1 — Entrypoint CLI `idm` → `micelia`**

`pyproject.toml:89-90`:
```toml
[project.scripts]
micelia = "app.cli:main"
idm = "app.cli:_main_deprecated"  # deprecated alias, removible en v0.2
```

En `app/cli.py`:
```python
def _main_deprecated():
    import warnings
    warnings.warn(
        "El CLI `idm` está deprecado, usa `micelia`. Removido en v0.2.",
        DeprecationWarning, stacklevel=2,
    )
    main()
```

**B.2 — Package name Python `idm-core` → `micelia`**
- `pyproject.toml:6` — `name = "idm-core"` → `name = "micelia"`
- `pyproject.toml:8` — description → `"Micelia — Orquestador central del ecosistema UTOP.IA"`
- `pyproject.toml:92` — `packages = ["app"]` se mantiene (el package importable sigue siendo `app`).
- Estrategia retrocompat: opcional meta-package `idm-core` que sólo declare `dependencies = ["micelia==0.1.0"]`.

**B.3 — SDK Python `idm_sdk` y clases `IdmClient` / `IdmServiceClient` → `MiceliaClient`**
- `sdk/python/pyproject.toml:8` — description con `idm-core` → `Micelia`
- `sdk/python/idm_sdk/` — mantener directorio; añadir alias en `__init__.py`
- `sdk/python/idm_sdk/__init__.py:3,8` — añadir `MiceliaClient = IdmClient` con `DeprecationWarning` para el nombre viejo; expandir `__all__`.
- `sdk/python/idm_sdk/client.py:17` — `class IdmClient` → `class MiceliaClient`; `IdmClient = MiceliaClient` como alias.
- `sdk/python/idm_sdk/client.py` líneas 22,46,79,108,125,138,161 — docstrings `idm-core` → `Micelia`.
- `sdk/python/idm_sdk/events.py:7,17,44,47` — docstrings `idm-core` → `Micelia`.
- `sdk/python/idm_sdk/config.py:12` — comentario sobre `IDM_CORE_URL` → mencionar `MICELIA_URL` con alias.
- `sdk/python/tests/test_client.py` líneas 1,23,33,43,58,144,153,222,249 — base URLs `http://idm-core:8888` son hostnames docker (cat. D); añadir test de alias `IdmClient`/`MiceliaClient`.

**B.4 — SDK interno `app/sdk` (`IdmServiceClient`)**
- `app/sdk/__init__.py` líneas 1,5,7,15,33,36 — `IdmServiceClient` aparece en docs y `__all__`. Añadir `MiceliaServiceClient = IdmServiceClient`.
- `app/sdk/client.py` líneas 2,5,26,28,34,35,46,80,94,142,144,159,171,181,189,193,236,265,346 — class y constructor parameter `idm_core_url: str` (línea 47), self.`idm_core_url` (líneas 57, 159, 193, 265). Renombrar a `micelia_url` con alias.
- `tests/test_idm_sdk.py` líneas 4,5,13,103,108,115,137,138 — usa `IdmServiceClient` y `idm_core_url=`. Actualizar y añadir test de alias.

**Resumen categoría B**: ~30 ocurrencias en ~10 archivos. Todas con alias compat.

### Categoría C — NO TOCAR (dominios funcionales)

Estos son los 5 dominios del ecosistema. NUNCA renombrar a `micelia`:

- `app/sdk/models.py:47` — comentario `# biohack, canela, ideacursi, cybertools, auto-mat-ion`. **Acción en T1.4**: ampliar a `# biohack, canela, ideacursi, cybertools, auto-mat-ion, micelia`.
- `scripts/init-db.sql:8-15,18,26,34,134-138` — `CREATE DATABASE biohack;`, `ideacursi`, `canela`, INSERTs de service_status. **NO TOCAR**.
- `docker-compose.yml` servicios `biohack-app`, `canela-molida`, `ideacursi-backend`, `cybertools`, `auto-mat-ion`. **NO TOCAR los nombres de servicio ni los repos hermanos**.
- `configs/prometheus.yml:40-97` — jobs `biohack-app`, `canela-molida`, `ideacursi-tool`, `cybertools`, `codking`, `auto-mat-ion`. **NO TOCAR job_name**.
- `.env.example:31-45` — `HEALTH_SERVICE_URL`, `RESEARCH_SERVICE_URL`, etc. **NO TOCAR**.
- `app/core/config.py:58-68` — `health_service_url`, `research_service_url`, etc. **NO TOCAR**.
- `app/sdk/__init__.py:8` — ejemplo `service_name="biohack-app"`. **NO TOCAR**.
- `docker-compose.yml:186` — `DATABASE_URL=postgresql+asyncpg://idm:idm_password@postgres:5432/biohack`. **NO TOCAR**.

### Categoría D — Decisiones pendientes

| # | Hallazgo | Recomendación T1.1 | Justificación |
|---|---|---|---|
| D.1 | Directorio del repo: `vital-core/` | **Diferir a v0.2** | Renombrar directorio rompe paths absolutos en `claude-sync.md`, MCP configs externos, scripts y bookmarks. |
| D.2 | DB Postgres: `idm_core`, user `idm`, password `idm_password`, tabla `idm_events` | **Diferir a v0.2** + nota de migración Alembic | Rename implica `RENAME DATABASE`, `ALTER ROLE`, migración y coordinación con todos los `DATABASE_URL`. Alto riesgo. |
| D.3 | Variables de entorno `IDM_CORE_URL`, `IDM_CORE_API_URL`, `IDM_CORE_API_KEY`, `NEXT_PUBLIC_IDM_CORE_URL` | **Añadir alias `MICELIA_URL` etc.; mantener `IDM_CORE_*` con prioridad de fallback en v0.1** | Los dominios hermanos leen `IDM_CORE_URL`. Romper sin alias bloquea integración externa. |
| D.4 | Container names `idm-core`, `idm-dashboard`, `idm-postgres-data`, `idm-redis-data`, `idm-prometheus`, `idm-grafana`, `idm-automation`, `idm-biohack`, `idm-research`, `idm-education`, `idm-security`, `idm-codking` | **Renombrar SÓLO `idm-core` → `micelia` en v0.1**; el resto mantener | El container del orquestador ES Micelia; los demás llevan prefijo `idm-` como convención docker. Rename de `idm-core` requiere ajustar 8+ `depends_on` y 10+ URLs internas en lockstep. |
| D.5 | Diseño visual Tailwind: tokens `idm-primary`, `idm-surface`, `idm-border`, etc. (422 ocurrencias en 49 archivos frontend) | **Diferir a v0.2** | PLAN_MICELIA_v0.md §1.3 excluye identidad visual del scope v0.1. |
| D.6 | `image: idm-core:latest` y `image: idm-dashboard:latest` | **Renombrar `idm-core:latest` → `micelia:latest`; mantener `idm-dashboard`** | El image tag del orquestador SÍ es el producto. |
| D.7 | `frontend/src/components/panel-idm/` (directorio) | **Diferir; renombrar a `panel-micelia/` en v0.2** | Mover directorio rompe imports en ~10 archivos; no es user-facing. |
| D.8 | **SDK Python**: `sdk/python/pyproject.toml:6` `name = "idm-sdk"` + directorio `sdk/python/idm_sdk/` + módulo importable `idm_sdk` | **Diferir a v0.2 con package shim `micelia-sdk`** | El rebrand v0.1 renombró la clase (`IdmClient` → `MiceliaClient`) pero conservó el nombre del package y del módulo. Renombrar el package implica meta-package pass-through `idm-sdk → micelia-sdk`, cambiar imports en tests, y coordinar con PyPI si se publica. El alias retrocompat `IdmClient` está implementado vía subclass con `DeprecationWarning` real (T5.4). Identificado en T5.2 (revisión independiente). |

### Resumen cuantitativo del inventario

| Categoría | Archivos | Ocurrencias estimadas |
|---|---|---|
| A — Rename directo | ~32 | ~80 |
| B — Rename con alias | ~10 | ~30 |
| C — No tocar | ~12 | (sin cambios) |
| D — Decisión pendiente / v0.2 | ~50 (mayoría tokens) | ~470 (422 tokens diferidos + 48 infra) |

## 4. Política source-id en eventos (T1.4)

**Decisión: AÑADIR `"micelia"` como 6º source válido.**

Justificación: (1) la BD ya admite cualquier string (`VARCHAR(50)` sin CHECK en `init-db.sql:53-69`) y el INSERT inicial en `init-db.sql:249` ya usa `source='idm-core'` — precedente claro de que el orquestador es un emisor legítimo. (2) Hay eventos legítimos generados por Micelia que no pertenecen a ningún dominio (system.initialized, scheduler.tick, frangels.quota_exceeded, prompt.executed, agent.heartbeat). Inventarlos como `source="system"` colisiona con `category="system"` y rompe la semántica `source = origen, category = clasificación`. Mantener un source-id propio (`"micelia"`) hace el log auditable.

**Implementación (para T1.4)**:
1. `app/sdk/models.py:47` — actualizar comentario: `source: str  # biohack, canela, ideacursi, cybertools, auto-mat-ion, micelia`.
2. `scripts/init-db.sql:249` — cambiar `'idm-core'` por `'micelia'` en el INSERT inicial.
3. Opcional: añadir `Literal` en `EventCreate.source` en `app/api/v1/events.py:37`. Recomendación: NO endurecer (los SDK externos pueden mandar custom sources); documentar en OpenAPI.
4. Aceptar ambos `"idm-core"` (legacy) y `"micelia"` (nuevo) durante v0.1 con normalización + log.warning. Removible en v0.2.
5. Test en `tests/e2e/` que verifica: POST `/api/v1/events` con `source="micelia"` se acepta y persiste; los 5 dominios siguen siendo válidos; `source="idm-core"` se acepta con DeprecationWarning.

## 5. Plan de migración compat (alias `idm` ↔ `micelia`)

**Estrategia general**: el rebrand v0.1 NO rompe consumidores externos. Todo nombre antiguo sigue funcionando pero emite `DeprecationWarning`. Remoción planificada para v0.2.

### 5.1 CLI
Definida en B.1 — wrapper `_main_deprecated` en `app/cli.py`.

### 5.2 Package Python
- Publicar paquete principal como `micelia` (cambio `pyproject.toml:6`).
- Opcional: paquete pass-through `idm-core` con `dependencies = ["micelia==0.1.0"]`.
- Importable `app` se mantiene (`packages = ["app"]`); no rompe imports existentes.

### 5.3 SDK Python (`idm_sdk` → `micelia_sdk`)
Definida en B.3 — `MiceliaClient` como nombre canónico, `IdmClient` como alias deprecado.

### 5.4 Variables de entorno
Patrón en `app/core/config.py` y `sdk/python/idm_sdk/config.py`:
```python
core_url = os.getenv("MICELIA_URL") or os.getenv("IDM_CORE_URL") or "http://localhost:8888"
```
Documentar en `.env.example`:
```
MICELIA_URL=http://localhost:8888
# IDM_CORE_URL=http://localhost:8888  # deprecated, removable v0.2
```

### 5.5 Source-id de eventos
Aceptar ambos `"idm-core"` (legacy) y `"micelia"` (nuevo) en POST `/api/v1/events` durante v0.1. Normalizar `source="idm-core"` → `"micelia"` con log.warning. Removible en v0.2.

## 6. Checklist ejecutable para T1.2, T1.3 y T1.4

### T1.2 — Documentación y copy (worktree)
- [ ] `README.md` líneas 1, 3, 9, 41, 59, 186, 203, 244, 279, 362.
- [ ] `SAAS_BLUEPRINT.md` líneas 1, 5, 43, 54.
- [ ] `PROMPTS.md` línea 5.
- [ ] `cowork.md` líneas 3, 5, 9.
- [ ] `claude-sync.md` 41 ocurrencias (preservar paths absolutos literales — D.1).
- [ ] `CLAUDE.md` línea 1.
- [ ] `Dockerfile` líneas 2, 9.
- [ ] `scripts/entrypoint.sh` líneas 3, 11, 55.
- [ ] `scripts/deploy-landings.sh` líneas 3, 141, 198, 247.
- [ ] `data/prompt-lists/proyectos.md` líneas 12, 20; `plan-corto-plazo.md` línea 13.
- [ ] `frontend/landing-pages/{index,blog,lab,playground}.html` 10 ocurrencias visibles.
- [ ] `docs/PLAN_MICELIA_v0.md` línea 137: actualizar comando grep.
- [ ] `tests/e2e/README.md` línea 6: alineación final.
- [ ] Crear sección "Legado" al final de `README.md`.
- **Verificación T1.2**: `grep -rE "IDM-CORE|IDMMORTALITY" --include="*.md" --include="*.sh" --include="*.sql" --include="*.html"` devuelve 0 hits fuera de la sección "Legado" del README.

### T1.3 — Strings de código (app/, sdk/, tests/, configs/, frontend src)
- [ ] `app/main.py` líneas 2, 60, 157, 165, 188, 193, 195, 268, 270 (A.1).
- [ ] `app/cli.py` líneas 1, 37, 40, 56, 109, 163, 167 (A.2).
- [ ] Comentarios cabecera A.3 (lista completa arriba).
- [ ] `app/core/logging.py` línea 35: path del log.
- [ ] `tests/test_root.py` línea 13, `tests/conftest.py` líneas 2, 74.
- [ ] `configs/prometheus.yml` líneas 2, 9, 25 + decidir job_name del orquestador (D.4).
- [ ] Frontend (A.7).
- [ ] `pyproject.toml` líneas 6, 8, 89-90 (B.1 + B.2).
- [ ] SDK Python (B.3): docstrings + alias `MiceliaClient`.
- [ ] `app/sdk` (B.4): `MiceliaServiceClient` alias.
- [ ] `tests/test_idm_sdk.py` líneas 4, 5, 13, 103, 108, 115, 137, 138.
- **Verificación T1.3**: `grep -rE "IDM-CORE|IDMMORTALITY" app/ sdk/ tests/ frontend/src/ configs/` devuelve 0 hits. `grep -E "idm-core|idm_core" app/ sdk/` devuelve sólo aliases marcados `# deprecated`.

### T1.4 — Política source-id
- [ ] Actualizar comentario `app/sdk/models.py:47` (añadir `micelia`).
- [ ] `scripts/init-db.sql:249` — `'idm-core'` → `'micelia'`.
- [ ] (Opcional) Normalizar `source="idm-core"` → `"micelia"` en `app/events/store.py` `append_event` con log.warning.
- [ ] Test en `tests/e2e/` que valida los 3 escenarios.
- **Verificación T1.4**: ejecutar el test nuevo + `grep "source.*idm-core" app/ scripts/` devuelve sólo el INSERT renombrado y la lógica de normalización.

### T1.5 — Verificación post-rebrand
- [ ] `pytest -x tests/` verde con cambios incluidos.
- [ ] `grep -RE "IDM-CORE|IDMMORTALITY|vital.core" --include="*.{py,ts,tsx,md}" .` no devuelve nada fuera de README "Legado".
- [ ] `python -c "from idm_sdk import IdmClient"` aún funciona (alias).
- [ ] `python -c "from idm_sdk import MiceliaClient"` funciona.
- [ ] `micelia --version` y `idm --version` funcionan; el segundo emite DeprecationWarning.

## 7. Riesgos detectados durante el inventario

| # | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| R1 | El paquete `vital_core-0.1.0` ya está instalado en `.venv` (inconsistencia con `pyproject.toml:6` que dice `idm-core`). | Media | Reinstalar con `pip install -e .` después del cambio en `pyproject.toml`. Documentar limpieza de paquetes huérfanos. |
| R2 | `frontend/landing-pages/blog.html:744` literalmente dice "From IDM-CORE to Vital Core" — un post sobre el rebrand previo. | Baja | Conservar el post original como archivo histórico; añadir uno nuevo "From Vital Core to Micelia". |
| R3 | `scripts/init-db.sql` ejecuta `\c idm_core` (línea 42) y crea la tabla `idm_events`. Renombrar a `micelia_events` rompe `app/events/store.py` y queries. | Alta si se intenta en v0.1 | Mantener nomenclatura legacy. Documentar como "schema heredado v0.x". |
| R4 | El contrato con dominios hermanos usa `IDM_CORE_URL` como env var. Cambiar sin alias rompe los 5 consumidores externos. | Alta | Alias `MICELIA_URL` + fallback `IDM_CORE_URL` (D.3). Coordinar con T0.1. |
| R5 | `tests/conftest.py:74` mockea el root con `"name": "IDM-CORE"`. Cambiar `app/main.py:268` sin tocar el mock deja tests verdes pero el mock obsoleto. | Media | Cambiar `app/main.py` y `tests/conftest.py` + `tests/test_root.py` en el mismo commit. |
| R6 | `docker-compose.yml` tiene >10 ocurrencias de `http://idm-core:8888`. Renombrar el container_name `idm-core` (D.4) obliga a cambiar todas las referencias en lockstep. | Alta | Commit atómico con todos sus consumers. Validar con `docker compose config`. |
| R7 | `category="identity"` aparece en `VALID_CATEGORIES` del SDK pero no en `/categories` del API. | Baja (pre-existente) | Reportar como issue separado a T2.1. |
| R8 | Drift entre `EventBus.CHANNELS` y `EVENT_CHANNELS` del SDK. | Baja | Documentar en T1.4; flag para T5.2. |
| R9 | `Micelia_Nodo1_Impacto_Socioeconomico.md` no accesible en sesión. Si contiene decisiones de naming distintas, hay riesgo de desalineación. | Media | Marcar este documento como `[v0-borrador]` y revalidar cuando el usuario lo monte (T5.3). |
| R10 | Usuario `idm` y password `idm_password` hardcodeados en docker-compose y .env.example. | Alta para v0.2 | NO tocar en v0.1. Planificar migración Alembic + rotación de credenciales en v0.2. |

---

**Estado**: documento listo para que T1.2, T1.3 y T1.4 lo consuman como checklist autoritativo.
