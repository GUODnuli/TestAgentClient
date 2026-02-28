# -*- coding: utf-8 -*-
"""
TaskManager — 动态任务树管理器

负责注册任务节点、调度 Worker 执行、发布任务树事件。
spawn_and_wait 在独立线程+独立 event loop 中运行 Worker，
避免 asyncio 嵌套运行问题。
"""
import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskNode:
    """任务树节点"""
    task_id: str
    description: str
    worker_name: str
    input_data: dict
    status: str = "pending"   # pending | running | completed | failed
    result: Optional[str] = None      # 前 500 字符摘要
    error: Optional[str] = None
    parent_id: Optional[str] = None
    depth: int = 0                    # 嵌套深度，root=0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "worker_name": self.worker_name,
            "input_data": self.input_data,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class TaskManager:
    """
    动态任务树管理器

    - create_task: 注册节点（不执行），emit task_tree_node_created
    - spawn_and_wait: 执行已注册任务，emit started / completed / failed
    - list_tasks: 返回当前任务树概览（供 Orchestrator 自检）
    - get_tree_snapshot: 返回完整任务树 dict（用于 task_tree_snapshot 事件）
    """

    MAX_DEPTH = 3

    def __init__(
        self,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]],
        workers: Dict[str, Any],       # {name: WorkerConfig}
        toolkit: Any,                  # agentscope Toolkit
        model: Any,                    # ChatModelBase
        message_queue: Optional[asyncio.Queue] = None,
        depth_offset: int = 0,
    ):
        self._progress_callback = progress_callback
        self._workers = workers
        self._toolkit = toolkit
        self._model = model
        self._message_queue = message_queue
        self._depth_offset = depth_offset  # 父任务的深度，子 TaskManager 用来继承

        self._tasks: Dict[str, TaskNode] = {}       # task_id → TaskNode
        self._task_counter = 0

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def create_task(
        self,
        description: str,
        worker_name: str,
        input_data: Optional[dict] = None,
        parent_id: Optional[str] = None,
    ) -> str:
        """
        注册任务节点（不执行）。

        Returns:
            task_id
        """
        self._task_counter += 1
        task_id = f"task_{self._task_counter:03d}"

        # 计算深度
        depth = self._depth_offset
        if parent_id and parent_id in self._tasks:
            depth = self._tasks[parent_id].depth + 1

        node = TaskNode(
            task_id=task_id,
            description=description,
            worker_name=worker_name,
            input_data=input_data or {},
            parent_id=parent_id,
            depth=depth,
        )
        self._tasks[task_id] = node

        self._emit("task_tree_node_created", {
            "task_id": task_id,
            "parent_id": parent_id,
            "description": description,
            "worker_name": worker_name,
            "status": "pending",
            "depth": depth,
        })

        logger.info("[TaskManager] Created task %s: %s (worker=%s, depth=%d)",
                    task_id, description[:60], worker_name, depth)
        return task_id

    def spawn_and_wait(self, task_id: str, timeout: Optional[int] = None) -> str:
        """
        同步执行已注册的任务，等待完成。

        在独立线程 + 独立 event loop 中运行 Worker，避免 asyncio 嵌套运行问题。

        Returns:
            Worker 的输出文本（失败时返回 "ERROR: ..." 字符串）
        """
        if task_id not in self._tasks:
            return f"ERROR: task_id '{task_id}' not found. Use create_task() first."

        node = self._tasks[task_id]

        if node.depth >= self.MAX_DEPTH:
            error_msg = f"ERROR: max nesting depth ({self.MAX_DEPTH}) reached for task {task_id}"
            node.status = "failed"
            node.error = error_msg
            self._emit("task_tree_node_failed", {
                "task_id": task_id,
                "status": "failed",
                "error": error_msg,
            })
            return error_msg

        worker_config = self._workers.get(node.worker_name)
        if not worker_config:
            error_msg = f"ERROR: worker '{node.worker_name}' not found"
            node.status = "failed"
            node.error = error_msg
            self._emit("task_tree_node_failed", {
                "task_id": task_id,
                "status": "failed",
                "error": error_msg,
            })
            return error_msg

        # 标记为 running
        node.status = "running"
        node.started_at = time.time()
        self._emit("task_tree_node_started", {
            "task_id": task_id,
            "status": "running",
        })

        # 构建子 TaskManager（子任务会继承 workers/toolkit/model）
        child_task_manager = TaskManager(
            progress_callback=self._progress_callback,
            workers=self._workers,
            toolkit=self._toolkit,
            model=self._model,
            message_queue=self._message_queue,
            depth_offset=node.depth + 1,
        )

        async def _run_worker():
            # 当前线程为 Worker 子线程，抑制 hook 向前端推送流式输出。
            # Orchestrator 主线程不受影响（threading.local 线程隔离）。
            try:
                from hook import _suppress
            except ImportError:
                try:
                    from agent.hook import _suppress
                except ImportError:
                    _suppress = None
            if _suppress is not None:
                _suppress.push = True

            # 延迟导入避免循环依赖
            try:
                from worker.worker_runner import WorkerRunner, WorkerTask
            except ImportError:
                from worker_runner import WorkerRunner, WorkerTask

            runner = WorkerRunner(
                config=worker_config,
                model=self._model,
                toolkit=self._toolkit,
                progress_callback=self._progress_callback,
                message_queue=self._message_queue,
                task_manager=child_task_manager,
            )

            task = WorkerTask(
                session_id=None,
                worker_name=node.worker_name,
                task_description=node.description,
                input_data=node.input_data,
                context={
                    "orchestrator_task_id": task_id,
                    "depth": node.depth,
                },
            )

            result = await runner.run(task)
            return result

        # 在独立线程+独立 event loop 中运行，避免嵌套 asyncio.run 问题
        effective_timeout = timeout or 1800

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _run_worker())
                worker_result = future.result(timeout=effective_timeout)

            output = worker_result.output
            if output is None:
                output = ""
            elif isinstance(output, list):
                # Extract text from AgentScope content block list
                # e.g. [{'type': 'text', 'text': '...'}]
                text_parts = []
                for block in output:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                output = "\n".join(text_parts) if text_parts else str(output)
            elif not isinstance(output, str):
                output = str(output)

            # 前 500 字符作为摘要
            result_summary = output[:500] + ("..." if len(output) > 500 else "")

            node.status = "completed"
            node.result = result_summary
            node.completed_at = time.time()

            self._emit("task_tree_node_completed", {
                "task_id": task_id,
                "status": "completed",
                "result_summary": result_summary,
            })

            logger.info("[TaskManager] Task %s completed (%.1fs)",
                        task_id, node.completed_at - node.started_at)
            return output

        except Exception as exc:
            error_msg = str(exc)
            node.status = "failed"
            node.error = error_msg
            node.completed_at = time.time()

            self._emit("task_tree_node_failed", {
                "task_id": task_id,
                "status": "failed",
                "error": error_msg,
            })

            logger.error("[TaskManager] Task %s failed: %s", task_id, error_msg)
            return f"ERROR: {error_msg}"

    def spawn_batch_and_wait(
        self,
        task_ids: List[str],
        timeout: int = 600,
    ) -> str:
        """
        并发执行多个已注册任务，所有任务同时启动，互不阻塞。

        每个任务在独立线程 + 独立 event loop 中运行（与 spawn_and_wait 机制相同），
        线程数 = len(task_ids)。

        Args:
            task_ids: 已通过 create_task() 注册的 task_id 列表（最少 1 个）
            timeout:  单个任务超时秒数（默认 600s），超时视为失败

        Returns:
            JSON 字符串::

                {
                  "total": 4,
                  "succeeded": 3,
                  "failed": 1,
                  "results": [
                    {"task_id": "task_001", "status": "ok",    "output": "..."},
                    {"task_id": "task_002", "status": "error", "error": "timeout"}
                  ]
                }
        """
        if not task_ids:
            return json.dumps(
                {"total": 0, "succeeded": 0, "failed": 0, "results": []},
                ensure_ascii=False,
            )

        # 校验所有 task_id 是否已注册
        missing = [tid for tid in task_ids if tid not in self._tasks]
        if missing:
            error_results = [
                {"task_id": tid, "status": "error",
                 "error": f"task_id '{tid}' not found, use create_task() first"}
                for tid in task_ids
            ]
            return json.dumps(
                {"total": len(task_ids), "succeeded": 0,
                 "failed": len(task_ids), "results": error_results},
                ensure_ascii=False,
            )

        # 单次等待上限 = 任务超时 + 30s 线程启动缓冲
        wall_timeout = timeout + 30
        results: List[dict] = []

        logger.info(
            "[TaskManager] spawn_batch_and_wait: launching %d tasks in parallel (timeout=%ds)",
            len(task_ids), timeout,
        )

        with ThreadPoolExecutor(max_workers=len(task_ids)) as pool:
            # 同时提交所有任务
            futures = {
                tid: pool.submit(self.spawn_and_wait, tid, timeout)
                for tid in task_ids
            }

            # 按原始顺序收集结果（所有 future 已并发运行）
            for tid in task_ids:
                try:
                    output = futures[tid].result(timeout=wall_timeout)
                    # spawn_and_wait 失败时返回 "ERROR: ..." 字符串
                    if isinstance(output, str) and output.startswith("ERROR:"):
                        results.append({"task_id": tid, "status": "error", "error": output[:300]})
                    else:
                        # 批量执行场景：Worker 结果已写入文件，Orchestrator 只需摘要
                        # 完整内容通过 list_output_files / read_output_file 获取
                        # 截断为 300 字符，避免 N 份完整输出堆满 Orchestrator 上下文
                        summary = output[:300] + ("..." if len(output) > 300 else "")
                        results.append({"task_id": tid, "status": "ok", "summary": summary})
                except TimeoutError:
                    results.append({
                        "task_id": tid, "status": "error",
                        "error": f"task timed out after {wall_timeout}s",
                    })
                except Exception as exc:
                    results.append({"task_id": tid, "status": "error", "error": str(exc)[:300]})

        succeeded = sum(1 for r in results if r["status"] == "ok")
        failed = len(results) - succeeded

        logger.info(
            "[TaskManager] spawn_batch_and_wait done: %d succeeded, %d failed",
            succeeded, failed,
        )

        return json.dumps(
            {"total": len(task_ids), "succeeded": succeeded,
             "failed": failed, "results": results},
            ensure_ascii=False,
        )

    def list_tasks(self) -> str:
        """返回当前任务树 JSON 字符串（供 Orchestrator 自我检查用）"""
        if not self._tasks:
            return "No tasks registered yet."

        lines = []
        for node in self._tasks.values():
            indent = "  " * node.depth
            status_icon = {
                "pending": "○",
                "running": "●",
                "completed": "✓",
                "failed": "✗",
            }.get(node.status, "?")

            line = f"{indent}{status_icon} [{node.task_id}] {node.description[:60]}"
            if node.worker_name:
                line += f" ({node.worker_name})"
            if node.status == "failed" and node.error:
                line += f"\n{indent}  ERROR: {node.error[:100]}"
            elif node.status == "completed" and node.result:
                line += f"\n{indent}  Result: {node.result[:100]}"
            lines.append(line)

        return "\n".join(lines)

    def get_tree_snapshot(self) -> dict:
        """返回完整任务树 dict，用于 task_tree_snapshot 事件"""
        return {
            "nodes": [node.to_dict() for node in self._tasks.values()]
        }

    def get_all_tasks(self) -> Dict[str, TaskNode]:
        return self._tasks

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _emit(self, event_type: str, data: dict) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(event_type, data)
            except Exception as exc:
                logger.warning("[TaskManager] Progress callback failed: %s", exc)

    def _task_manager_to_phase_results(self) -> List[dict]:
        """
        将任务树转换为 phase_results 格式，供 AgentLoop 的 GoalEvaluator 使用。
        """
        results = []
        for node in self._tasks.values():
            results.append({
                "phase_name": node.description[:60],
                "status": node.status if node.status in ("completed", "failed") else "partial",
                "worker_results": {
                    node.worker_name: {
                        "task_id": node.task_id,
                        "worker_name": node.worker_name,
                        "status": node.status,
                        "output": node.result or "",
                        "error": node.error,
                    }
                }
            })
        return results
