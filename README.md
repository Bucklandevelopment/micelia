# MicelIA

**Orquestador del ecosistema UTOP.IA, potenciado por IA**

Orquestador central que integra los pilares de SALUD, EDUCACIÓN e INVESTIGACIÓN del ecosistema UTOP.IA.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Micelia                                 │
│                    Gateway/Orquestador                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ biohack │  │ canela  │  │ideacursi│  │ cyber   │            │
│  │  -app   │  │ molida  │  │  tool   │  │ tools   │            │
│  │ (Salud) │  │(Invest.)│  │ (Educ.) │  │ (Seg.)  │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       │            │            │            │                  │
│       └────────────┴────────────┴────────────┘                  │
│                         │                                       │
│              ┌──────────┴──────────┐                           │
│              │    Event Store      │                           │
│              │   (PostgreSQL)      │                           │
│              └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Características

- **API Gateway**: Punto de entrada unificado para todos los microservicios
- **Event Sourcing**: Trazabilidad completa de todas las acciones
- **Service Registry**: Descubrimiento y monitoreo de servicios
- **Event Bus**: Comunicación asíncrona via Redis Pub/Sub
- **Energy Awareness**: Monitoreo de energía y batería del sistema
- **AI Unificada**: Acceso centralizado a Ollama y CodKing
- **CLI Rico**: Administración completa desde terminal

## Servicios Integrados

| Servicio | Descripción | Puerto |
|----------|-------------|--------|
| micelia | Gateway/Orquestador | 8888 |
| biohack-app | Sistema de Salud | 8080 |
| canela-molida | Investigación/Papers | 3690 |
| ideacursi-tool | Generación de Cursos | 5050 |
| cybertools | Seguridad/CodKing | 8000 |

## Inicio Rápido

### Requisitos

- Docker y Docker Compose
- Python 3.11+ (para desarrollo local)
- macOS (para integración con pmset/osascript)

### Desarrollo Local (con Makefile — recomendado)

