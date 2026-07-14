"""
API Router para el sistema de prompts de Micelia.

Gestión de prompts, quick notes, prompt lists, y control del pipeline.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AliasChoices, BaseModel, Field

from app.core.security import verify_auth

router = APIRouter(prefix="/prompts", tags=["Prompts"], dependencies=[Depends(verify_auth)])


# ==================== SCHEMAS ====================

class PromptCreate(BaseModel):
    content: str
    category: str = "note"
    priority: int = Field(default=5, ge=0, le=10)
    tags: List[str] = []
    scheduled_at: Optional[datetime] = None
    parent_prompt_id: Optional[UUID] = None
    prefer_paid: bool = False
    metadata: dict = {}


class QuickNoteCreate(BaseModel):
    text: str
    tags: List[str] = []


class PromptUpdate(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=10)
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    prefer_paid: Optional[bool] = None


class PromptListCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "general"
    content_md: str = ""


class PromptListUpdate(BaseModel):
    description: Optional[str] = None
    content_md: Optional[str] = None
    is_active: Optional[bool] = None


class PromptClassify(BaseModel):
    # El botón "Classify" del inbox (frontend/src/components/prompts/InboxPanel.tsx)
    # envía body vacío `{}` (auto-clasificar: mueve captured -> classified sin que el
    # humano elija categoría). `category` debe tener default o el panel recibe 422.
    # Default `"note"` = mismo bucket por defecto que PromptCreate.category.
    category: str = "note"
    tags: List[str] = []
    workflow: str = "quick_execute"
    provider_policy: str = "free-first"


class PromptPromoteToList(BaseModel):
    # El panel (frontend/src/lib/api.ts:promoteToList) envía la clave `slug`;
    # aceptamos ambas (`list_slug` histórico + `slug` del panel) vía AliasChoices
    # para honrar el contrato del panel sin romper consumidores existentes.
    list_slug: str = Field(
        ..., validation_alias=AliasChoices("list_slug", "slug")
    )


class PromptPromoteToSkill(BaseModel):
    name: str
    trigger_pattern: str


class PromptPromoteToMCP(BaseModel):
    pass


# ==================== PROMPT CRUD ====================

@router.post("")
async def create_prompt(data: PromptCreate, request: Request):
    """Crear un nuevo prompt"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    prompt_id = await store.create_prompt(
        content=data.content,
        category=data.category,
        priority=data.priority,
        tags=data.tags,
        scheduled_at=data.scheduled_at,
        parent_prompt_id=data.parent_prompt_id,
        prefer_paid=data.prefer_paid,
        metadata=data.metadata
    )

    return {"prompt_id": str(prompt_id), "status": "pending"}


@router.get("")
async def list_prompts(
    request: Request,
    status: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0
):
    """Listar prompts con filtros"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    return await store.list_prompts(
        status=status,
        category=category,
        source=source,
        limit=limit,
        offset=offset
    )


@router.get("/stats")
async def get_stats(request: Request):
    """Estadísticas del sistema de prompts"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    return await store.get_stats()


# ==================== INBOX / STAGING / ARCHIVE VIEWS ====================

@router.get("/inbox")
async def get_inbox(request: Request, limit: int = 50):
    """Obtener prompts en inbox (captured)"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")
    return {"prompts": await store.get_captured_prompts(limit), "view": "inbox"}


@router.get("/staging")
async def get_staging(request: Request, limit: int = 50):
    """Obtener prompts en staging"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")
    return {"prompts": await store.get_staged_prompts(limit), "view": "staging"}


@router.get("/archive")
async def get_archive(request: Request, limit: int = 50, offset: int = 0):
    """Obtener prompts archivados"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")
    return await store.get_archived_prompts(limit, offset)


# NOTE: the static "/lists" collection route must be declared *before* the
# dynamic "/{prompt_id}" route below; otherwise FastAPI matches "lists" as a
# prompt_id and the UUID validation returns 422, making the endpoint
# unreachable. "/lists/{slug}" (two segments) does not collide, so it stays in
# the PROMPT LISTS section further down.
@router.get("/lists")
async def list_all_lists(request: Request):
    """Listar todas las prompt lists"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    lists = await store.list_all_lists()
    return {"lists": lists, "count": len(lists)}


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: UUID, request: Request):
    """Obtener detalle de un prompt"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    prompt = await store.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt not found")

    return prompt


@router.patch("/{prompt_id}")
async def update_prompt(prompt_id: UUID, data: PromptUpdate, request: Request):
    """Actualizar un prompt"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "No fields to update")

    success = await store.update_prompt(prompt_id, **fields)
    if not success:
        raise HTTPException(404, "Prompt not found")

    return {"success": True}


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: UUID, request: Request):
    """Eliminar un prompt"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.delete_prompt(prompt_id)
    if not success:
        raise HTTPException(404, "Prompt not found")

    return {"success": True}


# ==================== QUICK NOTES ====================

@router.post("/notes")
async def create_note(data: QuickNoteCreate, request: Request):
    """Crear una nota rápida (se convierte en prompt automáticamente)"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    prompt_id = await store.create_note(text=data.text, tags=data.tags)
    return {"prompt_id": str(prompt_id), "status": "captured"}


# ==================== RETRY ====================

