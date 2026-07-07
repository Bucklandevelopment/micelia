"""
UserStore: persistencia de cuentas de usuario en PostgreSQL.

Sigue el mismo patrón que PromptStore/EventStore (SQLAlchemy async + async_sessionmaker,
degradación elegante sin base de datos). Es la capa de datos del funnel de registro;
la verificación de contraseña y la emisión de JWT viven en la capa de API (auth.py).
"""

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
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
from app.models.user import UserModel


class DuplicateEmailError(ValueError):
    """El email ya está registrado."""


class UserStore:
    """Almacena y consulta cuentas de usuario (email único + password hasheado)."""

    def __init__(self, database_url: Optional[str] = None):
        self._database_url = database_url or settings.database_url
        self.engine: Optional[AsyncEngine] = None
        self.async_session: Optional[async_sessionmaker[AsyncSession]] = None

    def _session(self) -> AsyncSession:
        """Abre una sesión; falla claro si no se llamó a initialize()."""
        if self.async_session is None:
            raise RuntimeError("UserStore no inicializado — llama a initialize() primero")
        return self.async_session()

    async def initialize(self) -> None:
        """Crea el engine async, la fábrica de sesiones y la tabla `users`."""
        self.engine = create_async_engine(
            self._database_url,
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
        log.info("UserStore inicializado correctamente")

    async def close(self) -> None:
        """Cierra el engine."""
        if self.engine:
            await self.engine.dispose()

    @staticmethod
    def _to_dict(user: UserModel, *, include_hash: bool = False) -> Dict[str, Any]:
        """Serializa un UserModel. Excluye el hash salvo que se pida explícitamente."""
        data: Dict[str, Any] = {
            "user_id": str(user.user_id),
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "plan_code": user.plan_code,
            "stripe_customer_id": user.stripe_customer_id,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }
        if include_hash:
            data["password_hash"] = user.password_hash
        return data

    async def create_user(
        self, email: str, password_hash: str, plan_code: str = "free"
    ) -> Dict[str, Any]:
        """
        Crea un usuario. `email` se normaliza a minúsculas/trim.
        Lanza DuplicateEmailError si el email ya existe.
        Devuelve el dict público (sin hash).
        """
        normalized = email.strip().lower()
        async with self._session() as session:
            existing = await session.execute(
                select(UserModel).where(UserModel.email == normalized)
            )
            if existing.scalar_one_or_none() is not None:
                raise DuplicateEmailError(normalized)

            user = UserModel(
                user_id=uuid4(),
                email=normalized,
                password_hash=password_hash,
                plan_code=plan_code,
                is_active=True,
                is_verified=False,
                created_at=utcnow_naive(),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            log.info(f"Usuario registrado: {normalized}")
            return self._to_dict(user)

    async def get_user_by_email(
        self, email: str, *, include_hash: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Busca por email (normalizado). Con include_hash devuelve el password_hash."""
        normalized = email.strip().lower()
        async with self._session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.email == normalized)
            )
            user = result.scalar_one_or_none()
            return self._to_dict(user, include_hash=include_hash) if user else None

    async def get_user_by_id(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Busca por user_id."""
        async with self._session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            return self._to_dict(user) if user else None

    async def touch_last_login(self, user_id: UUID) -> None:
        """Actualiza last_login_at al momento actual."""
        async with self._session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                # SQLAlchemy classic Column setter — mypy lo tipa como Column[datetime].
                user.last_login_at = utcnow_naive()  # type: ignore[assignment]
                await session.commit()
