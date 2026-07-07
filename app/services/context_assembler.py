"""
Context Layer Assembler: construye el prompt final desde 5 capas de contexto.

Capas:
- 0: Identidad (quién es el usuario, objetivos, tono, restricciones, presupuesto)
- 1: Dominio (rutina diaria, trabajo, corto plazo, proyectos, personal)
- 2: Contexto Temporal (hora, calendario, eventos próximos, energía del sistema)
- 3: Contexto Operativo (skills activas, MCP servers, herramientas, providers)
- 4: Contexto Vivo (nota actual, prompts relacionados, correlación, archivos MD)
"""

import os
from datetime import datetime, timezone
from typing import List, Optional

from app.core.config import settings


class ContextLayer:
    """Representa una capa de contexto"""
    def __init__(self, level: int, name: str, content: str = ""):
        self.level = level
        self.name = name
        self.content = content

    def __repr__(self):
        return f"Layer({self.level}: {self.name}, {len(self.content)} chars)"


class ContextAssembler:
    """
    Ensambla el prompt final combinando las 5 capas de contexto.
    """

    def __init__(self, prompt_store=None, skills_manager=None):
        self.prompt_store = prompt_store
        self.skills_manager = skills_manager
        self._identity_cache: Optional[str] = None

    async def assemble(self, prompt: dict, include_layers: Optional[List[int]] = None) -> str:
        """
        Ensambla el prompt final con todas las capas aplicables.

        Args:
            prompt: dict con el prompt a enriquecer
            include_layers: lista de capas a incluir (0-4). None = todas

        Returns:
            Prompt ensamblado con contexto
        """
        layers = include_layers or [0, 1, 2, 3, 4]
        assembled_layers: List[ContextLayer] = []

        if 0 in layers:
            assembled_layers.append(await self._layer_0_identity())
        if 1 in layers:
            assembled_layers.append(await self._layer_1_domain(prompt))
        if 2 in layers:
            assembled_layers.append(self._layer_2_temporal())
        if 3 in layers:
            assembled_layers.append(await self._layer_3_operative())
        if 4 in layers:
            assembled_layers.append(await self._layer_4_live(prompt))

        # Filtrar capas vacías
        active_layers = [layer for layer in assembled_layers if layer.content.strip()]

        if not active_layers:
            return prompt.get("content", "")

        # Construir prompt final
        parts = []
        for layer in active_layers:
            parts.append(f"[{layer.name}]\n{layer.content}")

        context_block = "\n\n".join(parts)
        user_content = prompt.get("content", "")

        return f"""## Context
{context_block}

## Task
{user_content}"""

    # === Layer 0: Identity ===
    async def _layer_0_identity(self) -> ContextLayer:
        """Capa de identidad del usuario"""
        if self._identity_cache:
            return ContextLayer(0, "Identity", self._identity_cache)

        identity_parts = []

        # Load from cowork.md if exists
        cowork_path = os.path.join(os.getcwd(), "cowork.md")
        if os.path.exists(cowork_path):
            try:
                with open(cowork_path, "r") as f:
                    content = f.read()
                # Extract first section as identity context (up to 500 chars)
                lines = content.split("\n")[:20]
                identity_parts.append("User context from cowork.md:")
                identity_parts.append("\n".join(lines))
            except Exception:
                pass

        # Load identity from settings or environment
        identity_parts.append(f"System: {settings.app_name}")
        identity_parts.append(f"Environment: {settings.environment}")

        content = "\n".join(identity_parts)
        self._identity_cache = content
        return ContextLayer(0, "Identity", content)

    # === Layer 1: Domain ===
    async def _layer_1_domain(self, prompt: dict) -> ContextLayer:
        """Capa de dominio: carga la lista MD relevante para la categoría"""
        category = prompt.get("category", "note")
        parts = []

        # Map category to prompt list slug
        category_to_list = {
            "routine": "rutina-diaria",
            "work": "laboral",
            "plan": "plan-corto-plazo",
            "short-term": "plan-corto-plazo",
            "project": "proyectos",
        }

        list_slug = category_to_list.get(category)
        if list_slug:
            list_path = os.path.join(settings.prompt_lists_dir, f"{list_slug}.md")
            if os.path.exists(list_path):
                try:
                    with open(list_path, "r") as f:
                        content = f.read()
                    # Skip frontmatter
                    if content.startswith("---"):
                        end = content.find("---", 3)
                        if end > 0:
                            content = content[end + 3:].strip()
                    parts.append(f"Active list ({list_slug}):")
                    # Limit to 1000 chars
                    parts.append(content[:1000])
                except Exception:
                    pass

        return ContextLayer(1, "Domain", "\n".join(parts))

    # === Layer 2: Temporal ===
    def _layer_2_temporal(self) -> ContextLayer:
        """Capa temporal: hora actual, día de la semana"""
        now = datetime.now(timezone.utc)
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        parts = [
            f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"Day: {day_names[now.weekday()]}",
        ]

        # Time-of-day context
        hour = now.hour
        if 6 <= hour < 12:
            parts.append("Period: Morning")
        elif 12 <= hour < 14:
            parts.append("Period: Midday")
        elif 14 <= hour < 18:
            parts.append("Period: Afternoon")
        elif 18 <= hour < 22:
            parts.append("Period: Evening")
        else:
            parts.append("Period: Night")

        return ContextLayer(2, "Temporal", "\n".join(parts))

    # === Layer 3: Operative ===
    async def _layer_3_operative(self) -> ContextLayer:
        """Capa operativa: skills activas, providers disponibles"""
        parts = []

        # Active skills
        if self.skills_manager:
            try:
                skills = self.skills_manager.list_skills()
                active = [s for s in skills if s.get("is_active")]
                if active:
                    names = [s["name"] for s in active[:10]]
                    parts.append(f"Active skills: {', '.join(names)}")
            except Exception:
                pass

        # Available providers
        parts.append(f"Default model: {settings.ollama_default_model}")
        if settings.openai_api_key:
            parts.append("Provider: OpenAI (paid) available")
        if settings.anthropic_api_key:
            parts.append("Provider: Anthropic (paid) available")

        return ContextLayer(3, "Operative", "\n".join(parts))

    # === Layer 4: Live ===
    async def _layer_4_live(self, prompt: dict) -> ContextLayer:
        """Capa viva: prompts relacionados, correlación"""
        parts = []

        # Related prompts by correlation_id
        correlation_id = prompt.get("correlation_id")
        if correlation_id and self.prompt_store:
            try:
                related = await self.prompt_store.list_prompts(limit=5)
                related_prompts = [
                    p for p in related.get("prompts", [])
                    if p.get("correlation_id") == correlation_id
                    and p.get("prompt_id") != prompt.get("prompt_id")
                ]
                if related_prompts:
                    parts.append("Related prompts:")
                    for rp in related_prompts[:3]:
                        parts.append(f"  - [{rp['status']}] {rp['content'][:100]}")
            except Exception:
                pass

        # Tags context
        tags = prompt.get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        return ContextLayer(4, "Live", "\n".join(parts))


# Singleton
_assembler: Optional[ContextAssembler] = None

def get_context_assembler(prompt_store=None, skills_manager=None) -> ContextAssembler:
    global _assembler
    if _assembler is None:
        _assembler = ContextAssembler(prompt_store, skills_manager)
    return _assembler
