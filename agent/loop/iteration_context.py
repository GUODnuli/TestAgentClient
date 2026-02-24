# -*- coding: utf-8 -*-
"""
Loop iteration context data structures.

Decoupled from GAM — pure data structures with zero external dependencies.
Future memory modules can plug in by implementing the same interface.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LoopIterationSummary:
    """
    Compact summary of a single coordinator execution iteration.

    Extracted from coordinator phase_results and stored for cross-iteration context passing.
    """

    iteration: int
    completed_tasks: List[str] = field(default_factory=list)   # Successfully completed items
    artifacts: Dict[str, Any] = field(default_factory=dict)    # Key outputs (file paths, test results, etc.)
    remaining_gaps: List[str] = field(default_factory=list)    # Unfinished / missed items
    status: str = "partial"                                     # "success" | "partial" | "failed"
    phase_count: int = 0

    def to_context_string(self) -> str:
        """
        Convert to compact text for LLM consumption.
        Designed to be token-efficient while retaining key information.
        """
        lines = [
            f"=== Iteration {self.iteration} Summary ===",
            f"Status: {self.status}  |  Phases executed: {self.phase_count}",
        ]

        if self.completed_tasks:
            lines.append("Completed:")
            for task in self.completed_tasks:
                lines.append(f"  ✓ {task}")

        if self.artifacts:
            lines.append("Key artifacts:")
            for key, value in self.artifacts.items():
                # Truncate long values
                val_str = str(value)
                if len(val_str) > 120:
                    val_str = val_str[:120] + "..."
                lines.append(f"  • {key}: {val_str}")

        if self.remaining_gaps:
            lines.append("Remaining gaps:")
            for gap in self.remaining_gaps:
                lines.append(f"  ✗ {gap}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "completed_tasks": self.completed_tasks,
            "artifacts": self.artifacts,
            "remaining_gaps": self.remaining_gaps,
            "status": self.status,
            "phase_count": self.phase_count,
        }


@dataclass
class LoopContext:
    """
    Aggregated context passed to each subsequent coordinator iteration.

    Contains summaries of all previous iterations and optional user guidance
    collected via Smart Mode notifications.
    """

    iteration: int                                                     # Current iteration index (0-based)
    iteration_summaries: List[LoopIterationSummary] = field(default_factory=list)
    user_guidance: Optional[str] = None                                # Smart Mode: extra user direction
    max_iterations: Optional[int] = None                               # Total loop limit (for final-iter warning)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "iteration_summaries": [s.to_dict() for s in self.iteration_summaries],
            "user_guidance": self.user_guidance,
            "max_iterations": self.max_iterations,
        }

    def to_context_string(self) -> str:
        """
        Build a compressed multi-iteration context string for the continuation planner.
        """
        parts = [
            f"[Agent Loop Context — entering iteration {self.iteration}]",
            f"Previous iterations completed: {len(self.iteration_summaries)}",
            "",
        ]

        for summary in self.iteration_summaries:
            parts.append(summary.to_context_string())
            parts.append("")

        # Collect all remaining gaps across iterations (deduplicated)
        all_gaps: List[str] = []
        seen: set = set()
        for summary in self.iteration_summaries:
            for gap in summary.remaining_gaps:
                if gap not in seen:
                    seen.add(gap)
                    all_gaps.append(gap)

        if all_gaps:
            parts.append("=== Accumulated Remaining Gaps ===")
            for gap in all_gaps:
                parts.append(f"  ✗ {gap}")
            parts.append("")

        if self.user_guidance:
            parts.append(f"=== User Guidance ===\n{self.user_guidance}\n")

        return "\n".join(parts)

    @property
    def all_remaining_gaps(self) -> List[str]:
        """Deduplicated remaining gaps across all previous iterations."""
        seen: set = set()
        gaps: List[str] = []
        for summary in self.iteration_summaries:
            for gap in summary.remaining_gaps:
                if gap not in seen:
                    seen.add(gap)
                    gaps.append(gap)
        return gaps
