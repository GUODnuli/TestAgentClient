# -*- coding: utf-8 -*-
"""Unit tests for LoopIterationSummary and LoopContext."""
import sys
from pathlib import Path

# Import directly from module file to avoid agentscope dependency in __init__.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "iteration_context",
    Path(__file__).parent.parent / "iteration_context.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
LoopIterationSummary = _mod.LoopIterationSummary
LoopContext = _mod.LoopContext


def test_summary_to_context_string_success():
    s = LoopIterationSummary(
        iteration=0,
        completed_tasks=["Write tests", "Fix bug"],
        artifacts={"test_result": "2/2 passed"},
        remaining_gaps=["Deploy to staging"],
        status="partial",
        phase_count=2,
    )
    text = s.to_context_string()
    assert "Iteration 0" in text
    assert "Write tests" in text
    assert "Fix bug" in text
    assert "test_result" in text
    assert "Deploy to staging" in text
    assert "partial" in text


def test_summary_to_context_string_empty():
    s = LoopIterationSummary(iteration=1)
    text = s.to_context_string()
    assert "Iteration 1" in text
    # No completed tasks / gaps listed
    assert "✓" not in text
    assert "✗" not in text


def test_summary_artifact_truncation():
    long_val = "x" * 200
    s = LoopIterationSummary(
        iteration=0,
        artifacts={"big": long_val},
    )
    text = s.to_context_string()
    # Should be truncated to 120 chars + "..."
    assert "..." in text
    assert "big" in text


def test_loop_context_all_remaining_gaps_deduplication():
    s1 = LoopIterationSummary(iteration=0, remaining_gaps=["gap A", "gap B"])
    s2 = LoopIterationSummary(iteration=1, remaining_gaps=["gap B", "gap C"])
    ctx = LoopContext(iteration=2, iteration_summaries=[s1, s2])
    gaps = ctx.all_remaining_gaps
    assert gaps == ["gap A", "gap B", "gap C"]


def test_loop_context_to_context_string():
    s = LoopIterationSummary(
        iteration=0,
        completed_tasks=["task1"],
        remaining_gaps=["remaining1"],
        status="partial",
        phase_count=1,
    )
    ctx = LoopContext(iteration=1, iteration_summaries=[s], user_guidance="focus on X")
    text = ctx.to_context_string()
    assert "entering iteration 1" in text
    assert "task1" in text
    assert "remaining1" in text
    assert "User Guidance" in text
    assert "focus on X" in text


def test_loop_context_to_dict():
    s = LoopIterationSummary(iteration=0, status="success")
    ctx = LoopContext(iteration=1, iteration_summaries=[s], max_iterations=5)
    d = ctx.to_dict()
    assert d["iteration"] == 1
    assert d["max_iterations"] == 5
    assert len(d["iteration_summaries"]) == 1


if __name__ == "__main__":
    test_summary_to_context_string_success()
    test_summary_to_context_string_empty()
    test_summary_artifact_truncation()
    test_loop_context_all_remaining_gaps_deduplication()
    test_loop_context_to_context_string()
    test_loop_context_to_dict()
    print("All tests passed!")
