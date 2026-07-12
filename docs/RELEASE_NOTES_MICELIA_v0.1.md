# Micelia v0.1 — Release Notes

**Fecha de release**: 2026-05-24 · **Última actualización**: 2026-07-12 (Ciclo 19)
**Estado**: release candidate (RC) endurecida — DoD v0.1 de calidad cerrado salvo QA visual de frontend (ver §11)
**Hito**: primera versión nombrada del orquestador anteriormente conocido como `vital-core` / `IDM-CORE`

---

## TL;DR

Micelia v0.1 es la primera release pública del orquestador central del ecosistema UTOP.IA. Marca tres consolidaciones simultáneas:

1. **Identidad**: el proyecto deja de llamarse `vital-core` / `IDM-CORE` / `IDMMORTALITY` y se renombra a **Micelia** (orquestador), separado claramente de los 5 dominios funcionales del ecosistema (`biohack`, `canela`, `ideacursi`, `cybertools`, `auto-mat-ion`).
2. **Infraestructura**: el proyecto se vuelve usable por un dev externo en un solo comando (`make setup`), con suite E2E completa (3.066 LOC en `tests/e2e/`), banner de dashboards y modo silencioso por defecto.
3. **Soberanía**: el proyecto se publica bajo una estrategia de defensa en profundidad de cinco capas (AGPLv3 + FSL-1.1-ALv2 + Apache 2.0 + trademark + cooperativa) explícitamente anti-Big-Tech, con una política de soberanía IA que obliga al core a funcionar con modelos open-weight.

Todos los cambios de identidad llevan **aliases retrocompat** con `DeprecationWarning`. Ningún consumidor existente se rompe en v0.1. Los aliases se removerán en v0.2.

---

## 1. Cambios destacados

### 1.1 Rebrand vital-core → Micelia

| Antes | Después | Estado retrocompat |
|---|---|---|
| `IDM-CORE` / `IDMMORTALITY` / `vital-core` (nombre del producto) | **Micelia** | Sin alias — son strings, no APIs |
| CLI `idm start` | **`micelia start`** | `idm` sigue funcionando con `DeprecationWarning` |
| Package Python `idm-core` (pyproject) | **`micelia`** | Pass-through opcional vía meta-package |
| Clase `IdmClient` (SDK) | **`MiceliaClient`** | `IdmClient` como subclass que emite `DeprecationWarning` al instanciar |
| Clase `IdmServiceClient` (`app/sdk`) | **`MiceliaServiceClient`** | Alias re-exportado |
| Kwarg `idm_core_url=` | **`micelia_url=`** | Kwarg viejo aceptado con `DeprecationWarning` + fallback de prioridad |
| Source-id `"idm-core"` en eventos (legacy del orquestador) | **`"micelia"`** (6º source añadido junto a los 5 dominios funcionales) | Normalización automática + `DeprecationWarning` |

**Importante**: los 5 dominios funcionales (`biohack`, `canela`, `ideacursi`, `cybertools`, `auto-mat-ion`) **NO se renombran**. Micelia es el orquestador; los dominios son sus consumidores. Esta distinción está documentada en `docs/REBRAND_MICELIA.md` y en el doc canónico `docs/Micelia_Nodo1_Impacto_Socioeconomico.md`.

### 1.2 Estrategia de licencia cooperativa

Micelia se publica bajo una arquitectura legal de cinco capas independientes diseñada para evitar captura corporativa, hosting parasitario y tecnofeudalismo IA. Detalle completo en `docs/LICENSING_STRATEGY.md`.

| Capa | Decisión | Defiende contra |
|---|---|---|
| Orquestador (`app/`, `frontend/`) | **AGPL-3.0-or-later** | Hosting parasitario (AWS-Elasticsearch pattern) |
| Módulos nuevos | **FSL-1.1-ALv2** (Sentry; → Apache 2.0 a los 2 años) | Captura comercial sin ventana competitiva |
| SDK Python (`sdk/python/`) | **Apache-2.0** | Imposición de copyleft a consumidores |
| Marca "Micelia" + logo | **Trademark** (EUIPO + USPTO en trámite) | Forks comerciales que extraigan el nombre |
| Copyright | **Asociación cooperativa** (in formation) + CLA con cláusulas anti-captura | Adquisición corporativa del proyecto |
| Bonus operativo | `AI_SOVEREIGNTY_POLICY.md`: core debe funcionar con modelos open-weight | Tecnofeudalismo IA (atadura a OpenAI/Anthropic) |

