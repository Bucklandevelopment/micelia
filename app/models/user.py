"""
Modelo de usuario para el funnel de registro de Micelia.

Primer nodo del embudo register → login → micelia (subdominios de idmmortality.com).
`plan_code` y `stripe_customer_id` quedan preparados para la fase de monetización
(Slice 3), pero este modelo NO implementa cobro: solo identidad multi-usuario.
"""

from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.time import utcnow_naive
from app.models.base import Base


class UserModel(Base):
    """Cuenta de usuario registrada (email + password hasheado)."""

    __tablename__ = "users"

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(320), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    # Estado de la cuenta
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Preparado para monetización (Slice 3) — sin lógica de cobro todavía
    plan_code = Column(String(32), default="free", nullable=False)
    stripe_customer_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
