# -*- coding: utf-8 -*-
"""
Orchestrator package

OrchestratorAgent replaces the static TaskPlanner + PhaseScheduler pipeline
with a ReAct-driven planner that first scouts the environment, then dynamically
decomposes work into a task tree, and finally dispatches workers.
"""
from .task_manager import TaskManager, TaskNode
from .orchestrator_tools import make_orchestrator_tools
from .orchestrator_agent import OrchestratorAgent

__all__ = ["TaskManager", "TaskNode", "make_orchestrator_tools", "OrchestratorAgent"]