**Por qué NO SSPL**: rechazada por OSI y Debian, rompe distribución; AGPL cubre el caso de uso de Micelia. Análisis completo en `docs/LICENSING_STRATEGY.md` §9.

### 1.3 Suite E2E

Nueva infraestructura de testing end-to-end aislada de servicios externos:

- **`tests/e2e/`** (3.066 LOC): happy path, error paths, gateway proxy, ciclo de eventos, política de source-id
- **`tests/e2e/mocks/`** (907 LOC): mock server respx con 4 modos (`healthy`, `degraded`, `down`, `slow`) + contratos Pydantic con `extra="forbid"` (17 modelos)
- **`tests/e2e/fixtures/data.py`** (629 LOC): 3 perfiles de usuario sintéticos, biomarkers con drift determinista, respuestas Bio-Savant curadas
- **`sdk/python/tests/test_e2e_micelia.py`** (329 LOC): tests del SDK con el orquestador completo vía ASGI

Total: **~3.500 LOC de infraestructura de testing**. Todos los tests son verdaderos E2E (usan `httpx.AsyncClient` + `ASGITransport` contra la app FastAPI real; sólo se mockean las fronteras HTTP salientes y la persistencia).

**Cobertura medida**: 24% sobre 6.762 statements en `app/`. Threshold v0.1 = 25% (baseline conservador). Roadmap progresivo hasta 70% en v0.4 documentado en `docs/COVERAGE_ROADMAP.md`. Esta cifra es **intencionalmente baja y honestamente reconocida** — forzar 70% en v0.1 produciría tests "de paso" sin valor real. El plan de subida está cuantificado por módulo (alta/media/baja prioridad).

### 1.4 Tooling y DX

**Makefile orquestador** con 28 targets agrupados por categoría:

- **Setup**: `make setup` (one-liner para day-1 onboarding: install-uv + venv + install + env + docker-infra), `make install`, `make env`
- **Tests**: `make test`, `make test-e2e`, `make test-sdk`, `make cov`, `make verify` (lint + typecheck + test + cov)
- **Calidad**: `make lint`, `make format`, `make typecheck`, `make rebrand-verify`
- **Run**: `make dev` (con banner ASCII de dashboards + modo silencioso), `make dev-verbose`
- **Docker**: `make docker-infra`, `make docker-full`, `make docker-monitoring`, …
- **Mantenimiento**: `make clean`, `make clean-all`, `make version`

**Mejoras de DX detectadas y resueltas durante v0.1**:

- Modo silencioso por defecto (`--log-level warning --no-access-log` + `LOG_LEVEL=warning` para loguru + `database_echo=False`)
- Banner ASCII al arrancar con URLs/puertos de gateway, frontend, 5 subservicios e infraestructura
- Migración a `uv` (10-100× más rápido que `pip`) con detección automática y fallback a venv tradicional
- `_check-venv`: detecta venv corrupto tras renombrado de directorio y avisa con instrucciones de fix
- Helper `app/core/time.py:utcnow_naive()` que resuelve los crashes recurrentes `can't subtract offset-naive and offset-aware datetimes` en scheduler y markdown_sync

### 1.5 Documentación

Estructura de docs publicada para Micelia v0.1:

| Documento | Propósito |
|---|---|
| `docs/Micelia_Nodo1_Impacto_Socioeconomico.md` | Tesis socioeconómica canónica (cooperativa, cobertura de necesidades básicas, perfil Nodo 1, impacto fiscal cuantificado) |
| `docs/PLAN_MICELIA_v0.md` | Plan de desarrollo del rebrand |
| `docs/REBRAND_MICELIA.md` | Inventario de cambios + decisiones diferidas D.1-D.8 |
| `docs/REBRAND_VERIFICATION_REPORT.md` | Verificación de cierre del rebrand |
| `docs/INDEPENDENT_REVIEW_v0.1.md` | Revisión independiente con hallazgos cerrados en T5.4 |
| `docs/LICENSING_STRATEGY.md` | Análisis completo de las 5 capas de defensa legal |
| `docs/AI_SOVEREIGNTY_POLICY.md` | Política open-weight (v0.1 declarativa, enforcement v0.2) |
| `docs/TRADEMARK_POLICY.md` | Política de uso de la marca con "fork test" |
| `docs/ETHICAL_USE.md` | Declaración de valores no vinculante |
| `docs/CLA.md` | CLA cooperativo con cláusulas anti-captura |
| `docs/DEPENDENCIES_AUDIT.md` | Auditoría de compatibilidad de licencias de las 34 deps |
| `docs/MICELIA_BIOHACK_CONTRACT.md` | Contrato bidireccional Micelia ↔ biohack-app |
| `docs/PROPUESTA_MARC_VIDAL.md` | Propuesta de colaboración con Marc Vidal (T7.1) |

---

## 2. Breaking changes

**Ninguno.** v0.1 mantiene compatibilidad total con consumidores existentes mediante aliases retrocompat. El precio es que la fase de cleanup (eliminación de aliases) se difiere a v0.2.

---

## 3. Deprecations (removibles en v0.2)

Los siguientes símbolos siguen funcionando pero emiten `DeprecationWarning`. **Todos serán removidos en v0.2**.

| Símbolo deprecado | Reemplazo | Cómo recibirás la warning |
|---|---|---|
| CLI `idm` | `micelia` | Al ejecutar `idm <cmd>` |
| Clase `IdmClient` (SDK `idm_sdk`) | `MiceliaClient` | Al instanciar `IdmClient(...)` |
| Kwarg `idm_core_url=` (en `IdmServiceClient`/`MiceliaServiceClient`) | `micelia_url=` | Al pasar el kwarg viejo |
| Property `idm_core_url` (lectura) | `micelia_url` | Al leer el atributo |
| Source-id `"idm-core"` en POST `/api/v1/events` | `"micelia"` | Normalizado server-side con warning |
| Variable env `IDM_CORE_URL` | `MICELIA_URL` (con fallback) | No emite warning aún; fallback silencioso. En v0.2 se removerá. |

---

## 4. Decisiones explícitamente diferidas a v0.2

Estas decisiones están registradas en `docs/REBRAND_MICELIA.md` §D y son trabajo planificado para la próxima release. No son omisiones — son cortes intencionales para acotar el alcance de v0.1.

| ID | Diferido | Razón |
|---|---|---|
| D.1 | Renombrar directorio del repo `vital-core/` → `micelia/` | Rompe paths absolutos en `claude-sync.md`, MCP configs externas, bookmarks. (Nota: el directorio ya ha sido renombrado informalmente; v0.2 cierra las referencias huérfanas) |
| D.2 | Migración BD: `idm_core` → `micelia`, user `idm`, tabla `idm_events` | Requiere migración Alembic + coordinación con todos los `DATABASE_URL` |
| D.3 | Variables de entorno: `IDM_CORE_URL` → `MICELIA_URL` con alias | Rompe consumidores externos sin alias coordinado |
| D.4 | Container names docker: `idm-core` → `micelia` | Requiere actualizar 8+ `depends_on` y 10+ URLs internas en lockstep |
| D.5 | Design tokens Tailwind: `idm-*` → `micelia-*` (422 ocurrencias en 49 archivos frontend) | Identidad visual fuera del scope v0.1 |
| D.6 | Image tags: `idm-core:latest` → `micelia:latest` | Coordinar con D.4 |
| D.7 | Directorio `frontend/src/components/panel-idm/` → `panel-micelia/` | Rompe imports en ~10 archivos |
| D.8 | SDK Python: `idm-sdk` → `micelia-sdk` (package + módulo importable) | Requiere meta-package pass-through + cambiar imports en tests + coordinar con PyPI |

---

## 5. Cambios técnicos relevantes

### 5.1 Nuevos archivos / módulos