@router.post("/{prompt_id}/retry")
async def retry_prompt(prompt_id: UUID, request: Request):
    """Reintentar un prompt fallido"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    prompt = await store.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt not found")

    if prompt["status"] not in ("failed", "completed"):
        raise HTTPException(400, f"Cannot retry prompt with status '{prompt['status']}'")

    await store.update_prompt(
        prompt_id,
        status="pending",
        error=None,
        output=None,
        iterations=prompt["iterations"] + 1
    )

    return {"success": True, "status": "pending"}


# ==================== CLASSIFICATION & STAGING ====================

@router.post("/{prompt_id}/classify")
async def classify_prompt(prompt_id: UUID, data: PromptClassify, request: Request):
    """Clasificar un prompt captured -> classified"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    prompt = await store.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt not found")
    if prompt["status"] != "captured":
        raise HTTPException(400, f"Can only classify 'captured' prompts, got '{prompt['status']}'")

    success = await store.classify_prompt(
        prompt_id, category=data.category, tags=data.tags,
        workflow=data.workflow, provider_policy=data.provider_policy
    )
    return {"success": success, "status": "classified"}


@router.post("/{prompt_id}/stage")
async def stage_prompt(prompt_id: UUID, request: Request):
    """Mover prompt a staging"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.stage_prompt(prompt_id)
    if not success:
        raise HTTPException(404, "Prompt not found")
    return {"success": True, "status": "staged"}


@router.post("/{prompt_id}/approve")
async def approve_staged(prompt_id: UUID, request: Request):
    """Aprobar prompt en staging -> pending"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.approve_staged(prompt_id)
    if not success:
        raise HTTPException(404, "Prompt not found")
    return {"success": True, "status": "pending"}


@router.post("/{prompt_id}/archive")
async def archive_prompt(prompt_id: UUID, request: Request):
    """Archivar un prompt"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.archive_prompt(prompt_id)
    if not success:
        raise HTTPException(404, "Prompt not found")
    return {"success": True, "status": "archived"}


# ==================== PROMOTION ====================

@router.post("/{prompt_id}/promote/list")
async def promote_to_list(prompt_id: UUID, data: PromptPromoteToList, request: Request):
    """Promover prompt a item de lista"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.promote_to_list(prompt_id, data.list_slug)
    if not success:
        raise HTTPException(404, "Prompt or list not found")
    return {"success": True, "promoted_to": "list", "ref": data.list_slug}


@router.post("/{prompt_id}/promote/skill")
async def promote_to_skill(prompt_id: UUID, data: PromptPromoteToSkill, request: Request):
    """Promover prompt a skill"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    skill_id = await store.promote_to_skill(prompt_id, data.name, data.trigger_pattern)
    if not skill_id:
        raise HTTPException(404, "Prompt not found")
    return {"success": True, "promoted_to": "skill", "skill_id": str(skill_id)}


@router.post("/{prompt_id}/promote/mcp")
async def promote_to_mcp(prompt_id: UUID, request: Request):
    """Marcar prompt para generar servidor MCP"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.promote_to_mcp(prompt_id)
    if not success:
        raise HTTPException(404, "Prompt not found")
    return {"success": True, "promoted_to": "mcp"}


# ==================== PROMPT LISTS ====================

@router.post("/lists")
async def create_list(data: PromptListCreate, request: Request):
    """Crear una nueva lista de prompts"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    list_id = await store.create_list(
        name=data.name,
        description=data.description,
        category=data.category,
        content_md=data.content_md
    )

    return {"list_id": str(list_id)}


# NOTE: GET "/lists" (collection) is declared earlier, before "/{prompt_id}",
# to avoid being shadowed by the dynamic route. See that section above.
@router.get("/lists/{slug}")
async def get_list(slug: str, request: Request):
    """Obtener detalle de una lista"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    prompt_list = await store.get_list(slug)
    if not prompt_list:
        raise HTTPException(404, "Prompt list not found")

    return prompt_list


@router.patch("/lists/{slug}")
async def update_list(slug: str, data: PromptListUpdate, request: Request):
    """Actualizar una lista"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "No fields to update")

    success = await store.update_list(slug, **fields)
    if not success:
        raise HTTPException(404, "Prompt list not found")

    return {"success": True}


@router.delete("/lists/{slug}")
async def delete_list(slug: str, request: Request):
    """Eliminar una lista"""
    store = request.app.state.prompt_store
    if not store:
        raise HTTPException(503, "Prompt system not available")

    success = await store.delete_list(slug)
    if not success:
        raise HTTPException(404, "Prompt list not found")

    return {"success": True}


# ==================== PIPELINE CONTROL ====================

@router.get("/pipeline/status")
async def pipeline_status(request: Request):
    """Estado del pipeline de procesamiento"""
    agent = getattr(request.app.state, 'prompt_agent', None)
    executor = getattr(request.app.state, 'prompt_executor', None)

    return {
        "agent": {
            "running": agent.running if agent else False,
            "last_scan": agent.last_scan.isoformat() if agent and agent.last_scan else None,
            "pending_count": agent.last_pending_count if agent else 0,
            "interval_seconds": agent.interval if agent else 0
        },
        "executor": {
            "running": executor.running if executor else False,
            "active_count": executor.active_count if executor else 0,
            "completed_today": executor.completed_today if executor else 0,
            "failed_today": executor.failed_today if executor else 0
        }
    }


@router.post("/pipeline/pause")
async def pipeline_pause(request: Request):
    """Pausar el pipeline"""
    agent = getattr(request.app.state, 'prompt_agent', None)
    executor = getattr(request.app.state, 'prompt_executor', None)

    if agent:
        await agent.stop()
    if executor:
        await executor.stop()

    return {"success": True, "status": "paused"}


@router.post("/pipeline/resume")
async def pipeline_resume(request: Request):
    """Reanudar el pipeline"""
    agent = getattr(request.app.state, 'prompt_agent', None)
    executor = getattr(request.app.state, 'prompt_executor', None)

    if agent:
        await agent.start()
    if executor:
        await executor.start()

    return {"success": True, "status": "running"}
