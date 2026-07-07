"""
Modelos de datos para el sistema de prompts de Micelia.
"""

from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.time import utcnow_naive
from app.models.base import Base


class PromptStatus(str, Enum):
    CAPTURED = "captured"      # just arrived from UI/API
    CLASSIFIED = "classified"  # taxonomy agent processed it
    STAGED = "staged"          # in staging area, awaiting user action
    PENDING = "pending"        # approved for execution queue
    QUEUED = "queued"          # prioritizer moved to execution queue
    PROCESSING = "processing"  # executor working on it
    COMPLETED = "completed"    # done
    FAILED = "failed"          # error
    REVIEWED = "reviewed"      # reviewer approved output
    ARCHIVED = "archived"      # moved to long-term storage
    PROMOTED = "promoted"      # converted to list/skill/MCP
    DRAFT = "draft"            # saved but not submitted


class PromptCategory(str, Enum):
    PLAN = "plan"
    SHORT_TERM = "short-term"
    WORK = "work"
    PERSONAL = "personal"
    ROUTINE = "routine"
    NOTE = "note"
    PROJECT = "project"


class PromptModel(Base):
    """Modelo para prompts individuales"""

    __tablename__ = "prompts"

    # Identificación
    prompt_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Contenido
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True, default="note")
    priority = Column(Integer, default=5, index=True)  # 0=low, 5=normal, 10=urgent
    status = Column(String(20), nullable=False, index=True, default="pending")

    # Ejecución
    model_used = Column(String(100))
    provider_used = Column(String(50))
    prefer_paid = Column(Boolean, default=False)
    review_score = Column(Float)
    iterations = Column(Integer, default=0)
    output = Column(Text)
    error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    scheduled_at = Column(DateTime, index=True)
    processing_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Jerarquía
    parent_prompt_id = Column(PGUUID(as_uuid=True), ForeignKey("prompts.prompt_id"), index=True)
    correlation_id = Column(PGUUID(as_uuid=True), index=True)

    # Metadata
    tags = Column(JSON, default=[])
    metadata_json = Column(JSON, default={})
    source = Column(String(50), default="api")  # api, note, schedule, list, calendar

    # Prompt OS workflow
    workflow = Column(String(50), default="quick_execute")  # quick_execute, reviewed_execute, full_pipeline
    classified_at = Column(DateTime)
    staged_at = Column(DateTime)
    archived_at = Column(DateTime)
    promoted_to = Column(String(50))  # list, skill, mcp
    promoted_ref = Column(String(200))  # slug of target list/skill/mcp
    provider_policy = Column(String(50), default="free-first")  # free-first, paid-for-work, critical-reviewed

    # Consumo
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency_ms = Column(Float)
    cost_usd = Column(Float)

    __table_args__ = (
        Index('ix_prompts_status_priority', 'status', 'priority'),
        Index('ix_prompts_category_status', 'category', 'status'),
        Index('ix_prompts_scheduled', 'scheduled_at', 'status'),
    )


class PromptListModel(Base):
    """Modelo para listas de prompts (archivos MD dinámicos)"""

    __tablename__ = "prompt_lists"

    list_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(200), nullable=False, unique=True)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text)
    category = Column(String(50), default="general")
    content_md = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, onupdate=utcnow_naive)
    metadata_json = Column(JSON, default={})


class SkillModel(Base):
    """Modelo para skills dinámicas"""

    __tablename__ = "skills"

    skill_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(200), nullable=False, unique=True)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text)
    trigger_pattern = Column(String(500))  # regex o keywords para auto-trigger
    prompt_template = Column(Text)  # template con {content} placeholder
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, onupdate=utcnow_naive)
    metadata_json = Column(JSON, default={})
