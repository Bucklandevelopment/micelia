"""
Skills Manager: Gestión de skills dinámicas almacenadas en PostgreSQL.

Las skills son plantillas de prompt con patrones de activación (regex)
que se aplican automáticamente cuando un prompt coincide.
"""

import re
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import delete, select, update

from app.core.logging import log
from app.core.time import utcnow_naive
from app.models.prompt import SkillModel
from app.services.prompt_store import PromptStore


class SkillsManager:
    """
    Gestor de skills dinámicas con PostgreSQL.

    Usa el mismo engine que PromptStore para compartir
    la conexión a la base de datos.
    """

    def __init__(self, prompt_store: PromptStore):
        self.prompt_store = prompt_store
        log.info("SkillsManager initialized")

    @property
    def async_session(self):
        """Reutiliza la session factory del PromptStore."""
        if not self.prompt_store.async_session:
            raise RuntimeError("PromptStore not initialized. Call prompt_store.initialize() first.")
        return self.prompt_store.async_session

    # ==================== CRUD ====================

    async def create_skill(
        self,
        name: str,
        description: str,
        trigger_pattern: str,
        prompt_template: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Crea una nueva skill.

        Args:
            name: Nombre de la skill
            description: Descripción de lo que hace
            trigger_pattern: Regex o keywords para auto-activación
            prompt_template: Template con {content} como placeholder
            metadata: Metadata adicional (opcional)

        Returns:
            dict con los datos de la skill creada
        """
        skill_id = uuid4()
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        # Validate the trigger pattern is valid regex
        try:
            re.compile(trigger_pattern)
        except re.error as e:
            raise ValueError(f"Invalid trigger_pattern regex: {e}")

        skill = SkillModel(
            skill_id=skill_id,
            name=name,
            slug=slug,
            description=description,
            trigger_pattern=trigger_pattern,
            prompt_template=prompt_template,
            is_active=True,
            usage_count=0,
            created_at=utcnow_naive(),
            metadata_json=metadata or {},
        )

        async with self.async_session() as session:
            session.add(skill)
            await session.commit()

        log.info(f"Skill created: {slug} (trigger: {trigger_pattern})")

        return self._skill_to_dict(skill)

    async def get_skill(self, slug: str) -> Optional[dict]:
        """
        Obtiene una skill por slug.

        Args:
            slug: Slug de la skill

        Returns:
            dict con datos de la skill o None
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(SkillModel).where(SkillModel.slug == slug)
            )
            skill = result.scalar_one_or_none()
            return self._skill_to_dict(skill) if skill else None

    async def list_skills(self) -> List[dict]:
        """Lista todas las skills ordenadas por nombre."""
        async with self.async_session() as session:
            result = await session.execute(
                select(SkillModel).order_by(SkillModel.name)
            )
            skills = result.scalars().all()
            return [self._skill_to_dict(s) for s in skills]

    async def update_skill(self, slug: str, data: dict) -> Optional[dict]:
        """
        Actualiza campos de una skill.

        Args:
            slug: Slug de la skill
            data: Dict con campos a actualizar

        Returns:
            dict con la skill actualizada o None si no existe
        """
        # Validate trigger_pattern if being updated
        if "trigger_pattern" in data:
            try:
                re.compile(data["trigger_pattern"])
            except re.error as e:
                raise ValueError(f"Invalid trigger_pattern regex: {e}")

        # Recalculate slug if name changes
        if "name" in data:
            data["slug"] = re.sub(r'[^a-z0-9]+', '-', data["name"].lower()).strip('-')

        data["updated_at"] = utcnow_naive()

        async with self.async_session() as session:
            result = await session.execute(
                update(SkillModel)
                .where(SkillModel.slug == slug)
                .values(**data)
            )
            await session.commit()

            if result.rowcount == 0:
                return None

        # Return updated skill (use new slug if changed)
        new_slug = data.get("slug", slug)
        return await self.get_skill(new_slug)

    async def delete_skill(self, slug: str) -> bool:
        """
        Elimina una skill.

        Args:
            slug: Slug de la skill

        Returns:
            True si se eliminó, False si no existía
        """
        async with self.async_session() as session:
            result = await session.execute(
                delete(SkillModel).where(SkillModel.slug == slug)
            )
            await session.commit()

            if result.rowcount > 0:
                log.info(f"Skill deleted: {slug}")
                return True
            return False

    async def toggle_skill(self, slug: str) -> Optional[bool]:
        """
        Alterna el estado activo de una skill.

        Args:
            slug: Slug de la skill

        Returns:
            Nuevo estado is_active, o None si no existe
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(SkillModel).where(SkillModel.slug == slug)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return None

            new_state = not skill.is_active

        async with self.async_session() as session:
            await session.execute(
                update(SkillModel)
                .where(SkillModel.slug == slug)
                .values(is_active=new_state, updated_at=utcnow_naive())
            )
            await session.commit()

        log.info(f"Skill toggled: {slug} -> {'active' if new_state else 'inactive'}")
        return new_state

    # ==================== MATCHING & APPLICATION ====================

    async def test_skill(self, slug: str, prompt: str) -> Optional[str]:
        """
        Prueba una skill aplicando su template a un prompt.

        Args:
            slug: Slug de la skill
            prompt: Texto de prueba

        Returns:
            Resultado de aplicar el template, o None si no existe
        """
        skill = await self.get_skill(slug)
        if not skill:
            return None

        return self.apply_skill(skill, prompt)

    async def match_skill(self, prompt_text: str) -> Optional[dict]:
        """
        Busca la primera skill activa cuyo trigger_pattern coincida con el prompt.

        Args:
            prompt_text: Texto del prompt a evaluar

        Returns:
            dict de la skill que coincide, o None
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(SkillModel)
                .where(SkillModel.is_active.is_(True))
                .order_by(SkillModel.name)
            )
            skills = result.scalars().all()

        for skill in skills:
            pattern = skill.trigger_pattern
            if not pattern:
                continue
            try:
                if re.search(pattern, prompt_text, re.IGNORECASE):
                    # Increment usage count
                    await self._increment_usage(skill.slug)
                    return self._skill_to_dict(skill)
            except re.error:
                log.warning(f"Invalid regex in skill '{skill.slug}': {pattern}")
                continue

        return None

    def apply_skill(self, skill: dict, prompt_text: str) -> str:
        """
        Aplica el template de una skill a un prompt.

        El template debe contener {content} como placeholder para
        el texto del prompt original.

        Args:
            skill: dict de la skill (con prompt_template)
            prompt_text: Texto del prompt

        Returns:
            Prompt transformado con el template aplicado
        """
        template = skill.get("prompt_template", "{content}")
        try:
            return template.format(content=prompt_text)
        except KeyError as e:
            log.warning(f"Skill template missing key: {e}")
            return template.replace("{content}", prompt_text)

    # ==================== INTERNAL ====================

    async def _increment_usage(self, slug: str) -> None:
        """Incrementa el contador de uso de una skill."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    update(SkillModel)
                    .where(SkillModel.slug == slug)
                    .values(
                        usage_count=SkillModel.usage_count + 1,
                        updated_at=utcnow_naive(),
                    )
                )
                await session.commit()
        except Exception as e:
            log.error(f"Failed to increment usage for skill '{slug}': {e}")

    def _skill_to_dict(self, skill: SkillModel) -> dict:
        """Convierte un SkillModel a diccionario."""
        return {
            "skill_id": str(skill.skill_id),
            "name": skill.name,
            "slug": skill.slug,
            "description": skill.description,
            "trigger_pattern": skill.trigger_pattern,
            "prompt_template": skill.prompt_template,
            "is_active": skill.is_active,
            "usage_count": skill.usage_count or 0,
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
            "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
            "metadata": skill.metadata_json or {},
        }


# ==================== SINGLETON ====================

_skills_manager: Optional[SkillsManager] = None


def get_skills_manager(prompt_store: Optional[PromptStore] = None) -> SkillsManager:
    """
    Singleton del SkillsManager.

    Requiere prompt_store en la primera invocación para compartir
    la conexión a PostgreSQL.
    """
    global _skills_manager
    if _skills_manager is None:
        if prompt_store is None:
            raise RuntimeError(
                "SkillsManager requires prompt_store on first initialization. "
                "Pass the PromptStore instance."
            )
        _skills_manager = SkillsManager(prompt_store)
    return _skills_manager
