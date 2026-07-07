"""
Executor de prompts: procesa prompts encolados via Frangels.

Soporta ejecución concurrente, review cross-model, y tracking de costos.
"""

import asyncio
from typing import Optional

from app.core.config import settings
from app.core.logging import log
from app.core.time import utcnow_naive


class PromptExecutor:
    """
    Procesa prompts de la cola usando Frangels orchestrator.
    Soporta providers gratuitos y de pago con review cross-model.
    """

    def __init__(self, prompt_store, frangels_orchestrator=None, event_bus=None, event_store=None):
        self._store = prompt_store
        self._orchestrator = frangels_orchestrator
        self._event_bus = event_bus
        self._event_store = event_store
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(settings.prompt_max_concurrent)
        self.running = False
        self.active_count = 0
        self.completed_today = 0
        self.failed_today = 0
        self._today_date = None

    async def start(self):
        """Inicia el loop de ejecución"""
        if self._task and not self._task.done():
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info(f"PromptExecutor iniciado (max_concurrent: {settings.prompt_max_concurrent})")

    async def stop(self):
        """Detiene el executor"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("PromptExecutor detenido")

    async def _run_loop(self):
        """Loop principal"""
        while self.running:
            try:
                self._reset_daily_counters()
                queued = await self._store.get_queued_prompts(
                    limit=settings.prompt_max_concurrent
                )
                if queued:
                    tasks = [self._execute_prompt(p) for p in queued]
                    await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"PromptExecutor loop error: {e}")
                await asyncio.sleep(5)

    async def _execute_prompt(self, prompt: dict):
        """Ejecuta un prompt individual"""
        async with self._semaphore:
            prompt_id = prompt["prompt_id"]
            self.active_count += 1
            start_time = utcnow_naive()

            try:
                # Marcar como processing
                await self._store.update_prompt(
                    prompt_id,
                    status="processing",
                    processing_at=start_time
                )

                # Ejecutar via Frangels
                result = await self._call_model(prompt)

                if not result["success"]:
                    await self._store.update_prompt(
                        prompt_id,
                        status="failed",
                        error=result.get("error", "Unknown error"),
                        iterations=prompt.get("iterations", 0) + 1
                    )
                    self.failed_today += 1
                    return

                # Review opcional para work/plan
                review_score = None
                if (settings.prompt_review_enabled and
                        prompt.get("category") in ("work", "plan")):
                    review_score = await self._review_output(
                        prompt["content"], result["content"]
                    )

                # Calcular latencia
                latency_ms = (utcnow_naive() - start_time).total_seconds() * 1000

                # Guardar resultado
                await self._store.update_prompt(
                    prompt_id,
                    status="completed",
                    output=result["content"],
                    model_used=result.get("model"),
                    provider_used=result.get("provider"),
                    review_score=review_score,
                    iterations=prompt.get("iterations", 0) + 1,
                    tokens_input=result.get("tokens_input", 0),
                    tokens_output=result.get("tokens_output", 0),
                    latency_ms=latency_ms,
                    cost_usd=result.get("cost_usd", 0),
                    completed_at=utcnow_naive()
                )

                self.completed_today += 1

                # Publicar evento
                if self._event_bus:
                    try:
                        await self._event_bus.publish("idm.prompts", {
                            "type": "prompt.completed",
                            "prompt_id": prompt_id,
                            "model": result.get("model"),
                            "latency_ms": latency_ms
                        })
                    except Exception:
                        pass

                # Registrar en Event Store
                if self._event_store:
                    try:
                        await self._event_store.append_event(
                            category="system",
                            source="prompt_executor",
                            action="execute",
                            event_type="prompt.execution.completed",
                            payload={"prompt_id": prompt_id, "model": result.get("model")},
                            compute_provider=result.get("provider"),
                            compute_model=result.get("model"),
                            compute_latency_ms=latency_ms,
                            compute_cost_usd=result.get("cost_usd")
                        )
                    except Exception:
                        pass

                log.debug(f"Prompt ejecutado: {prompt_id} ({result.get('model')})")

            except Exception as e:
                await self._store.update_prompt(
                    prompt_id,
                    status="failed",
                    error=str(e),
                    iterations=prompt.get("iterations", 0) + 1
                )
                self.failed_today += 1
                log.error(f"Error ejecutando prompt {prompt_id}: {e}")

            finally:
                self.active_count -= 1

    async def _call_model(self, prompt: dict) -> dict:
        """Llama al modelo via Frangels orchestrator"""
        if not self._orchestrator:
            return {
                "success": False,
                "error": "No Frangels orchestrator available"
            }

        try:
            # Determinar si usar paid
            prefer_paid = prompt.get("prefer_paid", False)
            category = prompt.get("category", "note")
            if category in ("work", "plan") and not prefer_paid:
                prefer_paid = True  # Auto-upgrade work/plan a paid si disponible

            messages = [
                {"role": "system", "content": "You are a helpful assistant. Respond concisely and accurately."},
                {"role": "user", "content": prompt["content"]}
            ]

            result = await self._orchestrator.chat(
                messages=messages,
                prefer_paid=prefer_paid
            )

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _review_output(self, original_prompt: str, output: str) -> Optional[float]:
        """Review cross-model del output"""
        if not self._orchestrator:
            return None

        try:
            review_prompt = (
                f"Review the following AI response for accuracy and completeness. "
                f"Rate from 0.0 to 1.0.\n\n"
                f"Original prompt: {original_prompt[:500]}\n\n"
                f"Response: {output[:1000]}\n\n"
                f"Reply with ONLY a number between 0.0 and 1.0."
            )

            result = await self._orchestrator.chat(
                messages=[{"role": "user", "content": review_prompt}],
                prefer_paid=False  # Review usa free tier
            )

            if result.get("success") and result.get("content"):
                try:
                    score = float(result["content"].strip())
                    return max(0.0, min(1.0, score))
                except ValueError:
                    return None

        except Exception:
            pass

        return None

    def _reset_daily_counters(self):
        """Reset contadores al cambiar de día"""
        today = utcnow_naive().date()
        if self._today_date != today:
            self._today_date = today
            self.completed_today = 0
            self.failed_today = 0
