"""
Prompt OS Agent Runner for Micelia.

Implements processing logic for the 4 Prompt OS agents:
- Ingest: Normalizes captured notes (language, intent, tags)
- Taxonomy: Classifies and tags prompts (category, workflow, priority)
- Archivist: Manages knowledge promotion and persistence decisions
- Builder: Detects patterns and proposes skills/MCP servers

Each agent constructs a system prompt from its AgentDefinition,
sends the input to the Frangels orchestrator, and parses the JSON output.
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.core.logging import log
from app.services.frangels.orchestrator import get_frangels_orchestrator

from .agent_definitions import AGENT_DEFINITIONS


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extract a JSON object from LLM output.

    Handles common issues:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace and prose
    - Multiple JSON objects (takes the first)
    """
    if not text or not text.strip():
        raise ValueError("Empty response from LLM")

    cleaned = text.strip()

    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find the first { ... } block
    brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM output: {cleaned[:200]}")


class PromptOSAgentRunner:
    """
    Runs Prompt OS agents (ingest, taxonomy, archivist, builder)
    using the Frangels orchestrator for LLM inference.
    """

    def __init__(self, orchestrator=None):
        """
        Initialize the runner.

        Args:
            orchestrator: Optional FrangelsOrchestrator instance.
                          If None, uses the global singleton.
        """
        self._orchestrator = orchestrator

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            self._orchestrator = get_frangels_orchestrator()
        return self._orchestrator

    async def _call_agent(
        self,
        agent_key: str,
        user_content: str,
        prefer_paid: bool = False,
    ) -> Dict[str, Any]:
        """
        Internal: call an agent via Frangels and parse the JSON result.

        Args:
            agent_key: Key in AGENT_DEFINITIONS (e.g. 'ingest', 'taxonomy').
            user_content: The user message to send to the agent.
            prefer_paid: Whether to prefer paid providers.

        Returns:
            Dict with 'data' (parsed JSON), 'model_used', 'provider_used',
            'tokens_input', 'tokens_output', 'latency_ms'.

        Raises:
            ValueError: If the agent key is unknown or JSON parsing fails.
        """
        agent_def = AGENT_DEFINITIONS.get(agent_key)
        if not agent_def:
            raise ValueError(f"Unknown agent: {agent_key}")

        messages = [
            {"role": "system", "content": agent_def.system_prompt},
            {"role": "user", "content": user_content},
        ]

        result = await self.orchestrator.chat(
            messages=messages,
            prefer_paid=prefer_paid,
        )

        if not result.success:
            error_msg = result.error or "Unknown inference error"
            log.error(f"PromptOS agent '{agent_key}' inference failed: {error_msg}")
            raise RuntimeError(f"Agent '{agent_key}' inference failed: {error_msg}")

        # Parse the JSON output
        try:
            parsed = _extract_json(result.content)
        except ValueError as exc:
            log.warning(
                f"PromptOS agent '{agent_key}' returned non-JSON output, "
                f"attempting recovery: {exc}"
            )
            raise ValueError(
                f"Agent '{agent_key}' did not return valid JSON: {exc}"
            ) from exc

        return {
            "data": parsed,
            "model_used": result.model,
            "provider_used": result.provider_id,
            "tokens_input": result.tokens_input,
            "tokens_output": result.tokens_output,
            "latency_ms": result.latency_ms,
        }

    # ------------------------------------------------------------------
    # Public agent methods
    # ------------------------------------------------------------------

    async def run_ingest(self, raw_text: str) -> Dict[str, Any]:
        """
        Run the Ingest agent to normalize raw captured text.

        Args:
            raw_text: Raw text input (voice note, clipboard, quick capture).

        Returns:
            Dict with keys: type, language, clean_text, extracted_tags,
            detected_intent. Plus metadata: model_used, provider_used,
            tokens_input, tokens_output, latency_ms.
        """
        if not raw_text or not raw_text.strip():
            return {
                "data": {
                    "type": "note",
                    "language": "unknown",
                    "clean_text": "",
                    "extracted_tags": [],
                    "detected_intent": "empty input",
                },
                "model_used": None,
                "provider_used": None,
                "tokens_input": 0,
                "tokens_output": 0,
                "latency_ms": 0,
            }

        user_content = (
            "Normalize the following captured text:\n\n"
            f"--- RAW TEXT ---\n{raw_text}"
        )

        try:
            return await self._call_agent("ingest", user_content)
        except (ValueError, RuntimeError) as exc:
            log.error(f"Ingest agent failed: {exc}")
            # Return a best-effort fallback
            return {
                "data": {
                    "type": "note",
                    "language": "unknown",
                    "clean_text": raw_text.strip(),
                    "extracted_tags": [],
                    "detected_intent": "normalization failed",
                },
                "model_used": None,
                "provider_used": None,
                "tokens_input": 0,
                "tokens_output": 0,
                "latency_ms": 0,
                "error": str(exc),
            }

    async def run_taxonomy(self, prompt_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the Taxonomy agent to classify and tag a prompt.

        Args:
            prompt_dict: Dict with at least 'content' key. May also include
                         'tags', 'category', 'type' from prior ingest.

        Returns:
            Dict with keys: category, tags, workflow, provider_policy,
            priority, needs_staging, reasoning. Plus metadata.
        """
        content = prompt_dict.get("content", "")
        existing_tags = prompt_dict.get("tags", [])
        prompt_type = prompt_dict.get("type", "unknown")
        language = prompt_dict.get("language", "unknown")

        user_content = (
            "Classify the following prompt:\n\n"
            f"--- PROMPT CONTENT ---\n{content}\n\n"
            f"--- METADATA ---\n"
            f"Type: {prompt_type}\n"
            f"Language: {language}\n"
            f"Existing tags: {json.dumps(existing_tags)}"
        )

        try:
            return await self._call_agent("taxonomy", user_content)
        except (ValueError, RuntimeError) as exc:
            log.error(f"Taxonomy agent failed: {exc}")
            return {
                "data": {
                    "category": "note",
                    "tags": existing_tags,
                    "workflow": "quick_execute",
                    "provider_policy": "free-first",
                    "priority": 5,
                    "needs_staging": False,
                    "reasoning": f"Taxonomy agent failed: {exc}",
                },
                "model_used": None,
                "provider_used": None,
                "tokens_input": 0,
                "tokens_output": 0,
                "latency_ms": 0,
                "error": str(exc),
            }

    async def run_archivist(self, prompt_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the Archivist agent to decide on knowledge promotion.

        Args:
            prompt_dict: Dict with 'content' (the original prompt) and
                         'output' (the completed result) keys.

        Returns:
            Dict with keys: should_persist, destination_type,
            destination_slug, formatted_content, summary. Plus metadata.
        """
        content = prompt_dict.get("content", "")
        output = prompt_dict.get("output", "")
        category = prompt_dict.get("category", "unknown")
        tags = prompt_dict.get("tags", [])

        user_content = (
            "Evaluate the following completed prompt for knowledge promotion:\n\n"
            f"--- ORIGINAL PROMPT ---\n{content}\n\n"
            f"--- OUTPUT ---\n{output}\n\n"
            f"--- METADATA ---\n"
            f"Category: {category}\n"
            f"Tags: {json.dumps(tags)}"
        )

        try:
            return await self._call_agent("archivist", user_content)
        except (ValueError, RuntimeError) as exc:
            log.error(f"Archivist agent failed: {exc}")
            return {
                "data": {
                    "should_persist": False,
                    "destination_type": None,
                    "destination_slug": None,
                    "formatted_content": None,
                    "summary": f"Archivist agent failed: {exc}",
                },
                "model_used": None,
                "provider_used": None,
                "tokens_input": 0,
                "tokens_output": 0,
                "latency_ms": 0,
                "error": str(exc),
            }

    async def run_builder(self, recent_prompts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run the Builder agent to detect patterns and propose skills/MCP.

        Args:
            recent_prompts: List of prompt dicts with at least 'content',
                            'category', 'tags' keys.

        Returns:
            Dict with keys: patterns_found, proposed_skills, proposed_mcp.
            Plus metadata.
        """
        if not recent_prompts:
            return {
                "data": {
                    "patterns_found": [],
                    "proposed_skills": [],
                    "proposed_mcp": [],
                },
                "model_used": None,
                "provider_used": None,
                "tokens_input": 0,
                "tokens_output": 0,
                "latency_ms": 0,
            }

        # Build a summary of recent prompts for the builder
        prompt_summaries = []
        for i, p in enumerate(recent_prompts, 1):
            summary = {
                "index": i,
                "content": p.get("content", "")[:500],  # Truncate long content
                "category": p.get("category", "unknown"),
                "tags": p.get("tags", []),
                "type": p.get("type", "unknown"),
            }
            prompt_summaries.append(summary)

        user_content = (
            f"Analyze the following {len(recent_prompts)} recent prompts for "
            "recurring patterns and automation opportunities:\n\n"
            f"--- RECENT PROMPTS ---\n{json.dumps(prompt_summaries, indent=2)}"
        )

        try:
            return await self._call_agent(
                "builder", user_content, prefer_paid=False
            )
        except (ValueError, RuntimeError) as exc:
            log.error(f"Builder agent failed: {exc}")
            return {
                "data": {
                    "patterns_found": [],
                    "proposed_skills": [],
                    "proposed_mcp": [],
                },
                "model_used": None,
                "provider_used": None,
                "tokens_input": 0,
                "tokens_output": 0,
                "latency_ms": 0,
                "error": str(exc),
            }


# Module-level convenience instance (lazy-initialized)
_runner: Optional[PromptOSAgentRunner] = None


def get_prompt_os_runner() -> PromptOSAgentRunner:
    """Get or create the singleton PromptOSAgentRunner."""
    global _runner
    if _runner is None:
        _runner = PromptOSAgentRunner()
    return _runner
