"""
Workflow Engine for Micelia Multi-Agent Orchestration.

Executes multi-agent workflows by stepping through workflow definitions,
calling models via the Frangels orchestrator, and tracking run results.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.logging import log

from .agent_definitions import AGENT_DEFINITIONS, AgentDefinition
from .workflows import WORKFLOWS, WorkflowDefinition


class WorkflowEngine:
    """
    Executes multi-agent workflows using the Frangels orchestrator.

    Each workflow run steps through a sequence of agents, passing context
    between them and deciding the next step based on success/failure.
    """

    def __init__(self, frangels_orchestrator, prompt_store, entire_service=None):
        self._orchestrator = frangels_orchestrator
        self._prompt_store = prompt_store
        self._entire_service = entire_service
        self._runs: List[Dict[str, Any]] = []
        self._max_stored_runs = 200

    async def execute_workflow(
        self,
        prompt_id: str,
        workflow_name: str = "reviewed_execute",
    ) -> Dict[str, Any]:
        """
        Execute a multi-agent workflow for a given prompt.

        Args:
            prompt_id: ID of the prompt to process (loaded from prompt_store).
            workflow_name: Name of the workflow to run.

        Returns:
            Dict with run_id, status, steps, total_duration_ms, total_cost_usd.
        """
        # Validate workflow
        workflow = WORKFLOWS.get(workflow_name)
        if not workflow:
            return {
                "run_id": str(uuid4()),
                "status": "failed",
                "error": f"Unknown workflow: {workflow_name}",
                "steps": [],
                "total_duration_ms": 0,
                "total_cost_usd": 0.0,
            }

        # Load prompt
        prompt_data = await self._prompt_store.get_prompt(prompt_id)
        if not prompt_data:
            return {
                "run_id": str(uuid4()),
                "status": "failed",
                "error": f"Prompt not found: {prompt_id}",
                "steps": [],
                "total_duration_ms": 0,
                "total_cost_usd": 0.0,
            }

        user_prompt = prompt_data.get("content", "")
        run_id = str(uuid4())
        run_start = datetime.now(timezone.utc)
        step_results: List[Dict[str, Any]] = []
        context: Dict[str, Any] = {
            "user_prompt": user_prompt,
            "plan": None,
            "executor_output": None,
            "review": None,
            "critique": None,
            "patched_output": None,
            "taxonomy_result": None,
            "builder_output": None,
        }
        total_cost_usd = 0.0
        retries_remaining = workflow.max_retries

        # Start audit session
        audit_session_id = None
        if self._entire_service:
            try:
                audit_session_id = await self._entire_service.start_session(
                    prompt_id=prompt_id,
                    workflow_name=workflow_name,
                    run_id=run_id,
                )
            except Exception as e:
                log.warning(f"Audit session start failed: {e}")

        log.info(
            f"Starting workflow '{workflow_name}' for prompt {prompt_id} "
            f"(run_id={run_id})"
        )

        # Walk the step graph
        step_index = 0
        overall_status = "completed"

        while step_index < len(workflow.steps):
            step_def = workflow.steps[step_index]
            agent_def = AGENT_DEFINITIONS.get(step_def.agent)
            if not agent_def:
                overall_status = "failed"
                step_results.append({
                    "step": step_index,
                    "agent": step_def.agent,
                    "action": step_def.action,
                    "status": "failed",
                    "error": f"Unknown agent: {step_def.agent}",
                    "duration_ms": 0,
                    "cost_usd": 0.0,
                })
                break

            # Build messages for this agent
            messages = self._build_messages(agent_def, step_def.action, context)

            # Call the model
            step_start = datetime.now(timezone.utc)
            try:
                result = await self._orchestrator.chat(
                    messages=messages,
                    prefer_paid=False,
                )
                step_duration_ms = (
                    (datetime.now(timezone.utc) - step_start).total_seconds() * 1000
                )

                success = getattr(result, "success", result.get("success", False)) if isinstance(result, dict) else result.success
                content = getattr(result, "content", result.get("content", "")) if isinstance(result, dict) else result.content
                content = content if isinstance(content, str) else ""
                tokens_in = getattr(result, "tokens_input", 0) if not isinstance(result, dict) else result.get("tokens_input", 0)
                tokens_out = getattr(result, "tokens_output", 0) if not isinstance(result, dict) else result.get("tokens_output", 0)
                model_used = getattr(result, "model", "") if not isinstance(result, dict) else result.get("model", "")
                provider_used = getattr(result, "provider_id", "") if not isinstance(result, dict) else result.get("provider_id", "")
                error_msg = getattr(result, "error", None) if not isinstance(result, dict) else result.get("error")

            except Exception as e:
                success = False
                content = ""
                tokens_in = 0
                tokens_out = 0
                model_used = ""
                provider_used = ""
                error_msg = str(e)
                step_duration_ms = (
                    (datetime.now(timezone.utc) - step_start).total_seconds() * 1000
                )

            # Estimate cost (rough: $0.002 per 1k tokens)
            step_cost = ((tokens_in + tokens_out) / 1000) * 0.002
            total_cost_usd += step_cost

            step_record = {
                "step": step_index,
                "agent": step_def.agent,
                "action": step_def.action,
                "status": "completed" if success else "failed",
                "output": content,
                "model": model_used,
                "provider": provider_used,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "duration_ms": round(step_duration_ms, 2),
                "cost_usd": round(step_cost, 6),
                "error": error_msg if not success else None,
            }
            step_results.append(step_record)

            # Audit checkpoint
            if self._entire_service and audit_session_id:
                try:
                    await self._entire_service.checkpoint(
                        session_id=audit_session_id,
                        agent_name=step_def.agent,
                        action=step_def.action,
                        output_summary=content[:200] if success else error_msg,
                    )
                except Exception:
                    pass

            if success:
                # Update context based on agent role
                self._update_context(context, step_def.agent, content)

                # Determine success/failure for reviewer (parse score)
                step_passed = True
                if step_def.agent == "reviewer":
                    step_passed = self._reviewer_passed(content)
                elif step_def.agent == "critic":
                    step_passed = not self._critic_requires_patch(content)

                if step_passed:
                    # Move to next_on_success
                    next_action = step_def.next_on_success
                else:
                    # Move to next_on_failure (retry path)
                    next_action = step_def.next_on_failure

                if next_action is None:
                    # Workflow complete
                    break

                # Find the step index for next_action
                next_index = self._find_step_index(workflow, next_action)
                if next_index is None:
                    overall_status = "failed"
                    log.error(
                        f"Workflow step '{step_def.agent}' references unknown "
                        f"next action '{next_action}'"
                    )
                    break

                # Check retry budget
                if next_index <= step_index:
                    if retries_remaining <= 0:
                        log.warning(
                            f"Workflow run {run_id}: max retries reached at "
                            f"step {step_index}"
                        )
                        break
                    retries_remaining -= 1

                step_index = next_index
            else:
                # Step failed — try failure path
                if step_def.next_on_failure:
                    next_index = self._find_step_index(
                        workflow, step_def.next_on_failure
                    )
                    if next_index is not None and retries_remaining > 0:
                        retries_remaining -= 1
                        step_index = next_index
                        continue

                overall_status = "failed"
                log.error(
                    f"Workflow run {run_id} failed at step {step_index} "
                    f"({step_def.agent}): {error_msg}"
                )
                break

        # End audit session
        if self._entire_service and audit_session_id:
            try:
                await self._entire_service.end_session(audit_session_id, overall_status)
            except Exception:
                pass

        total_duration_ms = (
            (datetime.now(timezone.utc) - run_start).total_seconds() * 1000
        )

        # Determine final output
        final_output = (
            context.get("patched_output")
            or context.get("executor_output")
            or ""
        )

        run_record = {
            "run_id": run_id,
            "prompt_id": prompt_id,
            "workflow": workflow_name,
            "status": overall_status,
            "final_output": final_output,
            "steps": step_results,
            "total_duration_ms": round(total_duration_ms, 2),
            "total_cost_usd": round(total_cost_usd, 6),
            "started_at": run_start.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store run
        self._runs.append(run_record)
        if len(self._runs) > self._max_stored_runs:
            self._runs = self._runs[-self._max_stored_runs:]

        log.info(
            f"Workflow '{workflow_name}' run {run_id} {overall_status} "
            f"in {total_duration_ms:.0f}ms ({len(step_results)} steps)"
        )

        return run_record

    def get_runs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Return recent workflow runs."""
        sorted_runs = sorted(
            self._runs, key=lambda r: r.get("started_at", ""), reverse=True
        )
        return sorted_runs[offset : offset + limit]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Return a specific run by ID."""
        for run in self._runs:
            if run["run_id"] == run_id:
                return run
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        agent_def: AgentDefinition,
        action: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Build the message list for a model call based on the agent and context."""
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": agent_def.system_prompt},
        ]

        user_prompt = context.get("user_prompt", "")

        if action == "analyze_and_plan":
            messages.append({
                "role": "user",
                "content": f"Analyze and plan the following prompt:\n\n{user_prompt}",
            })

        elif action == "execute":
            plan_text = context.get("plan") or "No plan available."
            messages.append({
                "role": "user",
                "content": (
                    f"Execute the following prompt according to the plan.\n\n"
                    f"--- PLAN ---\n{plan_text}\n\n"
                    f"--- USER PROMPT ---\n{user_prompt}"
                ),
            })

        elif action == "review":
            executor_output = context.get("executor_output") or ""
            messages.append({
                "role": "user",
                "content": (
                    f"Review the following response.\n\n"
                    f"--- ORIGINAL PROMPT ---\n{user_prompt}\n\n"
                    f"--- EXECUTOR RESPONSE ---\n{executor_output}"
                ),
            })

        elif action == "critique":
            executor_output = context.get("executor_output") or ""
            messages.append({
                "role": "user",
                "content": (
                    f"Critique the following response for hallucinations, "
                    f"inconsistencies, and safety issues.\n\n"
                    f"--- ORIGINAL PROMPT ---\n{user_prompt}\n\n"
                    f"--- EXECUTOR RESPONSE ---\n{executor_output}"
                ),
            })

        elif action == "patch":
            executor_output = context.get("executor_output") or ""
            review_text = context.get("review") or "No review available."
            critique_text = context.get("critique") or "No critique available."
            messages.append({
                "role": "user",
                "content": (
                    f"Patch the following response based on the review and critique.\n\n"
                    f"--- ORIGINAL PROMPT ---\n{user_prompt}\n\n"
                    f"--- EXECUTOR RESPONSE ---\n{executor_output}\n\n"
                    f"--- REVIEW ---\n{review_text}\n\n"
                    f"--- CRITIQUE ---\n{critique_text}"
                ),
            })

        elif action == "classify":
            messages.append({
                "role": "user",
                "content": (
                    f"Classify the following prompt. Determine category, tags, "
                    f"workflow, provider policy, and priority.\n\n"
                    f"--- PROMPT ---\n{user_prompt}"
                ),
            })

        elif action == "detect_pattern":
            messages.append({
                "role": "user",
                "content": (
                    f"Analyze the following prompt and any related context to detect "
                    f"recurring patterns that could become a reusable skill. "
                    f"If a pattern is found, describe the skill template.\n\n"
                    f"--- PROMPT ---\n{user_prompt}\n\n"
                    f"--- CLASSIFICATION ---\n{context.get('taxonomy_result') or 'N/A'}"
                ),
            })

        elif action == "detect_tool_need":
            messages.append({
                "role": "user",
                "content": (
                    f"Analyze the following prompt to determine if it needs external "
                    f"tools or APIs. If so, list the required operations and suggest "
                    f"an MCP server specification.\n\n"
                    f"--- PROMPT ---\n{user_prompt}\n\n"
                    f"--- CLASSIFICATION ---\n{context.get('taxonomy_result') or 'N/A'}"
                ),
            })

        elif action == "generate_skill":
            builder_output = context.get("builder_output") or ""
            messages.append({
                "role": "user",
                "content": (
                    f"Generate a complete skill template based on the detected pattern.\n\n"
                    f"--- ORIGINAL PROMPT ---\n{user_prompt}\n\n"
                    f"--- PATTERN ANALYSIS ---\n{builder_output}\n\n"
                    f"Output JSON with: name, slug, trigger_pattern (regex), "
                    f"prompt_template (with {{content}} placeholder), description."
                ),
            })

        elif action == "generate_mcp_spec":
            builder_output = context.get("builder_output") or ""
            messages.append({
                "role": "user",
                "content": (
                    f"Generate an MCP server specification based on the detected tool needs.\n\n"
                    f"--- ORIGINAL PROMPT ---\n{user_prompt}\n\n"
                    f"--- TOOL ANALYSIS ---\n{builder_output}\n\n"
                    f"Output JSON with: name, description, language (python|typescript), "
                    f"operations (list of {{name, description, parameters}})."
                ),
            })

        else:
            messages.append({"role": "user", "content": user_prompt})

        return messages

    def _update_context(
        self, context: Dict[str, Any], agent: str, content: str
    ) -> None:
        """Update the running context with the output of a step."""
        if agent == "planner":
            context["plan"] = content
        elif agent == "executor":
            context["executor_output"] = content
        elif agent == "reviewer":
            context["review"] = content
        elif agent == "critic":
            context["critique"] = content
        elif agent == "patcher":
            context["patched_output"] = content
        elif agent == "taxonomy":
            context["taxonomy_result"] = content
        elif agent == "builder":
            context["builder_output"] = content

    def _reviewer_passed(self, content: str) -> bool:
        """
        Parse the Reviewer's output to determine if the response passed.
        Looks for a JSON with "passed" or "score" fields.
        """
        try:
            data = json.loads(content)
            if "passed" in data:
                return bool(data["passed"])
            if "score" in data:
                return float(data["score"]) >= 0.7
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Fallback: look for keywords
        lower = content.lower()
        if "passed" in lower or "approved" in lower:
            return True
        if "failed" in lower or "rejected" in lower:
            return False

        # Default to passed if we cannot determine
        return True

    def _critic_requires_patch(self, content: str) -> bool:
        """
        Parse the Critic's output to determine if patching is required.
        """
        try:
            data = json.loads(content)
            if "requires_patch" in data:
                return bool(data["requires_patch"])
            if "severity" in data:
                return data["severity"] in ("medium", "high", "critical")
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Default: no patch needed
        return False

    def _find_step_index(
        self, workflow: WorkflowDefinition, action: str
    ) -> Optional[int]:
        """Find the index of a step by its action name."""
        for i, step in enumerate(workflow.steps):
            if step.action == action:
                return i
        return None
