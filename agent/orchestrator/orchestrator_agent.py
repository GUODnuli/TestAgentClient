# -*- coding: utf-8 -*-
"""
OrchestratorAgent

ReAct 模式的自主规划器，替换静态的 TaskPlanner + PhaseScheduler。

执行流程:
  1. Scout  — 用 read_file/glob_files/grep_files 探索环境
  2. Decompose — 用 create_task() 拆解任务
  3. Execute — 用 spawn_and_wait() / spawn_task() 驱动 Worker
  4. Verify & Finalize — 输出结构化 JSON 摘要
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit

from .task_manager import TaskManager
from .orchestrator_tools import make_orchestrator_tools

logger = logging.getLogger(__name__)

# 尝试导入 formatter helper
try:
    from model import get_formatter
except ImportError:
    get_formatter = None


def _get_formatter(model: ChatModelBase):
    """根据模型类型推断 formatter"""
    if get_formatter is None:
        return None
    model_class = type(model).__name__.lower()
    if "dashscope" in model_class:
        return get_formatter("dashscope")
    elif "openai" in model_class:
        return get_formatter("openai")
    elif "anthropic" in model_class:
        return get_formatter("anthropic")
    elif "gemini" in model_class:
        return get_formatter("gemini")
    elif "ollama" in model_class:
        return get_formatter("ollama")
    return get_formatter("dashscope")


class OrchestratorAgent:
    """
    自主规划器 — 替换 TaskPlanner + PhaseScheduler。

    使用 ReActAgent 先探索环境，再动态拆解任务，再派发 Worker 执行。
    """

    def __init__(
        self,
        model: ChatModelBase,
        toolkit: Toolkit,
        workers: Dict[str, Any],          # {name: WorkerConfig}
        skills: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        message_queue: Optional[asyncio.Queue] = None,
        max_iters: int = 30,
        timeout: int = 3600,
        prompts_dir: Optional[Path] = None,
    ):
        self.model = model
        self._workers = workers
        self._skills = skills
        self._progress_callback = progress_callback
        self._message_queue = message_queue
        self._max_iters = max_iters
        self._timeout = timeout
        self._prompts_dir = prompts_dir or Path("prompts/orchestrator")

        # 构建 TaskManager
        self.task_manager = TaskManager(
            progress_callback=progress_callback,
            workers=workers,
            toolkit=toolkit,
            model=model,
            message_queue=message_queue,
        )

        # 构建 Orchestrator 专用 Toolkit
        self._toolkit = self._build_toolkit(toolkit)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def run(
        self,
        objective: str,
        context: Optional[Dict[str, Any]] = None,
        loop_context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        运行 OrchestratorAgent ReAct 循环。

        Returns:
            结构化结果 dict，兼容 AgentLoop 的 _extract_summary。
        """
        # 发送初始空任务树快照
        self._emit("task_tree_snapshot", self.task_manager.get_tree_snapshot())

        prompt = self._build_prompt(objective, context or {}, loop_context)
        sys_prompt = self._load_system_prompt()
        formatter = _get_formatter(self.model)

        agent = ReActAgent(
            name="Orchestrator",
            sys_prompt=sys_prompt,
            model=self.model,
            formatter=formatter,
            toolkit=self._toolkit,
            memory=InMemoryMemory(),
            max_iters=self._max_iters,
        )

        # 启用消息队列（将 Orchestrator 的思考/输出流到前端）
        if self._message_queue is not None:
            agent.set_msg_queue_enabled(True, self._message_queue)

        logger.info("[Orchestrator] Starting ReAct loop for objective: %s", objective[:80])

        try:
            response = await asyncio.wait_for(
                agent(Msg(name="user", content=prompt, role="user")),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[Orchestrator] ReAct loop timed out after %ds", self._timeout)
            return self._build_error_result(objective, "Orchestrator timed out")
        except Exception as exc:
            logger.error("[Orchestrator] ReAct loop failed: %s", exc, exc_info=True)
            return self._build_error_result(objective, str(exc))

        # 解析最终输出中的 JSON 摘要
        output_text = ""
        if response is not None:
            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            output_text += block.get("text", "")
                elif isinstance(content, str):
                    output_text = content
            elif isinstance(response, str):
                output_text = response

        return self._parse_result(objective, output_text)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _build_toolkit(self, base_toolkit: Toolkit) -> Toolkit:
        """
        构建 Orchestrator 专用 toolkit。

        从 base_toolkit 中提取 read_file / glob_files / grep_files（通过名称匹配），
        加入任务管理工具（create_task, spawn_and_wait, spawn_task, list_tasks, get_available_workers）。

        如果无法提取，回退到从 tool.base 模块直接导入。
        """
        orch_toolkit = Toolkit()
        registered = set()

        # 策略 1: 尝试通过 Toolkit 内部属性提取只读工具（含 write_output_file / read_output_file / list_output_files）
        READ_TOOL_NAMES = {
            "read_file", "glob_files", "grep_files",
            "write_output_file", "read_output_file", "list_output_files",
        }
        try:
            # agentscope Toolkit 可能将工具存储在不同属性下
            tools_dict = None
            for attr in ("_tools", "tools", "_functions", "functions"):
                candidate = getattr(base_toolkit, attr, None)
                if isinstance(candidate, dict):
                    tools_dict = candidate
                    break

            if tools_dict:
                for tool_name, tool_obj in tools_dict.items():
                    if tool_name in READ_TOOL_NAMES:
                        func = (
                            getattr(tool_obj, "_func", None)
                            or getattr(tool_obj, "func", None)
                            or (tool_obj if callable(tool_obj) else None)
                        )
                        if func is not None and callable(func):
                            try:
                                orch_toolkit.register_tool_function(func)
                                registered.add(tool_name)
                                logger.debug("[Orchestrator] Registered from toolkit: %s", tool_name)
                            except Exception as exc:
                                logger.warning("[Orchestrator] Could not register %s: %s", tool_name, exc)
        except Exception as exc:
            logger.debug("[Orchestrator] Toolkit introspection failed: %s", exc)

        # 策略 2: 直接从 tool.base 模块导入（回退）
        # write_output_file / read_output_file / list_output_files 是工厂函数生成的闭包，不在 tool.base 中，跳过
        still_needed = (READ_TOOL_NAMES - registered) - {
            "write_output_file", "read_output_file", "list_output_files"
        }
        if still_needed:
            try:
                from tool.base import read_file, glob_files, grep_files
                fallback_map = {
                    "read_file": read_file,
                    "glob_files": glob_files,
                    "grep_files": grep_files,
                }
                for name in still_needed:
                    if name in fallback_map:
                        try:
                            orch_toolkit.register_tool_function(fallback_map[name])
                            registered.add(name)
                            logger.debug("[Orchestrator] Registered via fallback: %s", name)
                        except Exception as exc:
                            logger.warning("[Orchestrator] Fallback registration failed for %s: %s", name, exc)
            except ImportError as exc:
                logger.warning("[Orchestrator] Could not import tool.base: %s", exc)

        # 注册任务管理工具
        available_worker_names = list(self._workers.keys())
        orchestrator_tools = make_orchestrator_tools(self.task_manager, available_worker_names)
        for tool_func in orchestrator_tools:
            orch_toolkit.register_tool_function(tool_func)
            registered.add(tool_func.__name__)

        logger.info("[Orchestrator] Toolkit built with tools: %s", sorted(registered))
        return orch_toolkit

    def _build_prompt(
        self,
        objective: str,
        context: Dict[str, Any],
        loop_context: Optional[Any],
    ) -> str:
        """构建 Orchestrator 的用户提示词"""
        parts = []

        # Loop context (multi-round scenario)
        if loop_context is not None:
            loop_summary = _extract_loop_context_summary(loop_context)
            if loop_summary:
                parts.append(
                    "## Previous Iteration Context\n\n"
                    "The following work was completed in a previous iteration. "
                    "Build on it rather than repeating it.\n\n"
                    + loop_summary
                )

        # Workspace context
        workspace = context.get("workspace", "")
        if workspace:
            parts.append(f"## Workspace\n\n`{workspace}`")

        # Skills available
        if self._skills:
            skill_names = [s.get("name", "") for s in self._skills if s.get("name")]
            if skill_names:
                parts.append(f"## Available Skills\n\n" + "\n".join(f"- {n}" for n in skill_names))

        # Workers available
        if self._workers:
            lines = []
            for name, config in self._workers.items():
                desc = getattr(config, "description", "") or ""
                lines.append(f"- **{name}**: {desc}")
            parts.append("## Available Workers\n\n" + "\n".join(lines))

        # Objective
        parts.append(f"## Objective\n\n{objective}")

        parts.append(
            "\n\nBegin by scouting the environment (Phase 1), then decompose and execute."
        )

        return "\n\n".join(parts)

    def _load_system_prompt(self) -> str:
        """加载 orchestrator.md 系统提示词"""
        prompt_path = self._prompts_dir / "orchestrator.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # Fallback minimal prompt
        logger.warning(
            "[Orchestrator] System prompt not found at %s, using minimal fallback",
            prompt_path,
        )
        return (
            "You are an autonomous task orchestrator. "
            "Scout the environment, decompose the objective into tasks, "
            "execute workers, and output a JSON summary when done."
        )

    def _parse_result(self, objective: str, output_text: str) -> Dict[str, Any]:
        """解析 Orchestrator 最终输出中的 JSON 摘要"""
        # 尝试提取 JSON code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output_text, re.DOTALL)
        if json_match:
            try:
                summary = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                summary = {}
        else:
            # 尝试直接解析末尾的 JSON 对象
            json_match2 = re.search(r"\{[^{}]*\"objective\"[^{}]*\}", output_text, re.DOTALL)
            if json_match2:
                try:
                    summary = json.loads(json_match2.group(0))
                except json.JSONDecodeError:
                    summary = {}
            else:
                summary = {}

        # 补充默认字段
        if not summary.get("objective"):
            summary["objective"] = objective
        if "completed_tasks" not in summary:
            summary["completed_tasks"] = [
                node.description[:80]
                for node in self.task_manager.get_all_tasks().values()
                if node.status == "completed"
            ]
        if "remaining_gaps" not in summary:
            summary["remaining_gaps"] = [
                node.description[:80]
                for node in self.task_manager.get_all_tasks().values()
                if node.status == "failed"
            ]
        if "raw_output" not in summary:
            summary["raw_output"] = output_text[:2000]

        return summary

    def _build_error_result(self, objective: str, error: str) -> Dict[str, Any]:
        return {
            "objective": objective,
            "completed_tasks": [],
            "key_artifacts": {},
            "remaining_gaps": [f"Orchestrator failed: {error}"],
            "error": error,
        }

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(event_type, data)
            except Exception as exc:
                logger.warning("[Orchestrator] Progress callback failed: %s", exc)


def _extract_loop_context_summary(loop_context: Any) -> str:
    """从 LoopContext 提取摘要文本"""
    if loop_context is None:
        return ""
    try:
        if hasattr(loop_context, "to_dict"):
            ctx_dict = loop_context.to_dict()
        elif isinstance(loop_context, dict):
            ctx_dict = loop_context
        else:
            return str(loop_context)[:500]

        # LoopContext.to_dict() 结构：
        # {"iteration": N, "iteration_summaries": [{completed_tasks, remaining_gaps, ...}], ...}
        all_completed: list = []
        all_gaps: list = []
        seen_c: set = set()
        seen_g: set = set()

        for summary_dict in ctx_dict.get("iteration_summaries", []):
            for task in summary_dict.get("completed_tasks", []):
                if task not in seen_c:
                    seen_c.add(task)
                    all_completed.append(task)
            for gap in summary_dict.get("remaining_gaps", []):
                if gap not in seen_g:
                    seen_g.add(gap)
                    all_gaps.append(gap)

        parts = []
        if all_completed:
            parts.append("Completed tasks: " + "; ".join(all_completed[:10]))
        if all_gaps:
            parts.append("Remaining gaps: " + "; ".join(all_gaps[:5]))
        return "\n".join(parts)
    except Exception:
        return ""