- `LICENSE` (AGPLv3 verbatim tras `bash scripts/fetch-licenses.sh`)
- `LICENSE.fsl` (FSL-1.1-ALv2 verbatim)
- `NOTICE` (resumen multi-licencia + atribución upstream + nota copyright "in formation")
- `sdk/python/LICENSE` (Apache 2.0)
- `scripts/fetch-licenses.sh` (descarga texto canónico AGPLv3 del FSF con verificación SHA256)
- `app/core/time.py` (helpers `utcnow_naive()` / `utcnow_aware()`)
- `tests/e2e/conftest.py`, `tests/e2e/mocks/`, `tests/e2e/fixtures/` (infraestructura de tests E2E)
- `.github/PULL_REQUEST_TEMPLATE.md` (checklist con CLA + verify)

### 5.2 Cambios de configuración

- `pyproject.toml`: `license = "MIT"` → `license = "AGPL-3.0-or-later"` + classifier OSI AGPLv3
- `sdk/python/pyproject.toml`: `license = "MIT"` → `license = "Apache-2.0"` con comentario explicando la diferencia
- `app/core/config.py`: nuevo `database_echo: bool = False` separado del flag `debug`
- `app/cli.py` comando `start`: nuevos flags `--log-level` y `--access-log/--no-access-log`

### 5.3 Cambios de comportamiento

- **SQLAlchemy queries** dejan de loguearse por defecto (`database_echo=False`). Para activarlas en debugging: `DATABASE_ECHO=true make dev-verbose`
- **Loguru level** controlado por la env var `LOG_LEVEL` (uppercase). Compatible con la flag de uvicorn (lowercase)
- **Eventos legacy `source="idm-core"`** se aceptan pero emiten `DeprecationWarning` y se normalizan a `"micelia"` antes de persistir
- **Aliases `IdmClient` / `IdmServiceClient`** ahora emiten `DeprecationWarning` real al instanciar (antes eran alias transparentes)
- **service_registry**: los chequeos repetidos de subservicios opcionales que ya están caídos se loguean como DEBUG en lugar de WARNING (sólo se warna en transición healthy → unhealthy)

---

## 6. Bugs conocidos / cosas que NO están en v0.1

Identificados durante la revisión independiente (`docs/INDEPENDENT_REVIEW_v0.1.md`) y conscientemente diferidos:

1. **Cobertura de tests al 24%** (threshold actual: 25%). Reconocido y planificado: roadmap progresivo hasta 70% en v0.4 (`docs/COVERAGE_ROADMAP.md`). v0.1 prioriza calidad de tests E2E sobre cantidad de tests unitarios.
2. **`AI_SOVEREIGNTY_POLICY` enforcement técnico no implementado**: la política es declarativa en v0.1 (binding por código review, no por CI). Targets `make sovereignty-audit` y flag `--no-proprietary` llegan en v0.2.
3. **CLA pendiente review legal**: las cláusulas cooperativas §4 (no-relicenciamiento sin supermayoría) y §5 (reversión por captura) son innovadoras y pueden requerir ajustes en derecho español. Review legal (€500-1500) planificado antes de v0.2.
4. **T0.1 pendiente**: el contrato Micelia ↔ biohack-app está inferido desde el orquestador, no validado contra el repo real biohack-app. La suite E2E valida la hipótesis del equipo, no el contrato real. Bloqueante para v0.2.
5. **Trademark "Micelia" en trámite**: EUIPO y USPTO solicitados pero no concedidos. Para el pitch a MV basta con "solicitado".
6. **Asociación cooperativa en formación**: el copyright holder operacional es el founder hasta la constitución formal (esperada 2026-Q3/Q4); deed of transfer documentado en `NOTICE`.

---

## 7. Migración para consumidores existentes

### 7.1 Si usas el CLI

```bash
# Antes
idm start --reload

# Ahora (recomendado)
micelia start --reload

# El comando viejo sigue funcionando con DeprecationWarning hasta v0.2
```

### 7.2 Si usas el SDK Python

