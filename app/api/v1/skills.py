"""
API Router para Skills Manager de Micelia.

Gestiona skills dinamicas: crear, listar, actualizar, eliminar,
activar/desactivar, y probar con prompts de ejemplo.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.logging import log
from app.core.security import verify_auth
from app.services.skills_manager import get_skills_manager

router = APIRouter(prefix="/skills", dependencies=[Depends(verify_auth)])


# ==================== REQUEST/RESPONSE MODELS ====================

class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    # El panel (frontend/src/app/skills/page.tsx) NO exige description en el form de
    # crear skill (handleSubmit solo guarda name/trigger_pattern/prompt_template; el
    # input de description no es `required`) -> puede enviar "". Requerir min_length=1
    # daba 422 al crear una skill sin descripción. Se hace opcional (default ""),
    # consistente con SkillUpdate.description (ya Optional).
    description: str = Field(default="", max_length=2000)
    trigger_pattern: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Regex pattern for auto-triggering the skill",
    )
    prompt_template: str = Field(
        ...,
        min_length=1,
        description="Template with {content} placeholder",
    )
    metadata: Optional[dict] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    # El form de editar skill (SkillForm en skills/page.tsx) esparce el `form` entero
    # en mutate(form), así que `description` viaja SIEMPRE presente; handleSubmit solo
    # exige name/trigger_pattern/prompt_template, no description -> puede enviar "".
    # min_length=1 rechazaba ese "" presente con 422 (editar una skill y vaciar la
    # descripción fallaba). Sin min_length: "" es válido y se persiste (exclude_none lo
    # deja pasar por no ser None). Consistente con SkillCreate.description (C60).
    description: Optional[str] = Field(default=None, max_length=2000)
    trigger_pattern: Optional[str] = Field(default=None, min_length=1, max_length=500)
    prompt_template: Optional[str] = Field(default=None, min_length=1)
    metadata_json: Optional[dict] = None


class SkillTestRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)


# ==================== CRUD ====================

@router.post("")
async def create_skill(data: SkillCreate, request: Request):
    """
    Crea una nueva skill.

    La skill queda activa por defecto y se puede auto-activar cuando
    un prompt coincide con el trigger_pattern (regex).
    """
    try:
        manager = _get_manager(request)
        skill = await manager.create_skill(
            name=data.name,
            description=data.description,
            trigger_pattern=data.trigger_pattern,
            prompt_template=data.prompt_template,
            metadata=data.metadata,
        )
        return skill
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Failed to create skill: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {e}")


@router.get("")
async def list_skills(request: Request):
    """Lista todas las skills registradas."""
    try:
        manager = _get_manager(request)
        skills = await manager.list_skills()
        return {
            "skills": skills,
            "count": len(skills),
            "active": len([s for s in skills if s.get("is_active")]),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to list skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{slug}")
async def get_skill(slug: str, request: Request):
    """Obtiene detalle de una skill por slug."""
    try:
        manager = _get_manager(request)
        skill = await manager.get_skill(slug)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill '{slug}' not found")
        return skill
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get skill {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{slug}")
async def update_skill(slug: str, data: SkillUpdate, request: Request):
    """
    Actualiza campos de una skill.

    Solo se actualizan los campos proporcionados (PATCH parcial).
    """
    try:
        manager = _get_manager(request)

        fields = data.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        skill = await manager.update_skill(slug, fields)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill '{slug}' not found")

        return skill
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Failed to update skill {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{slug}")
async def delete_skill(slug: str, request: Request):
    """Elimina una skill."""
    try:
        manager = _get_manager(request)
        success = await manager.delete_skill(slug)
        if not success:
            raise HTTPException(status_code=404, detail=f"Skill '{slug}' not found")

        return {"success": True, "slug": slug, "message": f"Skill '{slug}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete skill {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ACTIONS ====================

@router.post("/{slug}/toggle")
async def toggle_skill(slug: str, request: Request):
    """
    Alterna el estado activo/inactivo de una skill.

    Skills inactivas no se auto-activan con match_skill.
    """
    try:
        manager = _get_manager(request)
        new_state = await manager.toggle_skill(slug)
        if new_state is None:
            raise HTTPException(status_code=404, detail=f"Skill '{slug}' not found")

        return {
            "success": True,
            "slug": slug,
            "is_active": new_state,
            "message": f"Skill '{slug}' {'activated' if new_state else 'deactivated'}",
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to toggle skill {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{slug}/test")
async def test_skill(slug: str, data: SkillTestRequest, request: Request):
    """
    Prueba una skill aplicando su template a un prompt de ejemplo.

    No ejecuta el prompt, solo muestra como quedaria despues
    de aplicar el template de la skill.
    """
    try:
        manager = _get_manager(request)

        result = await manager.test_skill(slug, data.prompt)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Skill '{slug}' not found")

        skill = await manager.get_skill(slug)

        return {
            "skill": slug,
            "original_prompt": data.prompt,
            "transformed_prompt": result,
            "template_used": skill.get("prompt_template", "") if skill else "",
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to test skill {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HELPERS ====================

def _get_manager(request: Request):
    """
    Obtiene el SkillsManager, inicializandolo con el prompt_store si necesario.

    Busca primero en app.state, luego intenta obtener el singleton.
    """
    # Try app.state first
    manager = getattr(request.app.state, "skills_manager", None)
    if manager:
        return manager

    # Fall back to singleton, using prompt_store from app.state
    prompt_store = getattr(request.app.state, "prompt_store", None)
    if not prompt_store:
        raise HTTPException(
            status_code=503,
            detail="Skills system not available: prompt_store not initialized",
        )

    try:
        manager = get_skills_manager(prompt_store)
        # Cache on app.state for future requests
        request.app.state.skills_manager = manager
        return manager
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
