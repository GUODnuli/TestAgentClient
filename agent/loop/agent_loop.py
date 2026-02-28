# -*- coding: utf-8 -*-
"""
AgentLoop

Drives the coordinator in a multi-iteration loop until the user's objective
is achieved or the maximum iteration count is reached.

Architecture:
    AgentLoop.run(objective)
        ├── [Iteration 0] Coordinator.execute(objective)              ← standard plan
        ├── GoalEvaluator.evaluate(objective, summaries)              ← LLM assessment
        ├── [Smart Mode] confidence < threshold → emit user_guidance_requested
        ├── [Iteration 1+] Coordinator.execute(objective, loop_ctx)   ← continuation plan
        └── ... until achieved=true or max_iterations reached
"""
import logging
from typing import Any, Callable, Dict, List, Optional

from .iteration_context import LoopContext, LoopIterationSummary
from .goal_evaluator import GoalEvaluator, GoalEvaluation

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Multi-iteration agent execution loop.

    Wraps a Coordinator instance and runs it repeatedly until the objective
    is achieved, a blocker is detected, or the iteration limit is reached.
    """

    def __init__(
        self,
        coordinator: Any,                      # Coordinator instance
        goal_evaluator: GoalEvaluator,
        max_iterations: int = 5,
        confidence_threshold: float = 0.7,     # Smart Mode threshold
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.coordinator = coordinator
        self.goal_evaluator = goal_evaluator
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.progress_callback = progress_callback or coordinator.progress_callback

    async def run(
        self,
        objective: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent loop until the objective is achieved or the limit is hit.

        Args:
            objective: The user's goal / task description.
            context: Initial execution context (e.g., workspace path).
            session_id: Session / conversation identifier.

        Returns:
            Aggregated result dictionary.
        """
        iteration_summaries: List[LoopIterationSummary] = []
        final_evaluation: Optional[GoalEvaluation] = None

        self._emit("loop_started", {
            "max_iterations": self.max_iterations,
            "objective": objective,
        })

        for i in range(self.max_iterations):
            self._emit("loop_iteration_started", {"iteration": i, "max": self.max_iterations})
            logger.info("[AgentLoop] Starting iteration %d / %d", i + 1, self.max_iterations)

            # Build loop context for continuation iterations
            loop_ctx = self._build_loop_context(i, iteration_summaries) if i > 0 else None

            # Execute coordinator (passes loop_ctx for continuation planning)
            try:
                result = await self.coordinator.execute(
                    objective=objective,
                    context=context,
                    session_id=session_id,
                    loop_context=loop_ctx,
                )
            except Exception as exc:
                logger.error("[AgentLoop] Coordinator failed on iteration %d: %s", i, exc)
                self._emit("loop_completed", {
                    "achieved": False,
                    "reason": f"Coordinator error on iteration {i}: {exc}",
                })
                return self._aggregate_results(
                    objective, iteration_summaries, final_evaluation,
                    error=str(exc),
                )

            # Extract iteration summary from coordinator result
            summary = self._extract_summary(result, i)
            iteration_summaries.append(summary)

            # LLM-based goal evaluation
            final_evaluation = await self.goal_evaluator.evaluate(objective, iteration_summaries)

            self._emit("goal_evaluated", {
                "iteration": i,
                "achieved": final_evaluation.achieved,
                "confidence": final_evaluation.confidence,
                "reason": final_evaluation.reason,
                "remaining_gaps": final_evaluation.remaining_gaps,
            })

            logger.info(
                "[AgentLoop] Iteration %d evaluated: achieved=%s confidence=%.2f",
                i, final_evaluation.achieved, final_evaluation.confidence,
            )

            # Update remaining gaps from evaluator into the summary
            if not final_evaluation.achieved and final_evaluation.remaining_gaps:
                summary.remaining_gaps = final_evaluation.remaining_gaps

            if final_evaluation.achieved:
                self._emit("loop_completed", {"achieved": True, "iterations": i + 1})
                break

            # Smart Mode: low-confidence notification (non-blocking)
            if final_evaluation.confidence < self.confidence_threshold:
                self._emit("user_guidance_requested", {
                    "iteration": i,
                    "reason": final_evaluation.reason,
                    "remaining_gaps": final_evaluation.remaining_gaps,
                    "message": (
                        "目标评估置信度较低，Agent 将继续尝试，"
                        "建议在下一轮对话中提供具体指引"
                    ),
                })

            if final_evaluation.should_stop:
                self._emit("loop_completed", {
                    "achieved": False,
                    "reason": final_evaluation.stop_reason or "No further progress possible",
                })
                break

        else:
            # Exhausted max_iterations
            self._emit("loop_completed", {
                "achieved": False,
                "reason": "已达最大迭代次数",
            })
            # Emit continuation prompt so the frontend can offer a "continue" button
            final_summary_text = self._build_final_summary_text(iteration_summaries)
            remaining = final_evaluation.remaining_gaps if final_evaluation else []
            gaps_str = "; ".join(remaining) if remaining else "unspecified gaps"
            self._emit("continuation_prompt", {
                "message": (
                    "The agent has reached its maximum iteration limit. "
                    "Would you like to continue working on the remaining tasks in a new session?"
                ),
                "remaining_gaps": remaining,
                "summary": final_summary_text,
                "suggested_next_message": f"Please continue from where you left off: {gaps_str}",
            })

        return self._aggregate_results(objective, iteration_summaries, final_evaluation)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_summary(self, coordinator_result: Dict[str, Any], iteration: int) -> LoopIterationSummary:
        """
        Build a LoopIterationSummary from a raw coordinator result dict.
        """
        phase_results = coordinator_result.get("phase_results", [])
        status = coordinator_result.get("status", "failed")

        completed_tasks: List[str] = []
        artifacts: Dict[str, Any] = {}

        for phase in phase_results:
            phase_name = phase.get("phase_name", "")
            phase_status = phase.get("status", "failed")

            worker_results = phase.get("worker_results", {})
            for worker_name, wr in worker_results.items():
                worker_status = wr.get("status", "failed")
                worker_output = wr.get("output", "")
                task_desc = wr.get("task_description", "")

                # Accept both "success" (legacy phase format) and "completed" (task-tree format)
                if worker_status in ("success", "completed"):
                    label = task_desc or phase_name or worker_name
                    completed_tasks.append(label)
                    # Store truncated output as artifact
                    if worker_output:
                        artifact_key = f"phase_{phase.get('phase', '')}_{worker_name}"
                        out_str = str(worker_output)
                        artifacts[artifact_key] = out_str[:500] if len(out_str) > 500 else out_str

        # Map coordinator status to loop status
        if status == "completed":
            loop_status = "success"
        elif status == "failed":
            loop_status = "failed"
        else:
            loop_status = "partial"

        return LoopIterationSummary(
            iteration=iteration,
            completed_tasks=completed_tasks,
            artifacts=artifacts,
            remaining_gaps=[],   # filled by GoalEvaluator after evaluate()
            status=loop_status,
            phase_count=len(phase_results),
        )

    def _build_loop_context(
        self,
        iteration: int,
        summaries: List[LoopIterationSummary],
    ) -> LoopContext:
        return LoopContext(
            iteration=iteration,
            iteration_summaries=list(summaries),  # shallow copy
            max_iterations=self.max_iterations,
        )

    def _aggregate_results(
        self,
        objective: str,
        summaries: List[LoopIterationSummary],
        final_eval: Optional[GoalEvaluation],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble the final report returned to the caller."""
        total_completed = []
        for s in summaries:
            total_completed.extend(s.completed_tasks)

        return {
            "objective": objective,
            "iterations_run": len(summaries),
            "achieved": final_eval.achieved if final_eval else False,
            "final_evaluation": final_eval.to_dict() if final_eval else {},
            "completed_tasks": total_completed,
            "iteration_summaries": [s.to_dict() for s in summaries],
            "status": "completed" if (final_eval and final_eval.achieved) else "incomplete",
            "error": error,
        }

    def _build_final_summary_text(self, summaries: List[LoopIterationSummary]) -> str:
        lines = [f"Agent loop ran {len(summaries)} iteration(s)."]
        for s in summaries:
            lines.append(s.to_context_string())
        return "\n".join(lines)

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Forward events through the coordinator's progress_callback."""
        if self.progress_callback:
            try:
                self.progress_callback(event_type, data)
            except Exception as exc:
                logger.warning("[AgentLoop] progress_callback failed: %s", exc)
