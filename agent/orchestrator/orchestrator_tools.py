# -*- coding: utf-8 -*-
"""
Orchestrator 工具函数工厂

将 TaskManager 的方法封装为 AgentScope 工具函数（同步 def）。
通过工厂函数绑定 task_manager 实例，避免依赖注入问题。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)


def make_orchestrator_tools(task_manager: Any, available_workers: List[str]):
    """
    工厂函数，返回绑定了 task_manager 的工具函数列表。

    Args:
        task_manager: TaskManager 实例
        available_workers: 可用 Worker 名称列表（用于文档字符串）

    Returns:
        工具函数列表
    """
    worker_list_str = ", ".join(available_workers) if available_workers else "(none loaded)"

    def create_task(
        description: str,
        worker_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
    ) -> ToolResponse:
        """Register a new task to be executed by the specified worker.

        Returns the task_id for use with spawn_and_wait().
        The task is NOT executed immediately — call spawn_and_wait(task_id) to run it.

        Args:
            description: Clear description of what this task should accomplish.
                         Be specific: include file paths, API endpoints, expected outputs.
            worker_name: Name of the worker to execute this task.
                         Must be one of the available workers.
            input_data: Dict with specific inputs for the worker.
                        Pass file contents, API specs, or other data already gathered —
                        do NOT ask the worker to re-discover information you already have.
            parent_id: Optional task_id of the parent task (for sub-tasks).

        Returns:
            ToolResponse containing task_id (e.g. "task_001")
        """
        if not description:
            return ToolResponse(content="ERROR: description cannot be empty")
        if not worker_name:
            return ToolResponse(content="ERROR: worker_name cannot be empty")

        result = task_manager.create_task(
            description=description,
            worker_name=worker_name,
            input_data=input_data,
            parent_id=parent_id,
        )
        return ToolResponse(content=result)

    async def spawn_and_wait(task_id: str) -> ToolResponse:
        """Execute a registered task and wait for its completion.

        Runs the worker asynchronously and returns the full output text.
        If the worker fails, returns an "ERROR: ..." string.

        Args:
            task_id: The task_id returned by create_task().

        Returns:
            Worker output text, or "ERROR: ..." on failure.
        """
        if not task_id:
            return ToolResponse(content="ERROR: task_id cannot be empty")

        result = await task_manager.spawn_and_wait(task_id)
        return ToolResponse(content=result)

    async def spawn_task(
        description: str,
        worker_name: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> ToolResponse:
        """Convenience: create a task AND execute it immediately in one call.

        Equivalent to: task_id = create_task(...); result = spawn_and_wait(task_id)

        Args:
            description: Clear description of what this task should accomplish.
            worker_name: Name of the worker to execute this task.
            input_data: Dict with specific inputs for the worker.

        Returns:
            Worker output text, or "ERROR: ..." on failure.
        """
        task_id = task_manager.create_task(
            description=description,
            worker_name=worker_name,
            input_data=input_data,
        )
        result = await task_manager.spawn_and_wait(task_id)
        return ToolResponse(content=result)

    def list_tasks() -> ToolResponse:
        """Show the current task tree with status.

        Use this to track progress before finalizing or when deciding next steps.

        Returns:
            Text representation of the task tree.
        """
        return ToolResponse(content=task_manager.list_tasks())

    def get_available_workers() -> ToolResponse:
        """List all available workers with their descriptions.

        Returns:
            JSON string with worker names and descriptions.
        """
        workers = task_manager._workers
        result = []
        for name, config in workers.items():
            result.append({
                "name": name,
                "description": getattr(config, "description", ""),
                "mode": getattr(config, "mode", "react"),
            })
        return ToolResponse(content=json.dumps(result, ensure_ascii=False, indent=2))

    async def spawn_batch_and_wait(task_ids: str, timeout: int = 600) -> ToolResponse:
        """Execute multiple registered tasks concurrently and wait for all to complete.

        All tasks start simultaneously as concurrent coroutines. Use this when tasks are
        independent of each other (e.g. generating test cases for N test-point batches
        in parallel).

        Args:
            task_ids: JSON array string of task_ids to run concurrently.
                      Example: '["task_001", "task_002", "task_003"]'
                      All task_ids must have been registered via create_task() first.
            timeout:  Per-task timeout in seconds (default 600). Tasks exceeding
                      this limit are marked as failed.

        Returns:
            JSON string::

                {
                  "total": 3,
                  "succeeded": 2,
                  "failed": 1,
                  "results": [
                    {"task_id": "task_001", "status": "ok",    "summary": "..."},
                    {"task_id": "task_002", "status": "error", "error": "timeout"}
                  ]
                }

            Note: succeeded results contain a 300-char "summary" (truncated) — NOT the full
            worker output. Use list_output_files() / read_output_file() to access full
            deliverable files written by workers.
        """
        if not task_ids:
            return ToolResponse(content="ERROR: task_ids cannot be empty")

        try:
            ids = json.loads(task_ids)
        except (json.JSONDecodeError, TypeError) as exc:
            return ToolResponse(content=f"ERROR: task_ids must be a valid JSON array string: {exc}")

        if not isinstance(ids, list):
            return ToolResponse(content="ERROR: task_ids must be a JSON array, e.g. '[\"task_001\", \"task_002\"]'")

        result = await task_manager.spawn_batch_and_wait(ids, timeout=timeout)
        return ToolResponse(content=result)

    # Update docstrings to include the actual worker list
    create_task.__doc__ = create_task.__doc__.replace(
        "Must be one of the available workers.",
        f"Must be one of: {worker_list_str}"
    )

    return [create_task, spawn_and_wait, spawn_task, list_tasks, get_available_workers, spawn_batch_and_wait]
