# -*- coding: utf-8 -*-
"""
Goal Evaluator

Uses LLM to assess whether the agent's objective has been achieved
based on the accumulated iteration summaries.
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from inspect import isasyncgen
from typing import Any, List, Optional

from agentscope.model import ChatModelBase

from .iteration_context import LoopIterationSummary

logger = logging.getLogger(__name__)

_EVALUATOR_SYSTEM_PROMPT = """\
You are a task completion evaluator. Given the original objective and the results
from previous execution iterations, determine whether the objective has been achieved.

Evaluation criteria:
- achieved=true: The core requirements of the objective are fully satisfied
- confidence: Your confidence level in this judgment (0.0-1.0)
- remaining_gaps: Specific unfinished items if the objective is not fully achieved
- should_stop: true only when further execution cannot make progress
  (e.g., missing required permissions, tools unavailable, or unresolvable blockers)

Respond in JSON format only:
{"achieved": bool, "confidence": float, "reason": str, "remaining_gaps": [...], "should_stop": bool, "stop_reason": str}
"""


@dataclass
class GoalEvaluation:
    """Result of a single goal evaluation."""

    achieved: bool
    confidence: float               # 0.0 – 1.0
    reason: str
    remaining_gaps: List[str] = field(default_factory=list)
    should_stop: bool = False       # True when further iterations cannot help
    stop_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "achieved": self.achieved,
            "confidence": self.confidence,
            "reason": self.reason,
            "remaining_gaps": self.remaining_gaps,
            "should_stop": self.should_stop,
            "stop_reason": self.stop_reason,
        }


class GoalEvaluator:
    """
    LLM-based goal evaluator.

    Makes a single non-streaming LLM call after each coordinator iteration
    to assess whether the original objective has been met.
    """

    def __init__(self, model: ChatModelBase):
        self.model = model

    async def evaluate(
        self,
        objective: str,
        iteration_summaries: List[LoopIterationSummary],
    ) -> GoalEvaluation:
        """
        Evaluate whether the objective has been achieved.

        Args:
            objective: The original user objective.
            iteration_summaries: Summaries of all completed iterations.

        Returns:
            GoalEvaluation with achieved status and remaining gaps.
        """
        prompt = self._build_prompt(objective, iteration_summaries)
        messages = [
            {"role": "system", "content": _EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response_text = await self._call_model(messages)
            return self._parse_response(response_text)
        except Exception as exc:
            logger.warning("GoalEvaluator LLM call failed: %s", exc)
            # Fail-open: assume not yet achieved, allow loop to continue
            return GoalEvaluation(
                achieved=False,
                confidence=0.5,
                reason=f"Evaluation failed: {exc}",
                remaining_gaps=["Could not evaluate — continuing"],
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        objective: str,
        summaries: List[LoopIterationSummary],
    ) -> str:
        parts = [
            f"## Original Objective\n{objective}",
            "",
            "## Execution History",
        ]

        if not summaries:
            parts.append("No iterations completed yet.")
        else:
            for summary in summaries:
                parts.append(summary.to_context_string())
                parts.append("")

        parts.append(
            "Based on the execution history above, has the original objective been achieved?\n"
            "Respond with JSON only."
        )

        return "\n".join(parts)

    def _parse_response(self, text: Any) -> GoalEvaluation:
        """Parse the LLM JSON response into a GoalEvaluation."""
        if not isinstance(text, str):
            text = str(text)

        # Strip markdown code fences if present
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find raw JSON object
            obj_match = re.search(r'\{.*\}', text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)

        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError as exc:
            logger.warning("GoalEvaluator: failed to parse JSON response: %s\nRaw: %s", exc, text[:300])
            return GoalEvaluation(
                achieved=False,
                confidence=0.4,
                reason="Failed to parse evaluator response",
                remaining_gaps=["Evaluation parse error — assuming incomplete"],
            )

        return GoalEvaluation(
            achieved=bool(data.get("achieved", False)),
            confidence=float(data.get("confidence", 0.5)),
            reason=str(data.get("reason", "")),
            remaining_gaps=list(data.get("remaining_gaps", [])),
            should_stop=bool(data.get("should_stop", False)),
            stop_reason=data.get("stop_reason") or None,
        )

    async def _call_model(self, messages: list) -> str:
        """Call model and return the response text."""
        result = self.model(messages)

        if asyncio.iscoroutine(result):
            result = await result

        if isasyncgen(result):
            collected = None
            async for chunk in result:
                collected = chunk
            result = collected

        # Extract text content
        if result is not None:
            if hasattr(result, 'get'):
                content = result.get('content', '')
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            return item.get('text', '')
                    return str(content)
                return str(content)
            if hasattr(result, 'text'):
                return result.text
            if hasattr(result, 'content'):
                return str(result.content)

        return str(result) if result is not None else ""
