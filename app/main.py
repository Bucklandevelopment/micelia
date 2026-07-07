"""
Micelia: Punto de entrada principal de la aplicación FastAPI.

Este es el orquestador central que:
1. Expone un API Gateway unificado
2. Proxea requests a microservicios
3. Gestiona el Event Store compartido
4. Coordina el motor IA (CodKing + Ollama)
5. Monitorea energía y recursos
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.api.v1 import (
    agents as agents_api,
)
from app.api.v1 import (
    ai,
    energy,
    events,
    frangels,
    gateway,
    health,
    prompts,
    system,
)
from app.api.v1 import (
    audit as audit_api,
)
from app.api.v1 import (
    auth as auth_api,
)
from app.api.v1 import (
    budget as budget_api,
)
from app.api.v1 import (
    calendar as calendar_api,
)
from app.api.v1 import (
    dashboard as dashboard_api,
)
from app.api.v1 import (
    mcp as mcp_api,
)
from app.api.v1 import (
    routine as routine_api,
)
from app.api.v1 import (
    skills as skills_api,
)
from app.api.v1 import (
    sync as sync_api,
)
from app.api.v1 import (
    tunnel as tunnel_api,
)
from app.core.config import settings
from app.core.logging import log
from app.events.store import EventStore
from app.services.agents.crew_manager import CrewManager
from app.services.agents.workflow_engine import WorkflowEngine
from app.services.entire_session import get_entire_service
from app.services.event_bus import EventBus
from app.services.frangels.orchestrator import get_frangels_orchestrator
from app.services.markdown_sync import MarkdownSyncService
from app.services.prompt_agent import PromptPrioritizationAgent
from app.services.prompt_executor import PromptExecutor
from app.services.prompt_store import PromptStore
from app.services.scheduler import PromptScheduler
from app.services.service_registry import ServiceRegistry
from app.services.tunnel import get_tunnel_service
from app.services.user_store import UserStore

# Clientes compartidos
http_client: httpx.AsyncClient = None  # type: ignore[assignment]
service_registry: ServiceRegistry = None  # type: ignore[assignment]
event_bus: EventBus = None  # type: ignore[assignment]
event_store: EventStore = None  # type: ignore[assignment]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifecycle manager: inicializa y cierra recursos compartidos.
    """
    global http_client, service_registry, event_bus, event_store

    log.info("=" * 60)
    log.info("Micelia: Iniciando orquestador")
    log.info("=" * 60)

    # Inicializar cliente HTTP compartido
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.service_timeout),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )
    app.state.http_client = http_client

    # Inicializar Service Registry
    service_registry = ServiceRegistry(http_client)
    app.state.service_registry = service_registry
    await service_registry.discover_services()

    # Inicializar Event Bus (Redis Pub/Sub)
    event_bus = EventBus()
    app.state.event_bus = event_bus
    await event_bus.connect()

    # Inicializar Event Store (PostgreSQL) — degrada con warning si no hay DB
    if settings.event_store_enabled:
        try:
            event_store = EventStore()
            await event_store.initialize()
            app.state.event_store = event_store
        except Exception as e:
            log.warning(
                f"Event Store no disponible (¿PostgreSQL apagado?): {e}. "
                "Continuando sin event sourcing."
            )
            event_store = None  # type: ignore[assignment]
            app.state.event_store = None
    else:
        app.state.event_store = None

    # Inicializar User Store (funnel de registro) — degrada con warning si no hay DB.
    # Independiente de los flags de prompt/event: el registro debe funcionar siempre
    # que haya una base de datos alcanzable.
    user_store = None
    try:
        user_store = UserStore()
        await user_store.initialize()
        app.state.user_store = user_store
        log.info("User Store inicializado (funnel de registro)")
    except Exception as e:
        log.warning(
            f"User Store no disponible (¿PostgreSQL apagado?): {e}. "
            "Registro de usuarios deshabilitado."
        )
        user_store = None
        app.state.user_store = None

    # Inicializar Prompt System
    prompt_store = None
    prompt_agent = None
    prompt_executor = None

    if settings.prompt_system_enabled:
        try:
            prompt_store = PromptStore()
            await prompt_store.initialize()
            app.state.prompt_store = prompt_store

            prompt_agent = PromptPrioritizationAgent(prompt_store, event_bus)
            app.state.prompt_agent = prompt_agent
            await prompt_agent.start()

            prompt_executor = PromptExecutor(
                prompt_store,
                frangels_orchestrator=get_frangels_orchestrator(),
                event_bus=event_bus,
                event_store=event_store
            )
            app.state.prompt_executor = prompt_executor
            await prompt_executor.start()

            log.info("Prompt System inicializado (agent + executor)")
        except Exception as e:
            log.warning(
                f"Prompt System no disponible (¿PostgreSQL apagado?): {e}. "
                "Continuando sin prompts."
            )
            prompt_store = None
            prompt_agent = None
            prompt_executor = None
            app.state.prompt_store = None
            app.state.prompt_agent = None
            app.state.prompt_executor = None
    else:
        app.state.prompt_store = None
        app.state.prompt_agent = None
        app.state.prompt_executor = None

    # Inicializar Markdown Sync Service
    md_sync = None
    if settings.prompt_system_enabled and prompt_store:
        md_sync = MarkdownSyncService(prompt_store)
        app.state.md_sync = md_sync
        await md_sync.start()
        log.info("MarkdownSyncService inicializado")
    else:
        app.state.md_sync = None

    # Inicializar Scheduler (Google Calendar + scheduled prompts)
    scheduler = None
    if settings.prompt_system_enabled and prompt_store:
        scheduler = PromptScheduler(prompt_store)
        app.state.scheduler = scheduler
        await scheduler.start()

    # Inicializar Entire CLI session service
    entire_service = get_entire_service()
    app.state.entire_service = entire_service

    # Inicializar Multi-Agent System
    frangels_orch = get_frangels_orchestrator()
    if settings.prompt_system_enabled and prompt_store:
        workflow_engine = WorkflowEngine(frangels_orch, prompt_store, entire_service=entire_service)
        app.state.workflow_engine = workflow_engine

        crew_manager = CrewManager(workflow_engine)
        app.state.crew_manager = crew_manager
        log.info("Multi-Agent system inicializado")
    else:
        app.state.workflow_engine = None
        app.state.crew_manager = None

    # Inicializar ngrok Tunnel (si habilitado)
    tunnel_service = get_tunnel_service()
    app.state.tunnel_service = tunnel_service
    if settings.ngrok_enabled:
        url = await tunnel_service.start()
        if url:
            log.info(f"ngrok tunnel: {url}")

    log.info("Micelia: Sistema inicializado correctamente")
    log.info(f"  Gateway: http://{settings.gateway_host}:{settings.gateway_port}")
    log.info(f"  Docs: http://{settings.gateway_host}:{settings.gateway_port}/docs")
    log.info("=" * 60)

    yield

    # Cleanup
    log.info("Micelia: Cerrando sistema...")

    # Stop tunnel
    if tunnel_service and tunnel_service.is_connected:
        await tunnel_service.stop()

    if md_sync:
        await md_sync.stop()

    if scheduler:
        await scheduler.stop()

    if prompt_agent:
        await prompt_agent.stop()
    if prompt_executor:
        await prompt_executor.stop()
    if prompt_store:
        await prompt_store.close()
    if user_store:
        await user_store.close()

    await http_client.aclose()
    await event_bus.disconnect()
    if event_store:
        await event_store.close()
    log.info("Micelia: Sistema cerrado correctamente")


