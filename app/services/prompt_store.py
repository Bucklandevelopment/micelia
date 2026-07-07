"""
PromptStore: Almacenamiento y gestión de prompts en PostgreSQL.

Sigue el patrón de EventStore con SQLAlchemy async.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import log
from app.core.time import utcnow_naive
from app.models.base import Base
from app.models.prompt import PromptListModel, PromptModel, SkillModel


class PromptStore:
    """
    Store de prompts con PostgreSQL.
    Gestiona CRUD de prompts, prompt lists y skills.
    """

    def __init__(self):
        self.engine = None
        self.async_session = None

    async def initialize(self):
        """Inicializa conexión y crea tablas"""
        try:
            self.engine = create_async_engine(
                settings.database_url,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                echo=settings.database_echo,
            )

            self.async_session = async_sessionmaker(
                self.engine,
                expire_on_commit=False,
            )

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            log.info("PromptStore inicializado correctamente")

        except Exception as e:
            log.error(f"Error inicializando PromptStore: {e}")
            raise

    async def close(self):
        """Cierra conexiones"""
        if self.engine:
            await self.engine.dispose()

    # ==================== PROMPTS CRUD ====================

    async def create_prompt(
        self,
        content: str,
        category: str = "note",
        priority: int = 5,
        tags: List[str] = None,
        scheduled_at: datetime = None,
        parent_prompt_id: UUID = None,
        correlation_id: UUID = None,
        source: str = "api",
        prefer_paid: bool = False,
        metadata: dict = None,
        status: str = "pending",
        workflow: str = "quick_execute",
        provider_policy: str = "free-first"
    ) -> UUID:
        """Crea un nuevo prompt"""
        prompt_id = uuid4()

        prompt = PromptModel(
            prompt_id=prompt_id,
            content=content,
            category=category,
            priority=priority,
            status=status,
            workflow=workflow,
            provider_policy=provider_policy,
            tags=tags or [],
            scheduled_at=scheduled_at,
            parent_prompt_id=parent_prompt_id,
            correlation_id=correlation_id,
            source=source,
            prefer_paid=prefer_paid,
            metadata_json=metadata or {},
            created_at=utcnow_naive()
        )

        async with self.async_session() as session:
            session.add(prompt)
            await session.commit()

        log.debug(f"Prompt creado: {prompt_id} [{category}]")
        return prompt_id

    async def get_prompt(self, prompt_id: UUID) -> Optional[dict]:
        """Obtiene un prompt por ID"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptModel).where(PromptModel.prompt_id == prompt_id)
            )
            prompt = result.scalar_one_or_none()
            return self._prompt_to_dict(prompt) if prompt else None

    async def update_prompt(self, prompt_id: UUID, **fields) -> bool:
        """Actualiza campos de un prompt"""
        async with self.async_session() as session:
            result = await session.execute(
                update(PromptModel)
                .where(PromptModel.prompt_id == prompt_id)
                .values(**fields)
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_prompt(self, prompt_id: UUID) -> bool:
        """Elimina un prompt"""
        async with self.async_session() as session:
            result = await session.execute(
                delete(PromptModel).where(PromptModel.prompt_id == prompt_id)
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== QUERIES ====================

    async def list_prompts(
        self,
        status: str = None,
        category: str = None,
        tags: List[str] = None,
        source: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Lista prompts con filtros"""
        async with self.async_session() as session:
            query = select(PromptModel)
            count_query = select(func.count(PromptModel.prompt_id))

            conditions = []
            if status:
                conditions.append(PromptModel.status == status)
            if category:
                conditions.append(PromptModel.category == category)
            if source:
                conditions.append(PromptModel.source == source)

            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))

            # Total count
            total_result = await session.execute(count_query)
            total = total_result.scalar()

            # Paginación
            query = query.order_by(
                PromptModel.priority.desc(),
                PromptModel.created_at.desc()
            ).limit(limit).offset(offset)

            result = await session.execute(query)
            prompts = result.scalars().all()

            return {
                "prompts": [self._prompt_to_dict(p) for p in prompts],
                "count": len(prompts),
                "limit": limit,
                "offset": offset,
                "total": total
            }

    async def get_pending_prompts(self, limit: int = 50) -> List[dict]:
        """Obtiene prompts pendientes para el agente de priorización"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptModel)
                .where(PromptModel.status == "pending")
                .order_by(PromptModel.created_at)
                .limit(limit)
            )
            return [self._prompt_to_dict(p) for p in result.scalars().all()]

    async def get_queued_prompts(self, limit: int = 10) -> List[dict]:
        """Obtiene prompts en cola para el executor"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptModel)
                .where(PromptModel.status == "queued")
                .order_by(PromptModel.priority.desc(), PromptModel.created_at)
                .limit(limit)
            )
            return [self._prompt_to_dict(p) for p in result.scalars().all()]

    async def get_scheduled_prompts(self, before: datetime) -> List[dict]:
        """Obtiene prompts programados que deben ejecutarse"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptModel)
                .where(and_(
                    PromptModel.status == "pending",
                    PromptModel.scheduled_at.isnot(None),
                    PromptModel.scheduled_at <= before
                ))
                .order_by(PromptModel.scheduled_at)
            )
            return [self._prompt_to_dict(p) for p in result.scalars().all()]

    # ==================== QUICK NOTES ====================

    async def create_note(self, text: str, tags: List[str] = None) -> UUID:
        """Crea una nota rápida como prompt"""
        # Auto-detectar tags del texto (#tag)
        auto_tags = re.findall(r'#(\w+)', text)
        # Limpiar el texto de hashtags
        clean_text = re.sub(r'#\w+', '', text).strip()
        all_tags = list(set((tags or []) + auto_tags))

        # Auto-detectar categoría de los tags
        category = "note"
        tag_to_category = {
            "work": "work", "trabajo": "work", "laboral": "work",
            "plan": "plan", "proyecto": "project", "project": "project",
            "routine": "routine", "rutina": "routine",
            "personal": "personal",
        }
        for tag in all_tags:
            if tag.lower() in tag_to_category:
                category = tag_to_category[tag.lower()]
                break

        # Auto-detectar prioridad
        priority = 5
        if "urgent" in all_tags or "urgente" in all_tags:
            priority = 10
        elif "low" in all_tags or "baja" in all_tags:
            priority = 2

        return await self.create_prompt(
            content=clean_text or text,
            category=category,
            priority=priority,
            tags=all_tags,
            source="note",
            status="captured"
        )

    # ==================== PROMPT LISTS ====================

    async def create_list(
        self,
        name: str,
        description: str = None,
        category: str = "general",
        content_md: str = ""
    ) -> UUID:
        """Crea una nueva lista de prompts"""
        list_id = uuid4()
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        prompt_list = PromptListModel(
            list_id=list_id,
            name=name,
            slug=slug,
            description=description,
            category=category,
            content_md=content_md,
            created_at=utcnow_naive()
        )

        async with self.async_session() as session:
            session.add(prompt_list)
            await session.commit()

        log.debug(f"PromptList creada: {slug}")
        return list_id

    async def get_list(self, slug: str) -> Optional[dict]:
        """Obtiene una lista por slug"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptListModel).where(PromptListModel.slug == slug)
            )
            pl = result.scalar_one_or_none()
            return self._list_to_dict(pl) if pl else None

    async def update_list(self, slug: str, **fields) -> bool:
        """Actualiza una lista"""
        fields["updated_at"] = utcnow_naive()
        async with self.async_session() as session:
            result = await session.execute(
                update(PromptListModel)
                .where(PromptListModel.slug == slug)
                .values(**fields)
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_list(self, slug: str) -> bool:
        """Elimina una lista"""
        async with self.async_session() as session:
            result = await session.execute(
                delete(PromptListModel).where(PromptListModel.slug == slug)
            )
            await session.commit()
            return result.rowcount > 0

    async def list_all_lists(self) -> List[dict]:
        """Lista todas las prompt lists"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptListModel).order_by(PromptListModel.created_at.desc())
            )
            return [self._list_to_dict(pl) for pl in result.scalars().all()]

    # ==================== STATS ====================

    async def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del sistema de prompts"""
        async with self.async_session() as session:
            # Total
            total_result = await session.execute(
                select(func.count(PromptModel.prompt_id))
            )
            total = total_result.scalar()

            # Por status
            status_result = await session.execute(
                select(PromptModel.status, func.count(PromptModel.prompt_id))
                .group_by(PromptModel.status)
            )
            by_status = dict(status_result.all())

            # Por categoría
            cat_result = await session.execute(
                select(PromptModel.category, func.count(PromptModel.prompt_id))
                .group_by(PromptModel.category)
            )
            by_category = dict(cat_result.all())

            # Completados hoy
            today_start = utcnow_naive().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            completed_result = await session.execute(
                select(func.count(PromptModel.prompt_id))
                .where(and_(
                    PromptModel.status == "completed",
                    PromptModel.completed_at >= today_start
                ))
            )
            completed_today = completed_result.scalar()

            # Tokens totales
            tokens_result = await session.execute(
                select(
                    func.coalesce(func.sum(PromptModel.tokens_input), 0),
                    func.coalesce(func.sum(PromptModel.tokens_output), 0),
                    func.coalesce(func.sum(PromptModel.cost_usd), 0)
                )
            )
            tokens_row = tokens_result.one()

            # Latencia media
            latency_result = await session.execute(
                select(func.avg(PromptModel.latency_ms))
                .where(PromptModel.latency_ms.isnot(None))
            )
            avg_latency = latency_result.scalar() or 0

            return {
                "total": total,
                "by_status": by_status,
                "by_category": by_category,
                "completed_today": completed_today,
                "total_tokens_input": tokens_row[0],
                "total_tokens_output": tokens_row[1],
                "total_cost_usd": float(tokens_row[2]),
                "avg_latency_ms": round(avg_latency, 2)
            }

    # ==================== CLASSIFICATION ====================

    async def classify_prompt(self, prompt_id: UUID, category: str, tags: List[str] = None,
                               workflow: str = "quick_execute", provider_policy: str = "free-first") -> bool:
        """Clasifica un prompt captured -> classified"""
        fields = {
            "status": "classified",
            "category": category,
            "workflow": workflow,
            "provider_policy": provider_policy,
            "classified_at": utcnow_naive(),
        }
        if tags:
            fields["tags"] = tags
        return await self.update_prompt(prompt_id, **fields)

    async def stage_prompt(self, prompt_id: UUID) -> bool:
        """Mueve un prompt a staging para acción manual"""
        return await self.update_prompt(
            prompt_id,
            status="staged",
            staged_at=utcnow_naive()
        )

    async def approve_staged(self, prompt_id: UUID) -> bool:
        """Aprueba un prompt en staging -> pending"""
        return await self.update_prompt(prompt_id, status="pending")

    async def archive_prompt(self, prompt_id: UUID) -> bool:
        """Archiva un prompt completado"""
        return await self.update_prompt(
            prompt_id,
            status="archived",
            archived_at=utcnow_naive()
        )

    # ==================== PROMOTION ====================

    async def promote_to_list(self, prompt_id: UUID, list_slug: str) -> bool:
        """Promueve un prompt a un item de una lista existente"""
        prompt = await self.get_prompt(prompt_id)
        if not prompt:
            return False

        # Append content to the list's markdown
        prompt_list = await self.get_list(list_slug)
        if not prompt_list:
            return False

        new_content = prompt_list["content_md"] + f"\n- [ ] {prompt['content']}"
        await self.update_list(list_slug, content_md=new_content)

        return await self.update_prompt(
            prompt_id,
            status="promoted",
            promoted_to="list",
            promoted_ref=list_slug
        )

    async def promote_to_skill(self, prompt_id: UUID, name: str, trigger_pattern: str) -> Optional[UUID]:
        """Promueve un prompt a una skill dinámica"""
        prompt = await self.get_prompt(prompt_id)
        if not prompt:
            return None

        # Create skill from prompt content as template
        skill_id = uuid4()
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        skill = SkillModel(
            skill_id=skill_id,
            name=name,
            slug=slug,
            description=f"Auto-generated from prompt {prompt_id}",
            trigger_pattern=trigger_pattern,
            prompt_template=prompt["content"],
            is_active=True,
            created_at=utcnow_naive()
        )

        async with self.async_session() as session:
            session.add(skill)
            await session.commit()

        await self.update_prompt(
            prompt_id,
            status="promoted",
            promoted_to="skill",
            promoted_ref=slug
        )

        return skill_id

    async def promote_to_mcp(self, prompt_id: UUID) -> bool:
        """Marca un prompt para generación de MCP server"""
        return await self.update_prompt(
            prompt_id,
            status="promoted",
            promoted_to="mcp"
        )

    # ==================== INBOX / STAGING QUERIES ====================

    async def get_captured_prompts(self, limit: int = 50) -> List[dict]:
        """Obtiene prompts recién capturados (inbox)"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptModel)
                .where(PromptModel.status == "captured")
                .order_by(PromptModel.created_at.desc())
                .limit(limit)
            )
            return [self._prompt_to_dict(p) for p in result.scalars().all()]

    async def get_staged_prompts(self, limit: int = 50) -> List[dict]:
        """Obtiene prompts en staging"""
        async with self.async_session() as session:
            result = await session.execute(
                select(PromptModel)
                .where(PromptModel.status == "staged")
                .order_by(PromptModel.priority.desc(), PromptModel.created_at.desc())
                .limit(limit)
            )
            return [self._prompt_to_dict(p) for p in result.scalars().all()]

    async def get_archived_prompts(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Obtiene prompts archivados con paginación"""
        async with self.async_session() as session:
            count_result = await session.execute(
                select(func.count(PromptModel.prompt_id))
                .where(PromptModel.status == "archived")
            )
            total = count_result.scalar()

            result = await session.execute(
                select(PromptModel)
                .where(PromptModel.status == "archived")
                .order_by(PromptModel.archived_at.desc())
                .limit(limit).offset(offset)
            )
            return {
                "prompts": [self._prompt_to_dict(p) for p in result.scalars().all()],
                "total": total,
                "limit": limit,
                "offset": offset
            }

    # ==================== SERIALIZERS ====================

    def _prompt_to_dict(self, prompt: PromptModel) -> dict:
        """Convierte modelo a diccionario"""
        return {
            "prompt_id": str(prompt.prompt_id),
            "content": prompt.content,
            "category": prompt.category,
            "priority": prompt.priority,
            "status": prompt.status,
            "model_used": prompt.model_used,
            "provider_used": prompt.provider_used,
            "prefer_paid": prompt.prefer_paid,
            "review_score": prompt.review_score,
            "iterations": prompt.iterations,
            "output": prompt.output,
            "error": prompt.error,
            "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
            "scheduled_at": prompt.scheduled_at.isoformat() if prompt.scheduled_at else None,
            "processing_at": prompt.processing_at.isoformat() if prompt.processing_at else None,
            "completed_at": prompt.completed_at.isoformat() if prompt.completed_at else None,
            "parent_prompt_id": str(prompt.parent_prompt_id) if prompt.parent_prompt_id else None,
            "correlation_id": str(prompt.correlation_id) if prompt.correlation_id else None,
            "tags": prompt.tags or [],
            "metadata": prompt.metadata_json or {},
            "source": prompt.source,
            "tokens_input": prompt.tokens_input or 0,
            "tokens_output": prompt.tokens_output or 0,
            "latency_ms": prompt.latency_ms,
            "cost_usd": prompt.cost_usd,
            "workflow": prompt.workflow,
            "classified_at": prompt.classified_at.isoformat() if prompt.classified_at else None,
            "staged_at": prompt.staged_at.isoformat() if prompt.staged_at else None,
            "archived_at": prompt.archived_at.isoformat() if prompt.archived_at else None,
            "promoted_to": prompt.promoted_to,
            "promoted_ref": prompt.promoted_ref,
            "provider_policy": prompt.provider_policy,
        }

    def _list_to_dict(self, pl: PromptListModel) -> dict:
        """Convierte modelo de lista a diccionario"""
        return {
            "list_id": str(pl.list_id),
            "name": pl.name,
            "slug": pl.slug,
            "description": pl.description,
            "category": pl.category,
            "content_md": pl.content_md,
            "is_active": pl.is_active,
            "created_at": pl.created_at.isoformat() if pl.created_at else None,
            "updated_at": pl.updated_at.isoformat() if pl.updated_at else None,
            "metadata": pl.metadata_json or {}
        }
