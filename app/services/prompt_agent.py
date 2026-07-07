"""
Agente de priorización de prompts.

Background task que cada N segundos escanea prompts pendientes,
calcula prioridad, agrupa relacionados, y los mueve a la cola.

Also runs the Taxonomy agent on newly captured prompts to auto-classify
them before priority calculation.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.core.config import settings
from app.core.logging import log
from app.services.agents.prompt_os_agents import get_prompt_os_runner


class PromptPrioritizationAgent:
    """
    Agente que prioriza prompts cada 5 segundos.
    Escanea captured → taxonomy → pending → calcula prioridad → queued.
    """

    def __init__(self, prompt_store, event_bus=None):
        self._store = prompt_store
        self._event_bus = event_bus
        self._task: Optional[asyncio.Task] = None
        self._taxonomy_runner = None
        self.interval = settings.prompt_agent_interval
        self.running = False
        self.last_scan: Optional[datetime] = None
        self.last_pending_count = 0

    async def start(self):
        """Inicia el loop de priorización"""
        if self._task and not self._task.done():
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info(f"PromptAgent iniciado (intervalo: {self.interval}s)")

    async def stop(self):
        """Detiene el agente"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("PromptAgent detenido")

    async def _run_loop(self):
        """Loop principal"""
        while self.running:
            try:
                await self._classify_captured()
                await self._process_pending()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"PromptAgent error: {e}")
                await asyncio.sleep(self.interval)

    async def _classify_captured(self):
        """
        Run the Taxonomy agent on newly captured prompts to auto-classify
        them before they enter the prioritization pipeline.

        Captured prompts get category, tags, workflow, provider_policy,
        and a suggested priority from the Taxonomy agent, then move to
        'pending' status for the normal prioritization loop.
        """
        if not hasattr(self._store, "get_captured_prompts"):
            return

        captured = await self._store.get_captured_prompts(limit=20)
        if not captured:
            return

        runner = get_prompt_os_runner()

        for prompt in captured:
            try:
                taxonomy_result = await runner.run_taxonomy(prompt)
                taxonomy_data = taxonomy_result.get("data", {})

                update_fields: dict[str, Any] = {
                    "status": "pending",
                }

                # Apply taxonomy classifications to the prompt
                if taxonomy_data.get("category"):
                    update_fields["category"] = taxonomy_data["category"]
                if taxonomy_data.get("tags"):
                    # Merge with existing tags, deduplicate
                    existing_tags = prompt.get("tags", []) or []
                    merged_tags = list(
                        dict.fromkeys(existing_tags + taxonomy_data["tags"])
                    )
                    update_fields["tags"] = merged_tags
                if taxonomy_data.get("priority") is not None:
                    update_fields["priority"] = taxonomy_data["priority"]
                if taxonomy_data.get("workflow"):
                    update_fields["workflow"] = taxonomy_data["workflow"]
                if taxonomy_data.get("provider_policy"):
                    update_fields["provider_policy"] = taxonomy_data["provider_policy"]
                if taxonomy_data.get("needs_staging") is not None:
                    update_fields["needs_staging"] = taxonomy_data["needs_staging"]

                await self._store.update_prompt(
                    prompt["prompt_id"],
                    **update_fields,
                )

                log.debug(
                    f"Taxonomy classified prompt {prompt['prompt_id']}: "
                    f"category={taxonomy_data.get('category')}, "
                    f"priority={taxonomy_data.get('priority')}, "
                    f"workflow={taxonomy_data.get('workflow')}"
                )

            except Exception as e:
                # If taxonomy fails, still move to pending with defaults
                log.warning(
                    f"Taxonomy classification failed for prompt "
                    f"{prompt['prompt_id']}: {e}. Moving to pending with defaults."
                )
                await self._store.update_prompt(
                    prompt["prompt_id"],
                    status="pending",
                )

        if captured:
            log.debug(
                f"PromptAgent: {len(captured)} captured prompts classified by Taxonomy"
            )

    async def _process_pending(self):
        """Procesa prompts pendientes"""
        pending = await self._store.get_pending_prompts(limit=50)
        self.last_scan = datetime.now(timezone.utc)
        self.last_pending_count = len(pending)

        if not pending:
            return

        for prompt in pending:
            priority = self._calculate_priority(prompt)
            group_id = self._find_group(prompt, pending)

            update_fields = {
                "priority": priority,
                "status": "queued"
            }
            if group_id:
                update_fields["correlation_id"] = group_id

            await self._store.update_prompt(
                prompt["prompt_id"],
                **update_fields
            )

            # Publicar evento
            if self._event_bus:
                try:
                    await self._event_bus.publish("idm.prompts", {
                        "type": "prompt.queued",
                        "prompt_id": prompt["prompt_id"],
                        "priority": priority,
                        "category": prompt["category"]
                    })
                except Exception:
                    pass  # Event bus puede no estar disponible

        log.debug(f"PromptAgent: {len(pending)} prompts priorizados")

    def _calculate_priority(self, prompt: dict) -> int:
        """Calcula prioridad basada en reglas"""
        priority = prompt.get("priority", 5)

        # Categoría
        category_boost = {
            "work": 2, "plan": 1, "project": 1,
            "routine": -1, "personal": 0, "note": 0
        }
        priority += category_boost.get(prompt.get("category", ""), 0)

        # Tags
        tags = prompt.get("tags", [])
        if "urgent" in tags or "urgente" in tags:
            priority += 5
        if "important" in tags or "importante" in tags:
            priority += 3
        if "low" in tags or "baja" in tags:
            priority -= 3

        # Scheduled pronto
        if prompt.get("scheduled_at"):
            try:
                scheduled = datetime.fromisoformat(prompt["scheduled_at"])
                if scheduled.tzinfo is None:
                    scheduled = scheduled.replace(tzinfo=timezone.utc)
                time_until = (scheduled - datetime.now(timezone.utc)).total_seconds()
                if time_until < 300:  # < 5 minutos
                    priority += 5
                elif time_until < 3600:  # < 1 hora
                    priority += 3
            except (ValueError, TypeError):
                pass

        # Antigüedad (boost leve para prompts viejos)
        if prompt.get("created_at"):
            try:
                created = datetime.fromisoformat(prompt["created_at"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
                if age_hours > 24:
                    priority += 1
                if age_hours > 72:
                    priority += 2
            except (ValueError, TypeError):
                pass

        return max(0, min(10, priority))

    def _find_group(self, prompt: dict, all_pending: list) -> Optional[str]:
        """Agrupa prompts relacionados"""
        # Si ya tiene correlation_id, usarlo
        if prompt.get("correlation_id"):
            return prompt["correlation_id"]

        # Buscar prompts con tags similares
        tags = set(prompt.get("tags", []))
        if not tags:
            return None

        for other in all_pending:
            if other["prompt_id"] == prompt["prompt_id"]:
                continue
            other_tags = set(other.get("tags", []))
            # Si comparten 2+ tags, agrupar
            if len(tags & other_tags) >= 2:
                return other.get("correlation_id") or str(uuid4())

        return None