El `Makefile` orquesta el flujo completo y usa [`uv`](https://astral.sh/uv) de
Astral como gestor de paquetes (10-100× más rápido que pip; reemplaza
`venv + pip + pip-tools + pipx` en un único binario). Si `uv` no está
instalado, cae automáticamente a `python -m venv` + `pip`.

Setup desde cero en un solo comando:

```bash
cd vital-core           # el directorio aún se llama así; el paquete es `micelia`
make setup              # install-uv + crea .venv + instala .[dev] + .env + docker-infra
make dev                # arranca el gateway Micelia en :8888 con --reload
```

O por pasos si prefieres control granular:

```bash
make install-uv         # instala uv (curl|sh oficial); idempotente
make env-create         # crea el .venv con Python 3.13 (alias de `make venv`)
make install            # instala Micelia .[dev] + respx + pytest-httpx
make env                # copia .env.example → .env (sólo si no existe)
make docker-infra       # levanta postgres + redis + ollama
```

En otra terminal, para el panel frontend:

```bash
make frontend-install     # primera vez
make frontend-dev         # arranca Next.js en :3001 contra backend real
make frontend-dev-mock    # arranca con backend mockeado (MSW) — útil para QA
```

El modo mock no necesita Postgres/Redis/Ollama ni el orquestador FastAPI;
intercepta todas las llamadas a `/api/v1/*` con datos sintéticos. Ver
`frontend/README.md` para la lista de endpoints cubiertos y limitaciones.

Comandos típicos del día a día:

| Comando | Qué hace |
|---|---|
| `make test`              | Toda la suite (unit + e2e + sdk) |
| `make test-e2e`          | Sólo E2E con mocks `respx` |
| `make cov`               | Cobertura ≥70% con reporte HTML en `htmlcov/` |
| `make verify`            | `lint + typecheck + test + cov` (gate pre-commit) |
| `make format`            | Black + Ruff `--fix` |
| `make rebrand-verify`    | Detecta strings residuales `IDM-CORE`/`IDMMORTALITY` |
| `make docker-full`       | Levanta el ecosistema completo (perfil `full`) |
| `make clean`             | Limpia caches; `make clean-all` borra también `.venv` |

### Desarrollo Local (sin Makefile)

Si prefieres invocar los comandos a mano, esto es lo que el Makefile hace
internamente:

```bash
# Clonar e instalar
cd vital-core
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" respx pytest-httpx

# Variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# Iniciar solo infraestructura
docker compose up postgres redis ollama -d

# Ejecutar gateway (alias retrocompat `idm` aún funciona con DeprecationWarning)
micelia start --reload
```

### Docker Compose

```bash
# Solo gateway + infraestructura
docker compose up -d

# Ecosistema completo
docker compose --profile full up -d

# Con monitoreo (Prometheus + Grafana)
docker compose --profile full --profile monitoring up -d

# Solo servicios específicos
docker compose --profile health up -d      # + biohack-app
docker compose --profile research up -d    # + canela-molida
docker compose --profile education up -d   # + ideacursi-tool
docker compose --profile security up -d    # + cybertools
```

## CLI

La CLI `vital` proporciona acceso completo al sistema:

```bash
# Ver estado general
idm status

# Estado detallado de servicios
idm services

# Ver últimos eventos
idm events --limit 50

# Filtrar por categoría
idm events --category health

# Estado de IA
idm ai status

# Estado de energía
idm energy

# Crear curso desde investigación
vital create-course "longevidad y senolíticos" --papers 50

# Iniciar gateway
idm start --host 0.0.0.0 --port 8888 --reload
```

## API

### Endpoints Principales

```
GET  /api/v1/health           # Health check básico
GET  /api/v1/health/detailed  # Estado detallado
GET  /api/v1/health/services  # Estado de microservicios

# Gateway (proxy a servicios)
ANY  /api/v1/gateway/{service}/{path}
POST /api/v1/gateway/pipeline/research-to-course

# Eventos
GET  /api/v1/events           # Listar eventos
POST /api/v1/events           # Crear evento
GET  /api/v1/events/stats     # Estadísticas
GET  /api/v1/events/timeline/{date}

# IA
GET  /api/v1/ai/status        # Estado de servicios IA
POST /api/v1/ai/generate      # Generación con Ollama
POST /api/v1/ai/codking/analyze  # Análisis con CodKing

# Energía
GET  /api/v1/energy/status    # Estado del sistema
GET  /api/v1/energy/history   # Historial
POST /api/v1/energy/set-mode  # Cambiar modo
```

### Ejemplos

```bash
# Health check
curl http://localhost:8888/api/v1/health/detailed | jq

# Proxy a canela-molida
curl http://localhost:8888/api/v1/gateway/research/papers/search?q=longevity

# Crear evento
curl -X POST http://localhost:8888/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "category": "health",
    "source": "biohack",
    "action": "create",
    "event_type": "biomarker.recorded",
    "payload": {"type": "hrv", "value": 45}
  }'

# Generar con IA
curl -X POST http://localhost:8888/api/v1/ai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explica los beneficios de la restricción calórica",
    "model": "llama3.2:3b"
  }'
```

## Arquitectura

### Flujo de Datos

```
Usuario → Micelia (Gateway) → Microservicio específico
                ↓
          Event Store (PostgreSQL)
                ↓
          Event Bus (Redis) → Otros servicios suscritos
```

### Event Sourcing

Todos los eventos siguen el schema `IdmEvent`:

```python
{
    "event_id": "uuid",
    "correlation_id": "uuid",     # Agrupa eventos relacionados
    "timestamp": "2024-01-15T10:30:00Z",
    "category": "health|education|research|security|system",
    "source": "biohack|canela|ideacursi|cybertools|auto-mat-ion|micelia",
    "action": "create|update|delete|query|analyze",
    "event_type": "biomarker.recorded",
    "payload": {},
    "metadata": {},
    "compute_provider": "ollama|codking|claude",
    "compute_latency_ms": 150.5
}
```

### Compute Router

Decisión inteligente entre cómputo local y cloud:

```
                     ┌─────────────────┐
                     │  Compute Router │
                     └────────┬────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    ┌────▼────┐         ┌─────▼─────┐        ┌────▼────┐
    │ LOCAL   │         │  HYBRID   │        │  CLOUD  │
    │ Ollama  │         │  CodKing  │        │  Claude │
    │ ONNX    │         │           │        │ OpenAI  │
    └─────────┘         └───────────┘        └─────────┘

    Prioridad:          Modelo                APIs
    - Privacidad        especializado         externas
    - Sin costo         3 cores:              para
    - Offline           - Health              tareas
                        - Education           complejas
                        - Security
```

## Configuración

### Variables de Entorno

```bash
# Aplicación
APP_NAME=micelia
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key

# Gateway
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8888

# Servicios
HEALTH_SERVICE_URL=http://localhost:8080
RESEARCH_SERVICE_URL=http://localhost:3690
EDUCATION_SERVICE_URL=http://localhost:5050
SECURITY_SERVICE_URL=http://localhost:8000

# Bases de datos
DATABASE_URL=postgresql+asyncpg://idm:idm_password@localhost:5432/idm_core
REDIS_URL=redis://localhost:6379/0

# IA
OLLAMA_BASE_URL=http://localhost:11434
CODKING_ENABLED=true
CODKING_MODEL_PATH=/path/to/codking/model

# Energía
SOLAR_PANEL_ENABLED=false
SOLAR_API_URL=
```

## Desarrollo

### Estructura del Proyecto

```
micelia/  # repo directory aún `vital-core/` en disco
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── cli.py               # CLI con Click/Rich
│   ├── api/
│   │   └── v1/
│   │       ├── health.py    # Health checks
│   │       ├── gateway.py   # API Gateway
│   │       ├── events.py    # Event API
│   │       ├── ai.py        # AI endpoints
│   │       └── energy.py    # Energy monitoring
│   ├── core/
│   │   ├── config.py        # Settings
│   │   └── logging.py       # Structured logging
│   ├── services/
│   │   ├── service_registry.py
│   │   └── event_bus.py
│   └── events/
│       └── store.py         # PostgreSQL Event Store
├── configs/
│   └── prometheus.yml
├── scripts/
│   └── init-db.sql
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

### Testing

```bash
# Instalar dependencias de desarrollo
pip install -e ".[dev]"

# Ejecutar tests
pytest

# Con cobertura
pytest --cov=app

# Solo tests de integración
pytest -m integration
```

## Monitoreo

### Prometheus + Grafana

```bash
# Iniciar stack de monitoreo
docker compose --profile monitoring up -d

# Acceder a:
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Métricas Disponibles

- `vital_requests_total` - Total de requests por endpoint
- `vital_request_duration_seconds` - Latencia por endpoint
- `vital_service_health` - Estado de microservicios (0/1)
- `idm_events_total` - Eventos procesados por categoría
- `vital_ai_inference_seconds` - Latencia de inferencia IA
- `vital_energy_battery_percent` - Nivel de batería

## Pipeline Research-to-Course

Flujo completo para generar cursos desde investigación:

```
1. Usuario: vital create-course "senolíticos"
                    │
2. canela-molida: Buscar papers en OpenAlex/arXiv
                    │
3. canela-molida: RAG synthesis de papers
                    │
4. ideacursi-tool: Generar estructura de curso
                    │
5. ideacursi-tool: Crear quizzes y ejercicios
                    │
6. Micelia: Almacenar eventos del pipeline
                    │
7. Usuario: Curso listo con N módulos
```

## Roadmap

- [ ] Dashboard web para Panel IDM
- [ ] Integración OSASCRIPT (Calendar, Contacts, Notes)
- [ ] CodKing multi-core training
- [ ] Sincronización con HealthKit via biohack-app
- [ ] Modo offline completo
- [ ] Mobile companion app

## Licencia

Micelia se distribuye bajo una **estrategia de defensa en profundidad de cinco capas** diseñada para proteger el carácter cooperativo del proyecto contra captura corporativa, hosting parasitario y tecnofeudalismo. Análisis completo: [`docs/LICENSING_STRATEGY.md`](docs/LICENSING_STRATEGY.md).

| Componente | Licencia | Por qué |
|---|---|---|
| Orquestador (`app/`, `frontend/`) | **AGPL-3.0-or-later** ([`LICENSE`](LICENSE)) | Cualquier SaaS basado en Micelia debe liberar mejoras. Cierra la grieta SaaS del GPL. |
| Módulos nuevos a partir de hoy | **FSL-1.1-ALv2** ([`LICENSE.fsl`](LICENSE.fsl)) | Source-available 2 años → Apache 2.0. Ventana competitiva justa estilo Sentry. |
| SDK Python (`sdk/python/`) | **Apache-2.0** ([`sdk/python/LICENSE`](sdk/python/LICENSE)) | Integración sin copyleft para máxima adopción. |
| Documentación (`docs/`) | **CC-BY-SA-4.0** | Reutilización libre con atribución y compartir-igual. |
| Datos sintéticos de tests | **CC0-1.0** | Dominio público. |
| Marca "Micelia" + logo | **Trademark registrado** ([`docs/TRADEMARK_POLICY.md`](docs/TRADEMARK_POLICY.md)) | El código es libre; el nombre protege a usuarios contra forks extractivos. |

**Documentos relacionados:**

- [`NOTICE`](NOTICE) — resumen multi-licencia con atribución de dependencias upstream
- [`docs/CLA.md`](docs/CLA.md) — Contributor License Agreement cooperativo (con cláusulas anti-captura)
- [`docs/AI_SOVEREIGNTY_POLICY.md`](docs/AI_SOVEREIGNTY_POLICY.md) — política vinculante de modelos open-weight
- [`docs/ETHICAL_USE.md`](docs/ETHICAL_USE.md) — declaración de valores (no legalmente vinculante)
- [`docs/DEPENDENCIES_AUDIT.md`](docs/DEPENDENCIES_AUDIT.md) — auditoría de compatibilidad de dependencias

**Para poblar `LICENSE` con el texto verbatim de AGPLv3** (los archivos del repo contienen el header informativo; el texto completo se descarga del FSF):

```bash
bash scripts/fetch-licenses.sh
```

Copyright (C) 2026 Asociación Micelia para la Soberanía Computacional Cooperativa *(in formation)* y contribuidores.

## Legado IDM-CORE

Este proyecto fue originalmente conocido como `vital-core` y, antes de eso,
como `IDM-CORE` (parte del llamado *IDMMORTALITY System*). En la versión
**v0.1** se renombró a **Micelia** como nombre canónico del orquestador del
ecosistema UTOP.IA. Los 5 dominios funcionales (`biohack`, `canela`,
`ideacursi`, `cybertools`, `auto-mat-ion`) **no** cambian de nombre.

Para no romper a los consumidores existentes, v0.1 mantiene los siguientes
**aliases retrocompat**, todos los cuales emiten `DeprecationWarning`:

| Pieza nueva | Alias deprecado | Notas |
|---|---|---|
| CLI `micelia` | `idm` | `idm <cmd>` sigue funcionando; emite warning. |
| Package Python `micelia` | `idm-core` | Pass-through opcional vía meta-package. |
| SDK `MiceliaClient` / `MiceliaServiceClient` | `IdmClient` / `IdmServiceClient` | Alias re-exportados desde `idm_sdk` y `app.sdk`. |
| Kwarg `micelia_url=` | `idm_core_url=` | Aceptado en constructores del SDK. |
| Env var `MICELIA_URL` | `IDM_CORE_URL` | `MICELIA_URL` toma prioridad; `IDM_CORE_URL` es fallback. |
| Source-id `"micelia"` en eventos | `"idm-core"` | Ambos aceptados; `"idm-core"` se normaliza a `"micelia"` con warning. |

**Todos estos aliases serán removidos en la v0.2.** Actualiza tu código a los
nombres nuevos antes de esa release.

Algunas piezas de infraestructura conservan nomenclatura heredada en v0.1 y
se diferirán a v0.2 (decisión documentada en `docs/REBRAND_MICELIA.md`,
categoría D):

- Directorio del repo: `vital-core/` (D.1).
- Base de datos Postgres: `idm_core`, usuario `idm`, tabla `idm_events` (D.2).
- Container names docker auxiliares: `idm-dashboard`, `idm-postgres-data`,
  etc. (D.4). Sólo `idm-core` → `micelia` se renombra en v0.1.
- Tokens de diseño Tailwind `idm-*` (D.5).

Documento de referencia autoritativo del rebrand:
[`docs/REBRAND_MICELIA.md`](docs/REBRAND_MICELIA.md).