```python
# Antes
from idm_sdk import IdmClient, IdmConfig

config = IdmConfig(core_url="http://localhost:8888", api_key="...", ...)
client = IdmClient(config)

# Ahora (recomendado)
from idm_sdk import MiceliaClient, IdmConfig

config = IdmConfig(core_url="http://localhost:8888", api_key="...", ...)
client = MiceliaClient(config)

# El nombre viejo sigue funcionando con DeprecationWarning hasta v0.2.
# Nota: el package se sigue importando como `idm_sdk` (D.8 difiere el rename a v0.2).
```

### 7.3 Si emites eventos al event store

```python
# Antes (legacy del orquestador)
event = {"source": "idm-core", "category": "system", "event_type": "x", "action": "create"}

# Ahora (recomendado)
event = {"source": "micelia", "category": "system", "event_type": "x", "action": "create"}

# El valor viejo se normaliza automáticamente con DeprecationWarning.
# Los 5 dominios funcionales (biohack, canela, ideacursi, cybertools, auto-mat-ion) SIGUEN siendo
# sources válidos y NO se renombran.
```

### 7.4 Si configuras por env vars

```bash
# Antes
export IDM_CORE_URL=http://localhost:8888

# Ahora (recomendado)
export MICELIA_URL=http://localhost:8888

# La var vieja se sigue leyendo como fallback (sin warning aún) hasta v0.2.
```

### 7.5 Si tienes un fork

- Para mantener compatibilidad con el ecosistema, sigue el protocolo de federación cuando esté publicado (T8.x, v0.2+)
- Para distribuir tu fork bajo el nombre "Micelia", lee `docs/TRADEMARK_POLICY.md` "fork test"
- Para contribuir cambios upstream, lee `docs/CLA.md`

---

## 8. Hoja de ruta v0.2 (preliminar)

Items prioritarios identificados durante v0.1 y comprometidos para la próxima release:

1. Cerrar T0.1 — inspección de biohack-app real y reconciliación de contratos INFERRED
2. Ejecutar las decisiones diferidas D.1 a D.8 (rename de directorio, BD, env vars, container names, design tokens, image tags, panel-idm/, sdk package)
3. Implementación técnica de `AI_SOVEREIGNTY_POLICY` (target `make sovereignty-audit`, flag `--no-proprietary` en tests)
4. Review legal externo del CLA cooperativo + resolución de cualquier ajuste
5. Constitución formal de la Asociación Micelia + transfer deed firmado
6. Trademark EUIPO/USPTO concedidos
7. Spec MFP v0.1 (Micelia Federation Protocol) bajo Apache 2.0
8. T4.1-T4.3 — frontend dev con backend mock + QA manual asistido
9. Eliminación de aliases retrocompat anunciada en estas notas (CLI `idm`, `IdmClient`, kwarg `idm_core_url`, source-id `"idm-core"`, env var `IDM_CORE_URL`)
10. Migración Asociación → Cooperativa formal cuando haya 3+ contribuidores activos

---

## 9. Reconocimientos

- **Nodo 1 (Jessicache)** — fundador, autor del doc Nodo 1 canónico, ejecutor del rebrand v0.1
- **Marc Vidal** — interlocutor objetivo cuya tesis pública (*"Contra la cultura del Subsidio"*, *"La Era de la Humanidad"*) inspira el ángulo de pitch externo (`docs/PROPUESTA_MARC_VIDAL.md`)
- **Comunidad cooperativa española** — convenciones de gobernanza y modelo de Asociación que inspiran la estructura legal de Micelia
- **Astral (uv) y los autores de Sentry (FSL)** — herramientas que materializan la mejora de DX y la estrategia de licencia
- **Free Software Foundation** — licencia AGPLv3 que estructura la capa 1 de la defensa anti-captura

---

## 10. Próximos pasos inmediatos

Para empezar a usar Micelia v0.1:

```bash
git clone <repo> micelia
cd micelia
bash scripts/fetch-licenses.sh     # hidrata LICENSE con texto verbatim AGPLv3
make setup                         # install-uv + venv + deps + .env + docker-infra
make test                          # verifica que la suite pasa en tu entorno
make dev                           # arranca el orquestador en :8888 con banner
```

