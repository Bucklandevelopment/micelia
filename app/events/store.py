"""
Event Store: Almacenamiento inmutable de eventos del Panel IDM.

Implementa Event Sourcing con PostgreSQL.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, and_, func, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import log
from app.core.time import utcnow_naive
from app.models.base import Base


class IdmEventModel(Base):
    """Modelo SQLAlchemy para eventos del Panel IDM"""

    __tablename__ = "idm_events"

    # Identificación
    event_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    correlation_id = Column(PGUUID(as_uuid=True), index=True)
    causation_id = Column(PGUUID(as_uuid=True), index=True)

    # Temporal
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    occurred_at = Column(DateTime, index=True)
    processed_at = Column(DateTime)

    # Clasificación
    category = Column(String(50), nullable=False, index=True)
    subcategory = Column(String(50), index=True)
    source = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)

    # Actor
    user_id = Column(PGUUID(as_uuid=True), index=True)
    device_id = Column(String(100))
    session_id = Column(PGUUID(as_uuid=True))

    # Contenido
    payload = Column(JSON, default={})
    event_metadata = Column(JSON, default={})

    # Cómputo
    compute_provider = Column(String(50))
    compute_model = Column(String(100))
    compute_latency_ms = Column(Float)
    compute_cost_usd = Column(Float)
    energy_cost_kwh = Column(Float)

    # Versionado
    version = Column(Integer, default=1)
    schema_version = Column(String(20), default="1.0.0")
    tags = Column(JSON, default=[])

    # Índices compuestos
    __table_args__ = (
        Index('ix_events_user_category_time', 'user_id', 'category', 'timestamp'),
        Index('ix_events_source_type', 'source', 'event_type'),
        Index('ix_events_correlation', 'correlation_id', 'timestamp'),
    )


class EventStore:
    """
    Store de eventos con persistencia en PostgreSQL.
    Append-only para garantizar inmutabilidad.
    """

    def __init__(self):
        self.engine: AsyncEngine = None  # type: ignore[assignment]
        self.async_session: async_sessionmaker[AsyncSession] = None  # type: ignore[assignment]

    async def initialize(self):
        """Inicializa conexión y crea tablas si no existen"""
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

            # Crear tablas
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            log.info("Event Store inicializado correctamente")

        except Exception as e:
            log.error(f"Error inicializando Event Store: {e}")
            raise

    async def close(self):
        """Cierra conexiones"""
        if self.engine:
            await self.engine.dispose()

    async def append_event(
        self,
        category: str,
        source: str,
        action: str,
        event_type: str,
        payload: Optional[dict] = None,
        subcategory: Optional[str] = None,
        event_metadata: Optional[dict] = None,
        tags: Optional[List[str]] = None,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        compute_provider: Optional[str] = None,
        compute_model: Optional[str] = None,
        compute_latency_ms: Optional[float] = None,
        compute_cost_usd: Optional[float] = None
    ) -> UUID:
        """
        Añade un evento al store (append-only).

        Returns:
            UUID del evento creado
        """
        # Compat: normaliza el source-id legacy 'idm-core' -> 'micelia'.
        # Decisión documentada en docs/REBRAND_MICELIA.md §4 (T1.4).
        if source == "idm-core":
            import warnings
            warnings.warn(
                "source='idm-core' está deprecado, usa 'micelia'. Será removido en v0.2.",
                DeprecationWarning,
                stacklevel=2,
            )
            source = "micelia"

        event_id = uuid4()

        event = IdmEventModel(
            event_id=event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            timestamp=utcnow_naive(),
            processed_at=utcnow_naive(),
            category=category,
            subcategory=subcategory,
            source=source,
            action=action,
            event_type=event_type,
            user_id=user_id,
            payload=payload or {},
            event_metadata=event_metadata or {},
            tags=tags or [],
            compute_provider=compute_provider,
            compute_model=compute_model,
            compute_latency_ms=compute_latency_ms,
            compute_cost_usd=compute_cost_usd
        )

        async with self.async_session() as session:
            session.add(event)
            await session.commit()

        log.debug(f"Evento creado: {event_id} ({event_type})")
        return event_id

    async def query_events(
        self,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """
        Consulta eventos con filtros.
        """
        async with self.async_session() as session:
            query = select(IdmEventModel)

            conditions = []
            if category:
                conditions.append(IdmEventModel.category == category)
            if subcategory:
                conditions.append(IdmEventModel.subcategory == subcategory)
            if source:
                conditions.append(IdmEventModel.source == source)
            if event_type:
                conditions.append(IdmEventModel.event_type == event_type)
            if since:
                conditions.append(IdmEventModel.timestamp >= since)
            if until:
                conditions.append(IdmEventModel.timestamp <= until)
            if user_id:
                conditions.append(IdmEventModel.user_id == user_id)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(IdmEventModel.timestamp.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            events = result.scalars().all()

            return [self._event_to_dict(e) for e in events]

    async def get_by_correlation(self, correlation_id: UUID) -> List[dict]:
        """Obtiene eventos por correlation_id"""
        async with self.async_session() as session:
            query = select(IdmEventModel).where(
                IdmEventModel.correlation_id == correlation_id
            ).order_by(IdmEventModel.timestamp)

            result = await session.execute(query)
            events = result.scalars().all()

            return [self._event_to_dict(e) for e in events]

    async def get_timeline(
        self,
        date: datetime,
        categories: Optional[List[str]] = None
    ) -> List[dict]:
        """Obtiene timeline de un día"""
        start = datetime.combine(date.date(), datetime.min.time())
        end = start + timedelta(days=1)

        async with self.async_session() as session:
            query = select(IdmEventModel).where(
                and_(
                    IdmEventModel.timestamp >= start,
                    IdmEventModel.timestamp < end
                )
            )

            if categories:
                query = query.where(IdmEventModel.category.in_(categories))

            query = query.order_by(IdmEventModel.timestamp)

            result = await session.execute(query)
            events = result.scalars().all()

            return [self._event_to_dict(e) for e in events]

    async def get_stats(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Obtiene estadísticas de eventos"""
        async with self.async_session() as session:
            # Total de eventos
            total_query = select(func.count(IdmEventModel.event_id))
            if since:
                total_query = total_query.where(IdmEventModel.timestamp >= since)
            total_result = await session.execute(total_query)
            total = total_result.scalar()

            # Por categoría
            cat_query = select(
                IdmEventModel.category,
                func.count(IdmEventModel.event_id)
            ).group_by(IdmEventModel.category)
            if since:
                cat_query = cat_query.where(IdmEventModel.timestamp >= since)
            cat_result = await session.execute(cat_query)
            # Row es tupla en runtime; el stub de SQLAlchemy no lo refleja.
            by_category: Dict[str, int] = dict(cat_result.all())  # type: ignore[arg-type]

            # Por fuente
            source_query = select(
                IdmEventModel.source,
                func.count(IdmEventModel.event_id)
            ).group_by(IdmEventModel.source)
            if since:
                source_query = source_query.where(IdmEventModel.timestamp >= since)
            source_result = await session.execute(source_query)
            # Row es tupla en runtime; el stub de SQLAlchemy no lo refleja.
            by_source: Dict[str, int] = dict(source_result.all())  # type: ignore[arg-type]

            return {
                "total_events": total,
                "by_category": by_category,
                "by_source": by_source
            }

    def _event_to_dict(self, event: IdmEventModel) -> dict:
        """Convierte modelo a diccionario"""
        return {
            "event_id": str(event.event_id),
            "correlation_id": str(event.correlation_id) if event.correlation_id else None,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "category": event.category,
            "subcategory": event.subcategory,
            "source": event.source,
            "action": event.action,
            "event_type": event.event_type,
            "payload": event.payload,
            "metadata": event.event_metadata,
            "tags": event.tags,
            "compute_provider": event.compute_provider,
            "compute_model": event.compute_model,
            "compute_latency_ms": event.compute_latency_ms
        }