# Crear aplicación FastAPI
app = FastAPI(
    title="Micelia",
    description="""
    ## Micelia — Orquestador Central

    Integra los siguientes subsistemas:

    - **Salud** (biohack-app): HealthKit, biomarcadores, predicciones
    - **Investigación** (canela-molida): Papers científicos, RAG offline
    - **Educación** (ideacursi-tool): Cursos, quizzes, ejercicios
    - **Seguridad** (cybertools): Análisis wireless, detección de amenazas

    Con un motor de IA unificado basado en CodKing (121M params, 50-260x más eficiente).
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Prometheus metrics
if settings.prometheus_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# Exception handler global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Error no manejado: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": str(exc) if settings.debug else "Error interno del servidor"
        }
    )


# Incluir routers
app.include_router(auth_api.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(gateway.router, prefix="/api/v1", tags=["Gateway"])
app.include_router(events.router, prefix="/api/v1", tags=["Events"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI"])
app.include_router(energy.router, prefix="/api/v1", tags=["Energy"])
app.include_router(system.router, prefix="/api/v1", tags=["System (OSASCRIPT)"])
app.include_router(frangels.router, prefix="/api/v1", tags=["Frangels (Cloud Helpers)"])
app.include_router(prompts.router, prefix="/api/v1", tags=["Prompts"])
app.include_router(tunnel_api.router, prefix="/api/v1", tags=["Tunnel"])
app.include_router(calendar_api.router, prefix="/api/v1", tags=["Calendar"])
app.include_router(mcp_api.router, prefix="/api/v1", tags=["MCP Servers"])
app.include_router(skills_api.router, prefix="/api/v1", tags=["Skills"])
app.include_router(agents_api.router, prefix="/api/v1", tags=["Agents"])
app.include_router(budget_api.router, prefix="/api/v1", tags=["Budget & Policy"])
app.include_router(sync_api.router, prefix="/api/v1", tags=["Sync"])
app.include_router(audit_api.router, prefix="/api/v1", tags=["Audit"])
app.include_router(dashboard_api.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(routine_api.router, prefix="/api/v1", tags=["Routine"])


@app.get("/", tags=["Root"])
async def root():
    """Información básica del sistema"""
    return {
        "name": "Micelia",
        "version": "0.1.0",
        "description": "Micelia — Orquestador del ecosistema UTOP.IA",
        "status": "operational",
        "services": {
            "health": settings.health_service_enabled,
            "research": settings.research_service_enabled,
            "education": settings.education_service_enabled,
            "security": settings.security_service_enabled,
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health",
            "gateway": "/api/v1/gateway",
            "events": "/api/v1/events",
            "ai": "/api/v1/ai",
            "energy": "/api/v1/energy",
            "system": "/api/v1/system",
            "frangels": "/api/v1/frangels",
            "prompts": "/api/v1/prompts",
            "tunnel": "/api/v1/tunnel",
            "calendar": "/api/v1/calendar",
            "mcp": "/api/v1/mcp",
            "skills": "/api/v1/skills",
            "agents": "/api/v1/agents",
            "budget": "/api/v1/budget",
            "sync": "/api/v1/sync",
            "audit": "/api/v1/audit",
            "dashboard": "/api/v1/dashboard",
            "routine": "/api/v1/routine",
            "metrics": "/metrics"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.gateway_host,
        port=settings.gateway_port,
        reload=settings.debug,
        workers=settings.gateway_workers
    )