Para entender por qué Micelia existe y qué problema resuelve, leer en este orden:

1. `docs/Micelia_Nodo1_Impacto_Socioeconomico.md` — tesis socioeconómica
2. `README.md` — overview técnico
3. `docs/LICENSING_STRATEGY.md` — por qué AGPL + cooperativa
4. `docs/AI_SOVEREIGNTY_POLICY.md` — por qué open-weight first
5. `docs/PROPUESTA_MARC_VIDAL.md` — ejemplo de cómo Micelia se posiciona en el debate sobre IA y empleo

---

## 11. Addendum — endurecimiento post-RC (Ciclos 6–19, jul 2026)

Tras cerrar la RC el 24-may, la rutina diaria (`DAILY_MICELIA_PLANNING.md`) ejecutó una
campaña de endurecimiento del núcleo. Cambios materiales sobre el estado del 24-may:

### 11.1 Cobertura de tests: 24% → 71.58% (DoD T5.1 cumplido)

El gate de cobertura subió por *ratchet* incremental (un módulo a 100% + un escalón de gate
por ciclo, sin tocar infra), midiendo **71.58%** con `--cov-fail-under=70`. La suite pasó de
~2,5k LOC iniciales a **932 tests** (`pytest`, +2 skip), todos deterministas (sin red/DB/
subprocesos reales; fronteras externas mockeadas con `AsyncMock`/`MagicMock`). Módulos que
pasaron de 0%→~100% en la campaña: `event_bus`, `markdown_sync`, `mcp_generator`,
`entire_session`, `workflow_engine`, `user_store`, `prompt_store`, y los routers
`app/api/v1/{prompts,routine,mcp,skills}.py`. Detalle por ciclo en `docs/ITERATION_LOG.md`
y `docs/COVERAGE_ROADMAP.md`. **El criterio DoD "cov ≥ 70%" queda cumplido.**

### 11.2 Funnel register→login desbloqueado (bug bcrypt resuelto)

Se detectó y corrigió un bug de runtime que hacía dar **500** a `POST /auth/register` y al
login real: `bcrypt 5.0.0` + `passlib 1.7.4` son incompatibles (passlib sondea
`bcrypt.__about__.__version__`, eliminado en bcrypt ≥ 4.1). Fix: pin **`bcrypt==4.0.1`** en
`pyproject.toml` + `uv lock`, con un test de integración que corre bcrypt real (falla con
5.0.0, pasa con 4.0.1). Añadido el frontend `/register` (clon de `/login` con auto-login) y
`frontend/.eslintrc.json` (antes `next lint` colgaba). `make frontend-lint` corre limpio.

### 11.3 Fixes de contrato de API

- `GET /prompts/lists` estaba **oculto** por la ruta dinámica `GET /prompts/{prompt_id}`
  (Starlette matcheaba `"lists"` como UUID → 422). Se reordenó la ruta estática antes de la
  dinámica; el endpoint de colección vuelve a ser alcanzable.
- `POST /skills` y `GET /skills` devolvían **500** cuando el store no estaba inicializado, en
  vez del **503** correcto (les faltaba `except HTTPException: raise`). Corregido en Ciclo 19,
  ya consistente con el resto de endpoints.

### 11.4 Estado del DoD v0.1 (ver checkboxes en `PLAN_MICELIA_v0.md §7`)

Cumplidos con evidencia: `pytest` verde (932), `cov ≥ 70%` (71.58%), grep de strings legado
limpio en `app/`+`sdk/`, los 5 dominios funcionales siguen siendo source-id válidos, `"micelia"`
añadido como 6º source, y estas release notes publicadas/actualizadas. **Pendiente de humano:**
QA visual de los 4 flujos de frontend y la actualización del doc canónico
`Micelia_Nodo1_Impacto_Socioeconomico.md` (requiere montarlo en sesión).

---

*Documento generado al cerrar v0.1 — 2026-05-24 · Nodo 1 (Jessicache).*
*Addendum de endurecimiento — 2026-07-12 (Ciclo 19), rutina Daily Micelia Full Planning.*

*"Micelia no te paga por existir — te cubre por contribuir."*
