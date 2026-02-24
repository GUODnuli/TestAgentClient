# -*- coding: utf-8 -*-
"""Unit tests for GoalEvaluator._parse_response."""
import sys, types, importlib.util
from pathlib import Path

# Stub out agentscope so we can import GoalEvaluator without installing it
agentscope_stub = types.ModuleType("agentscope")
agentscope_model_stub = types.ModuleType("agentscope.model")
agentscope_model_stub.ChatModelBase = object
agentscope_stub.model = agentscope_model_stub
sys.modules.setdefault("agentscope", agentscope_stub)
sys.modules.setdefault("agentscope.model", agentscope_model_stub)

# Register the 'loop' package so relative imports in goal_evaluator.py work
loop_dir = Path(__file__).parent.parent
sys.path.insert(0, str(loop_dir.parent))   # agent/ on sys.path

# Create a stub 'loop' package if agentscope isn't available
loop_pkg = types.ModuleType("loop")
loop_pkg.__path__ = [str(loop_dir)]
loop_pkg.__package__ = "loop"
sys.modules.setdefault("loop", loop_pkg)

# Load iteration_context into loop.iteration_context
_ic_spec = importlib.util.spec_from_file_location(
    "loop.iteration_context",
    loop_dir / "iteration_context.py",
    submodule_search_locations=[],
)
_ic_mod = importlib.util.module_from_spec(_ic_spec)
_ic_mod.__package__ = "loop"
sys.modules["loop.iteration_context"] = _ic_mod
_ic_spec.loader.exec_module(_ic_mod)

# Load goal_evaluator into loop.goal_evaluator
_ge_spec = importlib.util.spec_from_file_location(
    "loop.goal_evaluator",
    loop_dir / "goal_evaluator.py",
    submodule_search_locations=[],
)
_ge_mod = importlib.util.module_from_spec(_ge_spec)
_ge_mod.__package__ = "loop"
sys.modules["loop.goal_evaluator"] = _ge_mod
_ge_spec.loader.exec_module(_ge_mod)

GoalEvaluator = _ge_mod.GoalEvaluator
GoalEvaluation = _ge_mod.GoalEvaluation


class _FakeModel:
    """Minimal stub so GoalEvaluator can be instantiated without agentscope."""
    def __call__(self, messages):
        return None


def _make_evaluator():
    return GoalEvaluator(model=_FakeModel())


def test_parse_achieved_true():
    ev = _make_evaluator()
    result = ev._parse_response(
        '{"achieved": true, "confidence": 0.95, "reason": "All done", '
        '"remaining_gaps": [], "should_stop": false, "stop_reason": null}'
    )
    assert result.achieved is True
    assert result.confidence == 0.95
    assert result.reason == "All done"
    assert result.remaining_gaps == []
    assert result.should_stop is False
    assert result.stop_reason is None


def test_parse_achieved_false_with_gaps():
    ev = _make_evaluator()
    result = ev._parse_response(
        '{"achieved": false, "confidence": 0.4, "reason": "Incomplete", '
        '"remaining_gaps": ["step A", "step B"], "should_stop": false, "stop_reason": ""}'
    )
    assert result.achieved is False
    assert result.confidence == 0.4
    assert "step A" in result.remaining_gaps
    assert "step B" in result.remaining_gaps


def test_parse_should_stop():
    ev = _make_evaluator()
    result = ev._parse_response(
        '{"achieved": false, "confidence": 0.3, "reason": "Blocked", '
        '"remaining_gaps": [], "should_stop": true, "stop_reason": "No permission"}'
    )
    assert result.should_stop is True
    assert result.stop_reason == "No permission"


def test_parse_json_in_markdown_fence():
    ev = _make_evaluator()
    text = """```json
{"achieved": true, "confidence": 0.9, "reason": "Done", "remaining_gaps": [], "should_stop": false, "stop_reason": null}
```"""
    result = ev._parse_response(text)
    assert result.achieved is True
    assert result.confidence == 0.9


def test_parse_invalid_json_returns_fallback():
    ev = _make_evaluator()
    result = ev._parse_response("this is not json at all")
    assert isinstance(result, GoalEvaluation)
    assert result.achieved is False
    assert result.confidence == 0.4


def test_to_dict():
    ev = GoalEvaluation(
        achieved=True, confidence=0.99, reason="Done",
        remaining_gaps=[], should_stop=False, stop_reason=None
    )
    d = ev.to_dict()
    assert d["achieved"] is True
    assert d["confidence"] == 0.99


if __name__ == "__main__":
    test_parse_achieved_true()
    test_parse_achieved_false_with_gaps()
    test_parse_should_stop()
    test_parse_json_in_markdown_fence()
    test_parse_invalid_json_returns_fallback()
    test_to_dict()
    print("All tests passed!")
