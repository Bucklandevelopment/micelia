# Claude Sync: Guia de Integracion Micelia + Ecosistema Claude

> Guia practica para maximizar Claude Desktop, Code, Dispatch y MCP Servers
> como capa de inteligencia natural sobre Micelia (Prompt OS, ex-idm-core).

---

## Tabla de Contenidos

1. [Claude Desktop + MCP Servers](#1-claude-desktop--mcp-servers)
2. [Claude Code](#2-claude-code)
3. [Dispatch y Automatizaciones](#3-dispatch-y-automatizaciones)
4. [MCP Servers que Micelia puede exponer](#4-mcp-servers-que-micelia-puede-exponer)
5. [Personalizaciones Avanzadas](#5-personalizaciones-avanzadas)
6. [Cowork Pattern](#6-cowork-pattern)
7. [Arquitectura de Integracion Completa](#7-arquitectura-de-integracion-completa)

---

## 1. Claude Desktop + MCP Servers

### Concepto Central

Claude Desktop se convierte en la interfaz de lenguaje natural para Micelia.
En lugar de abrir el dashboard o usar curl, le dices a Claude:
"Muestra los prompts pendientes en staging" y Claude consulta la API via MCP.

### Crear un MCP Server para Micelia

Un MCP server es un proceso stdio que expone herramientas (tools) a Claude Desktop.
Micelia ya tiene `app/services/mcp_generator.py` -- la idea es generar servers
que envuelvan los endpoints REST.

Estructura minima de un MCP server en Python:

```python
# mcp_servers/vital_prompts_mcp.py
import json
import sys
import httpx

VITAL_BASE = "http://localhost:8888/api/v1"

TOOLS = [
    {
        "name": "list_prompts",
        "description": "Lista prompts en el pipeline. Filtrar por stage: inbox, classified, staged, executed, archived.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["inbox", "classified", "staged", "executed", "archived"]},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "create_prompt",
        "description": "Crea un nuevo prompt en el inbox de Micelia.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Texto del prompt"},
                "source": {"type": "string", "default": "claude-desktop"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]}
            },
            "required": ["content"]
        }
    },
    {
        "name": "advance_prompt",
        "description": "Avanza un prompt al siguiente stage del pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt_id": {"type": "string"},
                "target_stage": {"type": "string"}
            },
            "required": ["prompt_id"]
        }
    },
    {
        "name": "pipeline_status",
        "description": "Resumen del estado actual del pipeline de prompts.",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

async def handle_tool(name: str, args: dict) -> str:
    async with httpx.AsyncClient(base_url=VITAL_BASE, timeout=30) as client:
        if name == "list_prompts":
            r = await client.get("/prompts", params=args)
            return r.text
        elif name == "create_prompt":
            r = await client.post("/prompts", json=args)
            return r.text
        elif name == "advance_prompt":
            r = await client.post(f"/prompts/{args['prompt_id']}/advance", json=args)
            return r.text
        elif name == "pipeline_status":
            r = await client.get("/prompts/pipeline/status")
            return r.text
    return json.dumps({"error": f"Tool desconocido: {name}"})

# El loop stdio MCP se implementa con el SDK oficial:
# pip install mcp
# Usar mcp.server.stdio para el transporte
```

### Configuracion en Claude Desktop

Editar `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "idm-prompts": {
      "command": "python",
      "args": [
        "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core/mcp_servers/vital_prompts_mcp.py"
      ],
      "env": {
        "IDM_CORE_URL": "http://localhost:8888",
        "IDM_API_KEY": "${IDM_API_KEY}"
      }
    },
    "idm-skills": {
      "command": "python",
      "args": [
        "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core/mcp_servers/vital_skills_mcp.py"
      ]
    },
    "idm-system": {
      "command": "python",
      "args": [
        "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core/mcp_servers/vital_system_mcp.py"
      ]
    }
  }
}
```

### Flujo de Uso

1. Abres Claude Desktop
2. Dices: "Que prompts tengo pendientes en staging?"
3. Claude invoca `list_prompts(stage="staged")`
4. Ves la lista en lenguaje natural con contexto
5. Dices: "Ejecuta el prompt de refactoring de frangels"
6. Claude invoca `advance_prompt(prompt_id="...", target_stage="executed")`

El insight clave: Claude Desktop ya no es solo un chat -- es un **terminal
inteligente** para Micelia que entiende contexto y puede encadenar acciones.

---

## 2. Claude Code

### CLAUDE.md para Micelia

Crear `/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core/CLAUDE.md`:

```markdown
# Micelia — Prompt OS

## Stack
- Backend: FastAPI (Python 3.11+), SQLAlchemy async, Redis pub/sub
- Frontend: Next.js 14 (en /frontend)
- CLI: Click (app/cli.py)
- Puerto: 8888

## Estructura del Proyecto
- app/api/v1/       — 18 routers REST (prompts, skills, frangels, events, etc.)
- app/services/     — Logica de negocio (frangels/, scheduler, event_bus, etc.)
- app/core/         — Config, security, logging
- app/models/       — SQLAlchemy models
- sdk/              — SDK Python para satelites
- frontend/         — Dashboard Next.js
- tests/            — pytest tests
- scripts/          — Utilidades de deployment
- configs/          — Configuraciones por entorno

## Patrones Clave
- Pipeline de prompts: inbox -> classify -> stage -> execute -> review -> archive
- Frangels: 18 proveedores LLM, policy engine, quota manager, orquestador
- Event sourcing: todos los cambios generan eventos en el event bus (Redis)
- Service registry: satelites se registran con heartbeat cada 30s
- MCP generator: genera MCP servers desde definiciones de tools

## Comandos
- `idm status`    — Estado del sistema
- `idm services`  — Lista servicios registrados
- `idm start`     — Inicia Micelia  # alias deprecado de `micelia start`
- `pytest tests/`   — Ejecutar tests

## Convenciones
- Async everywhere: usar `async def` para handlers y servicios
- Modelos Pydantic para request/response
- Errores como HTTPException con codigos semanticos
- Logging estructurado via app/core/logging.py
- Variables de entorno en .env, cargadas via app/core/config.py
```

### Sistema de Memoria (.claude/memory/)

El directorio `.claude/memory/` persiste contexto entre sesiones de Claude Code.
Organizar asi:

```
.claude/
  memory/
    MEMORY.md              # Contexto general del ecosistema (ya existe)
    vital-decisions.md     # Decisiones arquitectonicas y su razon
    vital-patterns.md      # Patrones recurrentes y anti-patrones
    vital-debt.md          # Deuda tecnica conocida y plan de pago
  agents/
    prompt-reviewer.md     # Agente para revisar cambios en pipeline
    test-runner.md         # Agente para ejecutar y analizar tests
    deploy-helper.md       # Agente para asistir deployments
  settings.json            # Hooks y configuracion
```

Ejemplo de `vital-decisions.md`:

```markdown
# Decisiones Arquitectonicas

## 2026-02: Event Bus con Redis en lugar de Kafka
- Razon: simplicidad, ya tenemos Redis para cache
- Tradeoff: no hay persistencia de eventos garantizada
- Mitigacion: Event Store en PostgreSQL como backup

## 2026-02: SDK vendored en cada satelite
- Razon: independencia de deploys, no requiere PyPI
- Tradeoff: duplicacion de codigo
- Mitigacion: script de sync para propagar cambios
```

### Agentes Personalizados

Crear en `.claude/agents/` archivos Markdown que definen agentes especializados:

```markdown
<!-- .claude/agents/prompt-reviewer.md -->
# Prompt Pipeline Reviewer

Eres un reviewer especializado en el pipeline de prompts de Micelia.

## Tu Rol
Revisa cambios en:
- app/api/v1/prompts.py
- app/services/prompt_store.py
- app/services/prompt_executor.py
- app/services/prompt_agent.py

## Checklist
1. Cada transicion de stage debe generar un evento en el event bus
2. Validar que los prompts tienen source y priority
3. No permitir saltos de stage (inbox -> executed sin pasar por staged)
4. Verificar que el executor maneja timeouts y errores de proveedor
5. Los prompts archivados deben ser inmutables

## Formato de Review
- APROBADO / CAMBIOS NECESARIOS / BLOQUEADO
- Lista de observaciones con severidad (critico/medio/bajo)
```

```markdown
<!-- .claude/agents/test-runner.md -->
# Test Runner Agent

Eres un agente especializado en ejecutar y analizar tests de Micelia.

## Flujo
1. Ejecuta `pytest tests/ -v --tb=short`
2. Analiza fallos: identifica si son bugs reales o tests fragiles
3. Para tests nuevos: verifica cobertura de edge cases
4. Sugiere tests faltantes basado en el codigo modificado

## Reglas
- Nunca marques un test como "skip" sin justificacion
- Los tests de integracion requieren Redis corriendo
- Mocks de httpx para tests de SDK de satelites
```

### Hooks en settings.json

```json
{
  "hooks": {
    "PreCommit": [
      {
        "command": "pytest tests/ -x -q --timeout=30",
        "description": "Ejecutar tests antes de commit"
      },
      {
        "command": "python -m ruff check app/",
        "description": "Lint con ruff"
      }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(pytest *)",
      "Bash(python -m ruff *)",
      "Bash(vital *)",
      "Read(**/idm-core/**)"
    ]
  }
}
```

### Slash Commands Personalizados

Crear skills reutilizables para operaciones frecuentes:

```markdown
<!-- .claude/commands/vital-status.md -->
Ejecuta `curl -s http://localhost:8888/api/v1/health | python -m json.tool`
y resume el estado del sistema en una tabla:
- Servicios registrados y su ultimo heartbeat
- Estado del event bus
- Prompts por stage
- Proveedores frangels activos
```

```markdown
<!-- .claude/commands/sync-sdk.md -->
Sincroniza el SDK de Micelia a todos los satelites:
1. Lee app/sdk/ como fuente de verdad
2. Compara con sdk/ en cada satelite (biohack-app, canela-molida, etc.)
3. Reporta diferencias
4. Pregunta antes de copiar cambios
```

### Mejores Practicas para Prompts en Claude Code

- **Ser especifico con archivos**: "Modifica app/api/v1/prompts.py para agregar
  un endpoint GET /prompts/stats que devuelva conteos por stage"
- **Dar contexto del patron**: "Sigue el patron de app/api/v1/skills.py que usa
  dependency injection con Depends(get_skills_manager)"
- **Pedir validacion**: "Despues de implementar, ejecuta los tests y verifica
  que no rompe nada existente"
- **Referenciar decisiones**: "Consulta cowork.md para ver las prioridades actuales"

---

## 3. Dispatch y Automatizaciones

### Tareas Programadas con Claude

Claude Code soporta tareas programadas via `scheduled-tasks`. Esto permite
automatizar operaciones recurrentes sobre Micelia.

### Health Check Diario (9:00 AM)

```
Task ID: vital-daily-health
Cron: 0 9 * * *
Prompt:
  Ejecuta un health check completo de Micelia:
  1. curl http://localhost:8888/api/v1/health
  2. curl http://localhost:8888/api/v1/services
  3. Revisa logs recientes: tail -50 logs/micelia.log
  4. Verifica que Redis esta corriendo: redis-cli ping
  5. Resume el estado en un reporte conciso
  6. Si hay errores criticos, crea un prompt urgente en el inbox
```

### Code Review Semanal (Lunes 10:00 AM)

```
Task ID: vital-weekly-review
Cron: 0 10 * * 1
Prompt:
  Revisa los cambios de la ultima semana en Micelia:
  1. git log --oneline --since="7 days ago" (si hay git)
  2. Busca TODOs y FIXMEs nuevos en app/
  3. Verifica que no hay endpoints sin autenticacion
  4. Revisa que los tests siguen pasando
  5. Genera un resumen para cowork.md con hallazgos
```

### Auditoria Mensual de Dependencias (Dia 1, 8:00 AM)

```
Task ID: vital-monthly-deps
Cron: 0 8 1 * *
Prompt:
  Auditoria mensual de dependencias de Micelia:
  1. Lee pyproject.toml y verifica versiones
  2. Busca vulnerabilidades conocidas con pip-audit
  3. Revisa que las dependencias de frontend estan actualizadas
  4. Compara con las versiones usadas por los satelites
  5. Genera un reporte con recomendaciones de actualizacion
```

### Integracion con el PromptScheduler de Micelia

Micelia tiene su propio scheduler en `app/services/scheduler.py`.
La integracion bidireccional funciona asi:

```
PromptScheduler (Micelia)          Claude Dispatch
        |                                    |
        |-- cron job dispara prompt -------->|
        |                                    |-- Claude ejecuta la tarea
        |<-- resultado como evento ---------|
        |                                    |
        |-- prompt requiere LLM ----------->|
        |                                    |-- Claude procesa via frangels
        |<-- respuesta clasificada ---------|
```

Para conectarlos, Micelia puede exponer un webhook que Claude Dispatch invoque:

```python
# app/api/v1/dispatch.py
@router.post("/dispatch/webhook")
async def receive_dispatch_result(
    task_id: str,
    result: dict,
    event_bus: EventBus = Depends(get_event_bus)
):
    """Recibe resultados de tareas ejecutadas por Claude Dispatch."""
    await event_bus.publish("dispatch.completed", {
        "task_id": task_id,
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"status": "received"}
```

### Sincronizacion con Google Calendar

Micelia ya tiene `app/services/google_calendar.py`. La integracion con
Claude Dispatch permite:

1. **Claude lee el calendario** via MCP server `vital-calendar-mcp`
2. **Crea eventos** para tareas programadas de largo plazo
3. **Sincroniza deadlines** del pipeline de prompts con el calendario
4. **Notificaciones**: prompts con deadline generan eventos de calendario

---

## 4. MCP Servers que Micelia puede exponer

### vital-prompts-mcp

**Proposito**: CRUD completo del pipeline de prompts.

| Tool | Descripcion | Endpoint |
|------|-------------|----------|
| `list_prompts` | Lista prompts por stage/filtro | GET /api/v1/prompts |
| `get_prompt` | Detalle de un prompt | GET /api/v1/prompts/{id} |
| `create_prompt` | Crea prompt en inbox | POST /api/v1/prompts |
| `advance_prompt` | Mueve al siguiente stage | POST /api/v1/prompts/{id}/advance |
| `classify_prompt` | Clasifica un prompt | POST /api/v1/prompts/{id}/classify |
| `execute_prompt` | Ejecuta un prompt staged | POST /api/v1/prompts/{id}/execute |
| `archive_prompt` | Archiva un prompt completado | POST /api/v1/prompts/{id}/archive |
| `pipeline_stats` | Conteos y metricas del pipeline | GET /api/v1/prompts/stats |
| `search_prompts` | Busqueda semantica en prompts | GET /api/v1/prompts/search |

```python
# mcp_servers/vital_prompts_mcp.py
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx

app = Server("idm-prompts")
BASE = "http://localhost:8888/api/v1"

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="list_prompts",
            description="Lista prompts. Filtros: stage, priority, source, limit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stage": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                }
            }
        ),
        # ... mas tools
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        if name == "list_prompts":
            r = await client.get("/prompts", params=arguments)
            return [TextContent(type="text", text=r.text)]
    return [TextContent(type="text", text=f"Tool no encontrado: {name}")]

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### vital-skills-mcp

**Proposito**: Gestionar el sistema de skills.

| Tool | Descripcion | Endpoint |
|------|-------------|----------|
| `list_skills` | Lista skills disponibles | GET /api/v1/skills |
| `get_skill` | Detalle de un skill | GET /api/v1/skills/{id} |
| `create_skill` | Crea un nuevo skill | POST /api/v1/skills |
| `test_skill` | Ejecuta un skill en dry-run | POST /api/v1/skills/{id}/test |
| `suggest_skills` | Sugiere skills para un prompt | POST /api/v1/skills/suggest |
| `skill_stats` | Estadisticas de uso de skills | GET /api/v1/skills/stats |

### vital-frangels-mcp

**Proposito**: Monitorear y gestionar proveedores LLM.

| Tool | Descripcion | Endpoint |
|------|-------------|----------|
| `provider_status` | Estado de los 18 proveedores | GET /api/v1/frangels/status |
| `usage_stats` | Estadisticas de uso y costos | GET /api/v1/frangels/usage |
| `budget_check` | Presupuesto restante por proveedor | GET /api/v1/frangels/budget |
| `test_provider` | Ping a un proveedor especifico | POST /api/v1/frangels/test |
| `set_policy` | Modifica politica de ruteo | PUT /api/v1/frangels/policy |
| `provider_ranking` | Ranking por latencia/calidad | GET /api/v1/frangels/ranking |

### vital-events-mcp

**Proposito**: Consultar y crear eventos del event sourcing.

| Tool | Descripcion | Endpoint |
|------|-------------|----------|
| `query_events` | Timeline de eventos filtrable | GET /api/v1/events |
| `event_detail` | Detalle de un evento | GET /api/v1/events/{id} |
| `create_event` | Emite un evento manual | POST /api/v1/events |
| `event_stats` | Conteos por tipo/servicio/dia | GET /api/v1/events/stats |
| `subscribe_pattern` | Suscribe a patron de eventos | POST /api/v1/events/subscribe |

### vital-calendar-mcp

**Proposito**: Integrar Google Calendar con el workflow.

| Tool | Descripcion | Endpoint |
|------|-------------|----------|
| `list_events` | Eventos del calendario | GET /api/v1/calendar/events |
| `create_event` | Crea evento en calendario | POST /api/v1/calendar/events |
| `update_event` | Modifica un evento | PUT /api/v1/calendar/events/{id} |
| `sync_deadlines` | Sincroniza deadlines de prompts | POST /api/v1/calendar/sync |
| `today_agenda` | Agenda del dia | GET /api/v1/calendar/today |

### vital-system-mcp

**Proposito**: Estado del sistema y gestion de infraestructura.

| Tool | Descripcion | Endpoint |
|------|-------------|----------|
| `system_health` | Health check completo | GET /api/v1/health |
| `service_registry` | Servicios registrados | GET /api/v1/services |
| `energy_status` | Consumo energetico | GET /api/v1/energy |
| `tunnel_status` | Estado del tunel ngrok | GET /api/v1/tunnel |
| `tunnel_toggle` | Activa/desactiva tunel | POST /api/v1/tunnel/toggle |
| `system_logs` | Ultimas lineas de log | GET /api/v1/system/logs |

### Patron Comun de Implementacion

Todos los MCP servers siguen la misma estructura:

```python
# Estructura base para cualquier vital-*-mcp
import asyncio
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

VITAL_BASE = "http://localhost:8888/api/v1"

def create_vital_mcp(name: str, tools_config: list[dict]):
    """Fabrica de MCP servers para Micelia."""
    app = Server(name)

    @app.list_tools()
    async def list_tools():
        return [Tool(**t) for t in tools_config]

    @app.call_tool()
    async def call_tool(tool_name: str, arguments: dict):
        cfg = next((t for t in tools_config if t["name"] == tool_name), None)
        if not cfg:
            return [TextContent(type="text", text=f"Tool desconocido: {tool_name}")]

        method = cfg.get("method", "GET")
        path = cfg["path"].format(**arguments)
        async with httpx.AsyncClient(base_url=VITAL_BASE, timeout=30) as client:
            if method == "GET":
                r = await client.get(path, params=arguments)
            elif method == "POST":
                r = await client.post(path, json=arguments)
            elif method == "PUT":
                r = await client.put(path, json=arguments)
            return [TextContent(type="text", text=r.text)]

    return app
```

---

## 5. Personalizaciones Avanzadas

### Agente: prompt-os-reviewer

```markdown
<!-- .claude/agents/prompt-os-reviewer.md -->
# Prompt OS Reviewer

Especializado en revisar cambios al pipeline de prompts de Micelia.

## Archivos bajo tu responsabilidad
- app/api/v1/prompts.py
- app/services/prompt_store.py
- app/services/prompt_executor.py
- app/services/prompt_agent.py
- app/services/context_assembler.py

## Invariantes que debes verificar
1. Todo prompt tiene: id, content, source, stage, created_at
2. Las transiciones de stage son lineales: inbox -> classified -> staged -> executed -> reviewed -> archived
3. Nunca se salta un stage sin flag explicito de override
4. Cada transicion emite un evento al event bus
5. El executor nunca modifica el prompt original -- crea un resultado separado
6. Los prompts archivados son inmutables
7. El context_assembler no filtra informacion sin razon documentada

## Formato de salida
### Estado: [APROBADO | CAMBIOS | BLOQUEADO]
### Observaciones
- [CRITICO/MEDIO/BAJO] Descripcion del hallazgo
### Sugerencias
- Mejoras opcionales que no bloquean
```

### Agente: frangels-auditor

```markdown
<!-- .claude/agents/frangels-auditor.md -->
# Frangels Auditor

Audita la configuracion y uso de los 18 proveedores LLM.

## Archivos bajo tu responsabilidad
- app/services/frangels/orchestrator.py
- app/services/frangels/policy_engine.py
- app/services/frangels/quota_manager.py
- app/services/frangels/provider_store.py
- app/services/frangels/angels.py
- app/api/v1/frangels.py
- configs/

## Verificaciones
1. Ningun API key hardcodeado -- todos deben venir de env vars
2. El policy engine tiene fallback definido para cada proveedor
3. Los quotas tienen limites razonables (no infinitos)
4. El orquestador maneja timeouts y retries con backoff
5. Los costos estimados coinciden con la documentacion del proveedor
6. Las credenciales cifradas usan el store, no archivos planos

## Metricas a reportar
- Costo estimado mensual por proveedor
- Tasa de fallos por proveedor (si hay logs)
- Proveedores sin uso en los ultimos 30 dias
- Proveedores sin fallback configurado
```

### Agente: security-checker

```markdown
<!-- .claude/agents/security-checker.md -->
# Security Checker

Valida la seguridad de Micelia.

## Archivos criticos
- app/core/security.py
- app/core/config.py
- app/api/v1/auth.py
- .env (verificar que no esta en version control)

## Checklist de seguridad
1. Autenticacion: todos los endpoints sensibles requieren auth
2. CORS: configurado restrictivamente, no wildcard en produccion
3. Rate limiting: implementado en endpoints publicos
4. Sanitizacion: inputs validados con Pydantic, sin SQL injection
5. Secretos: ninguno en codigo fuente, todos en .env o vault
6. HTTPS: el tunel ngrok usa TLS
7. Logs: no loggear tokens, passwords, ni API keys
8. Dependencias: sin vulnerabilidades conocidas criticas
```

### Organizacion de Memoria

Principio: **recordar decisiones, derivar estado del codigo**.

Lo que SI guardar en `.claude/memory/`:
- Decisiones arquitectonicas y su razonamiento
- Bugs resueltos y su causa raiz (para no repetirlos)
- Patrones que funcionan bien en el proyecto
- Deuda tecnica conocida con prioridad
- Preferencias del usuario (estilo de codigo, convenciones)

Lo que NO guardar:
- Listas de archivos (cambion constantemente)
- Estado actual de features (derivar del codigo)
- Documentacion que ya existe en el repo
- Configuraciones temporales

### CLAUDE.md: Patrones Especificos de Micelia

```markdown
## Patrones Anti-Fragiles

### Servicio con Graceful Degradation
Los servicios deben funcionar aunque Micelia este caido:
- Intentar registrarse
- Si falla, loggear warning y continuar
- Reintentar registro cada 30s en background

### Event Publishing
Siempre publicar eventos despues de la operacion, no antes:
  result = await do_operation()
  await event_bus.publish("operation.completed", result)

### Dependency Injection
Usar FastAPI Depends() para inyectar servicios:
  async def get_prompt_store() -> PromptStore: ...
  @router.get("/prompts")
  async def list_prompts(store: PromptStore = Depends(get_prompt_store)): ...
```

---

## 6. Cowork Pattern

### El Patron de Colaboracion Humano-Claude

El `cowork.md` es el centro gravitacional de la colaboracion. No es documentacion
-- es una conversacion estrategica continua.

### Estructura de cowork.md

```markdown
# Cowork - Micelia

## Prioridades Actuales (semana del 17-21 Mar)
1. [EN PROGRESO] Completar MCP servers para Claude Desktop
2. [PENDIENTE] Tests end-to-end del pipeline de prompts
3. [BLOQUEADO] Deployment a produccion - falta validar Docker Compose

## Decisiones Pendientes
- Migrar event bus de Redis a algo persistente?
- Frangels: agregar soporte para modelos locales (Ollama)?
- Frontend: mantener Next.js o migrar a algo mas ligero?

## Notas de Sesion
### 2026-03-21 - Sesion con Claude Code
- Creamos claude-sync.md como guia de integracion
- Proximo paso: implementar vital-prompts-mcp

## Deuda Tecnica
- [ ] Los tests de integracion necesitan Redis mock
- [ ] El scheduler no persiste estado entre reinicios
- [ ] Falta rate limiting en el API gateway
```

### Session Handoff: Continuidad entre Sesiones

Cuando inicias una nueva sesion de Claude Code, el contexto se carga desde:

1. **CLAUDE.md** -- estructura y convenciones del proyecto
2. **`.claude/memory/MEMORY.md`** -- contexto del ecosistema completo
3. **`cowork.md`** -- prioridades y estado actual

Para un handoff efectivo, termina cada sesion actualizando cowork.md:

```markdown
## Fin de Sesion [fecha]
### Completado
- Implementado endpoint X en app/api/v1/...
- Tests agregados en tests/test_...

### En Progreso
- Refactoring de frangels orchestrator (50%)
- Archivo: app/services/frangels/orchestrator.py linea 145

### Contexto para la Proxima Sesion
- El test test_quota_exceeded falla porque el mock no simula bien el timeout
- Revisar si el policy engine maneja el caso de todos los proveedores caidos
```

### El Ciclo Blueprint-Plan-Implement-Validate

```
  BLUEPRINT (cowork.md)
       |
       v
    PLAN (Claude analiza, propone enfoque)
       |
       v
  IMPLEMENT (Claude Code escribe codigo)
       |
       v
  VALIDATE (tests, review, health check)
       |
       v
  BLUEPRINT (actualizar cowork.md con resultados)
```

Ejemplo practico:

1. **Blueprint**: "Necesito que el pipeline de prompts soporte prioridades
   y que los prompts criticos salten al frente de la cola"
2. **Plan**: Claude analiza prompt_store.py, propone agregar campo priority
   con enum y modificar los queries de listado
3. **Implement**: Claude Code modifica los archivos necesarios y crea tests
4. **Validate**: Ejecutar pytest, verificar que el endpoint responde bien
5. **Blueprint**: Actualizar cowork.md con el resultado y la siguiente prioridad

### Uso de Multiples Instancias de Claude

La configuracion optima usa tres capas:

| Instancia | Rol | Uso |
|-----------|-----|-----|
| **Claude Desktop** | Investigacion y consulta rapida | "Como funciona el policy engine?" / Consultar docs via MCP |
| **Claude Code** | Implementacion y desarrollo | Escribir codigo, ejecutar tests, refactoring |
| **Claude Dispatch** | Automatizacion y monitoreo | Health checks, auditorias, tareas programadas |

Flujo tipico de un dia:

1. **Manana**: Claude Dispatch ejecuta el health check diario (automatico)
2. **Planificacion**: Abres Claude Desktop, preguntas por MCP: "Estado del pipeline?"
3. **Desarrollo**: Abres Claude Code, dices: "Revisa cowork.md y trabaja en la
   prioridad 1"
4. **Validacion**: Claude Code ejecuta tests y reporta
5. **Cierre**: Actualizas cowork.md con resultados

---

## 7. Arquitectura de Integracion Completa

### Diagrama del Sistema

```
+------------------------------------------------------------------+
|                     USUARIO (Mac Studio)                          |
+------------------------------------------------------------------+
        |                    |                    |
        v                    v                    v
+----------------+  +----------------+  +-------------------+
| Claude Desktop |  |  Claude Code   |  | Claude Dispatch   |
| (chat + MCP)   |  | (desarrollo)   |  | (automatizacion)  |
+----------------+  +----------------+  +-------------------+
        |                    |                    |
        | MCP stdio          | filesystem          | cron/webhook
        v                    v                    v
+------------------------------------------------------------------+
|                    MCP SERVERS (stdio)                            |
|  vital-prompts | vital-skills | vital-frangels | vital-events    |
|  vital-calendar | vital-system                                   |
+------------------------------------------------------------------+
        |
        | httpx (localhost)
        v
+------------------------------------------------------------------+
|                    MICELIA (localhost:8888)                     |
|                                                                  |
|  +------------+  +-----------+  +------------+  +----------+    |
|  | Prompt     |  | Frangels  |  | Event Bus  |  | Service  |    |
|  | Pipeline   |  | (18 LLMs) |  | (Redis)    |  | Registry |    |
|  +------------+  +-----------+  +------------+  +----------+    |
|  +------------+  +-----------+  +------------+  +----------+    |
|  | Skills     |  | Calendar  |  | Scheduler  |  | API      |    |
|  | Manager    |  | (Google)  |  |            |  | Gateway  |    |
|  +------------+  +-----------+  +------------+  +----------+    |
|                                                                  |
+------------------------------------------------------------------+
        |                    |                    |
        | SDK/REST           | Redis pub/sub      | ngrok tunnel
        v                    v                    v
+------------------------------------------------------------------+
|                    SATELITES (6 servicios)                        |
|  biohack-app | canela-molida | ideacursi-tool                   |
|  cybertools  | codking       | auto-mat-ion                     |
+------------------------------------------------------------------+
        |
        | ngrok
        v
+------------------------------------------------------------------+
|              ACCESO PUBLICO (idmmortality.com)                    |
+------------------------------------------------------------------+
```

### Flujo de Datos: Prompt desde Claude Desktop hasta Ejecucion

```
1. Usuario en Claude Desktop:
   "Analiza el paper de longevidad que subi ayer"

2. Claude Desktop invoca MCP tool:
   vital-prompts.create_prompt({
     content: "Analizar paper de longevidad reciente",
     source: "claude-desktop",
     priority: "high"
   })

3. MCP server hace POST a Micelia:
   POST http://localhost:8888/api/v1/prompts
   Body: { content, source, priority }

4. Micelia procesa:
   a. Crea prompt en inbox
   b. Emite evento: prompt.created
   c. Auto-clasifica con frangels
   d. Emite evento: prompt.classified
   e. Si es analizable, busca skill adecuado

5. Event Bus (Redis) propaga:
   Canal "prompt.classified" -> canela-molida escucha
   canela-molida tiene capacidad paper.ingested

6. Micelia orquesta:
   a. Envia tarea a canela-molida via API gateway
   b. canela-molida procesa el paper
   c. Resultado vuelve a Micelia
   d. Prompt avanza a "executed"
   e. Emite evento: prompt.executed

7. Usuario en Claude Desktop:
   "Como quedo el analisis del paper?"
   -> MCP tool: vital-prompts.get_prompt(id)
   -> Resultado en lenguaje natural
```

### Flujo de Datos: Claude Code como Audit Trail

```
1. Desarrollador abre Claude Code en el repo de Micelia (`vital-core/` en disco)

2. Claude Code lee contexto:
   - CLAUDE.md -> estructura del proyecto
   - .claude/memory/MEMORY.md -> estado del ecosistema
   - cowork.md -> prioridades actuales

3. Desarrollador: "Agrega endpoint de metricas a frangels"

4. Claude Code:
   a. Analiza app/api/v1/frangels.py
   b. Analiza app/services/frangels/orchestrator.py
   c. Implementa endpoint
   d. Crea tests
   e. Ejecuta pytest

5. Si Micelia esta corriendo, Claude Code puede:
   a. POST /api/v1/events (crear evento de tipo dev.change)
   b. El evento queda en el Event Store (PostgreSQL)
   c. Audit trail: quien cambio que, cuando, por que

6. Claude Code actualiza cowork.md:
   "Endpoint de metricas implementado, 3 tests nuevos pasando"

7. Proxima sesion de Claude Code tiene contexto completo
```

### Configuracion Completa de Claude Desktop

El archivo final `claude_desktop_config.json` para la integracion completa:

```json
{
  "mcpServers": {
    "idm-prompts": {
      "command": "python",
      "args": ["mcp_servers/vital_prompts_mcp.py"],
      "cwd": "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core",
      "env": { "IDM_CORE_URL": "http://localhost:8888" }
    },
    "idm-skills": {
      "command": "python",
      "args": ["mcp_servers/vital_skills_mcp.py"],
      "cwd": "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core"
    },
    "idm-frangels": {
      "command": "python",
      "args": ["mcp_servers/vital_frangels_mcp.py"],
      "cwd": "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core"
    },
    "idm-events": {
      "command": "python",
      "args": ["mcp_servers/idm_events_mcp.py"],
      "cwd": "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core"
    },
    "idm-calendar": {
      "command": "python",
      "args": ["mcp_servers/vital_calendar_mcp.py"],
      "cwd": "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core"
    },
    "idm-system": {
      "command": "python",
      "args": ["mcp_servers/vital_system_mcp.py"],
      "cwd": "/Users/unknown1/Codex/github/UTOP.IA/SECos/projects/idm-core"
    }
  }
}
```

### Checklist de Implementacion

Orden recomendado para implementar esta integracion:

```
Fase 1 - Fundamentos (1-2 dias)
  [x] Crear claude-sync.md (esta guia)
  [ ] Crear CLAUDE.md para Micelia
  [ ] Configurar .claude/settings.json con hooks
  [ ] Crear .claude/agents/ con los 3 agentes

Fase 2 - MCP Servers (3-5 dias)
  [ ] Implementar vital-system-mcp (mas simple, para validar patron)
  [ ] Implementar vital-prompts-mcp (mas valor inmediato)
  [ ] Implementar vital-skills-mcp
  [ ] Implementar vital-frangels-mcp
  [ ] Configurar claude_desktop_config.json
  [ ] Validar que Claude Desktop puede consultar Micelia

Fase 3 - Automatizacion (2-3 dias)
  [ ] Configurar health check diario en Claude Dispatch
  [ ] Configurar code review semanal
  [ ] Crear webhook de dispatch en Micelia
  [ ] Integrar con PromptScheduler

Fase 4 - Refinamiento (continuo)
  [ ] Ajustar agentes basado en uso real
  [ ] Expandir herramientas de MCP servers segun necesidad
  [ ] Optimizar memoria y contexto
  [ ] Documentar patrones que emerjan en cowork.md
```

---

## Notas Finales

Esta guia es un documento vivo. A medida que la integracion madure:

- Los MCP servers se expandiran con mas herramientas
- Los agentes se refinaran con mejores checklists
- El cowork.md capturara patrones que hoy no imaginamos
- La automatizacion via Dispatch reducira trabajo manual

El objetivo final: **Micelia + Claude = un sistema que se desarrolla,
monitorea y mejora a si mismo, con el humano como director estrategico**.
