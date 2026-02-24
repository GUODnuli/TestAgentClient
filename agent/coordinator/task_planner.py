# -*- coding: utf-8 -*-
"""
任务规划器

使用 LLM 将用户请求分解为可执行的 Worker 任务序列。
"""
import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from inspect import isasyncgen
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentscope.model import ChatModelBase

logger = logging.getLogger(__name__)


@dataclass
class WorkerAssignment:
    """Worker 任务分配"""

    worker: str  # Worker 名称
    task: str  # 任务描述
    input: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "worker": self.worker,
            "task": self.task,
            "input": self.input,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerAssignment":
        """从字典创建"""
        return cls(
            worker=data.get("worker", ""),
            task=data.get("task", ""),
            input=data.get("input", {}),
            depends_on=data.get("depends_on", []),
        )


@dataclass
class Phase:
    """执行阶段"""

    phase: int  # 阶段编号
    name: str  # 阶段名称
    workers: List[WorkerAssignment] = field(default_factory=list)
    parallel: bool = False  # 是否并行执行
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "phase": self.phase,
            "name": self.name,
            "workers": [w.to_dict() for w in self.workers],
            "parallel": self.parallel,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Phase":
        """从字典创建"""
        workers = [
            WorkerAssignment.from_dict(w)
            for w in data.get("workers", [])
        ]
        return cls(
            phase=data.get("phase", 0),
            name=data.get("name", ""),
            workers=workers,
            parallel=data.get("parallel", False),
            depends_on=data.get("depends_on", []),
        )


@dataclass
class ExecutionPlan:
    """执行计划"""

    task_id: str
    objective: str
    context: Dict[str, Any] = field(default_factory=dict)
    phases: List[Phase] = field(default_factory=list)
    completion_criteria: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "context": self.context,
            "phases": [p.to_dict() for p in self.phases],
            "completion_criteria": self.completion_criteria,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        """从字典创建"""
        phases = [Phase.from_dict(p) for p in data.get("phases", [])]
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            objective=data.get("objective", ""),
            context=data.get("context", {}),
            phases=phases,
            completion_criteria=data.get("completion_criteria", ""),
        )


class TaskPlanner:
    """
    任务规划器

    使用 LLM 分析用户请求，生成结构化的执行计划。
    """

    def __init__(
        self,
        model: ChatModelBase,
        prompts_dir: Optional[Path] = None,
    ):
        """
        初始化任务规划器

        Args:
            model: LLM 模型实例
            prompts_dir: 提示词目录
        """
        self.model = model
        self.prompts_dir = Path(prompts_dir) if prompts_dir else None

        # 加载提示词模板
        self._system_prompt = self._load_prompt("task_decomposition.md")
        self._continuation_system_prompt = self._build_continuation_system_prompt()

    async def create_plan(
        self,
        objective: str,
        context: Dict[str, Any],
        available_workers: List[Dict[str, Any]],
        available_skills: List[Dict[str, Any]],
        loop_context: Optional[Any] = None,   # LoopContext from AgentLoop; None on first iteration
    ) -> ExecutionPlan:
        """
        创建执行计划

        Args:
            objective: 任务目标
            context: 上下文信息
            available_workers: 可用 Worker 列表
            available_skills: 可用 Skill 列表
            loop_context: AgentLoop 传入的迭代上下文（续写模式）

        Returns:
            执行计划
        """
        # Choose prompt mode based on whether we're in a continuation iteration
        is_continuation = loop_context is not None and loop_context.iteration > 0

        if is_continuation:
            system_prompt = self._continuation_system_prompt
            prompt = self._build_continuation_prompt(
                objective=objective,
                context=context,
                workers=available_workers,
                skills=available_skills,
                loop_context=loop_context,
            )
        else:
            system_prompt = self._system_prompt
            prompt = self._build_prompt(
                objective=objective,
                context=context,
                workers=available_workers,
                skills=available_skills,
            )

        logger.debug("Task planner prompt (continuation=%s):\n%s", is_continuation, prompt[:500])

        # 调用 LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        # 调用模型并处理流式响应
        response = await self._call_model(messages)

        # 解析响应
        plan_dict = self._parse_response(response)

        # 创建计划对象
        plan = ExecutionPlan(
            task_id=str(uuid.uuid4()),
            objective=objective,
            context=context,
            phases=[Phase.from_dict(p) for p in plan_dict.get("phases", [])],
            completion_criteria=plan_dict.get("completion_criteria", ""),
        )

        # 验证计划
        self._validate_plan(plan, available_workers)

        return plan

    def _build_prompt(
        self,
        objective: str,
        context: Dict[str, Any],
        workers: List[Dict[str, Any]],
        skills: List[Dict[str, Any]],
    ) -> str:
        """
        构建规划提示词

        Args:
            objective: 任务目标
            context: 上下文
            workers: 可用 Workers
            skills: 可用 Skills

        Returns:
            提示词
        """
        parts = []

        # 任务目标
        parts.append(f"## Task Objective\n{objective}")

        # 上下文信息
        if context:
            parts.append(f"## Context\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```")

        # 可用 Workers
        workers_desc = []
        for w in workers:
            tools_str = ", ".join(w.get("tools", [])) or "none"
            workers_desc.append(
                f"- **{w['name']}**: {w.get('description', 'No description')}\n"
                f"  - Tools: {tools_str}\n"
                f"  - Mode: {w.get('mode', 'react')}"
            )
        parts.append(f"## Available Workers\n" + "\n".join(workers_desc))

        # 可用 Skills
        if skills:
            skills_desc = []
            for s in skills:
                tags_str = ", ".join(s.get("tags", [])) or "none"
                skills_desc.append(
                    f"- **{s['name']}**: {s.get('description', 'No description')}\n"
                    f"  - Tags: {tags_str}"
                )
            parts.append(f"## Available Skills\n" + "\n".join(skills_desc))

        # 输出格式要求
        parts.append("""## Output Format

Please generate an execution plan in JSON format:

```json
{
  "phases": [
    {
      "phase": 1,
      "name": "Phase name",
      "parallel": false,
      "workers": [
        {
          "worker": "worker_name",
          "task": "Task description for this worker",
          "input": {"key": "value"},
          "depends_on": []
        }
      ],
      "depends_on": []
    }
  ],
  "completion_criteria": "Description of what constitutes task completion"
}
```

Guidelines:
1. Use only workers from the Available Workers list
2. Set `parallel: true` for workers that can run simultaneously
3. Use `depends_on` to specify dependencies (reference phase numbers like "phase_1")
4. Use `$phase_N.output` syntax to reference outputs from previous phases
5. Keep tasks atomic and focused
6. Consider error scenarios and include validation steps if needed
""")

        return "\n\n".join(parts)

    def _build_continuation_system_prompt(self) -> str:
        """System prompt used for continuation (iteration > 0) planning."""
        return """\
You are a continuation planning assistant for an autonomous agent loop.
Previous execution iterations have completed some work toward the objective.
Your job is to plan ONLY the remaining work needed to bridge the gap between
the current state and the fully achieved objective.

Planning principles:
1. Do NOT repeat steps that were already successfully completed
2. Target each phase specifically at the remaining_gaps identified by the evaluator
3. Reference existing artifacts (file paths, test results) in task descriptions when relevant
4. Keep each phase atomic and focused on a single concern
5. If the remaining work is small, consolidate into fewer phases rather than over-decomposing
"""

    def _build_continuation_prompt(
        self,
        objective: str,
        context: Dict[str, Any],
        workers: List[Dict[str, Any]],
        skills: List[Dict[str, Any]],
        loop_context: Any,
    ) -> str:
        """
        Build the user message for a continuation iteration.

        Includes:
        - Final iteration warning (if approaching max_iterations)
        - Accumulated iteration history (compressed)
        - Remaining gaps
        - Available workers/skills (same format as standard prompt)
        """
        parts = []

        # Final iteration warning block
        max_iters = getattr(loop_context, 'max_iterations', None)
        current_iter = loop_context.iteration
        if max_iters is not None and current_iter >= max_iters - 2:
            parts.append(
                f"IMPORTANT: This is iteration {current_iter + 1} of {max_iters} "
                f"(the FINAL or second-to-last iteration).\n\n"
                "You must:\n"
                "1. Summarize all work completed across all previous iterations\n"
                "2. Complete any remaining critical tasks if feasible within this iteration\n"
                "3. DO NOT start new long-running tool calls that cannot finish in this session\n"
                "4. Produce a clear final summary of: what was accomplished, what remains unfinished,\n"
                "   and specific recommendations for the user on next steps\n"
            )

        # Iteration history
        parts.append(f"## Original Objective\n{objective}")
        parts.append(f"## Execution History\n{loop_context.to_context_string()}")

        # Remaining gaps summary
        all_gaps = loop_context.all_remaining_gaps
        if all_gaps:
            gap_list = "\n".join(f"- {g}" for g in all_gaps)
            parts.append(f"## Remaining Gaps (what still needs to be done)\n{gap_list}")
        else:
            parts.append("## Remaining Gaps\nNot yet assessed — plan all unfinished work.")

        # Context
        if context:
            parts.append(
                f"## Context\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```"
            )

        # Available Workers
        workers_desc = []
        for w in workers:
            tools_str = ", ".join(w.get("tools", [])) or "none"
            workers_desc.append(
                f"- **{w['name']}**: {w.get('description', 'No description')}\n"
                f"  - Tools: {tools_str}\n"
                f"  - Mode: {w.get('mode', 'react')}"
            )
        parts.append("## Available Workers\n" + "\n".join(workers_desc))

        # Available Skills
        if skills:
            skills_desc = []
            for s in skills:
                tags_str = ", ".join(s.get("tags", [])) or "none"
                skills_desc.append(
                    f"- **{s['name']}**: {s.get('description', 'No description')}\n"
                    f"  - Tags: {tags_str}"
                )
            parts.append("## Available Skills\n" + "\n".join(skills_desc))

        # Output format
        parts.append("""\
## Output Format

Generate a continuation execution plan in JSON format targeting ONLY the remaining gaps:

```json
{
  "phases": [
    {
      "phase": 1,
      "name": "Phase name",
      "parallel": false,
      "workers": [
        {
          "worker": "worker_name",
          "task": "Task description for this worker",
          "input": {"key": "value"},
          "depends_on": []
        }
      ],
      "depends_on": []
    }
  ],
  "completion_criteria": "Description of what constitutes task completion"
}
```

Guidelines:
1. Use only workers from the Available Workers list
2. Focus exclusively on the Remaining Gaps listed above
3. Set `parallel: true` for workers that can run simultaneously
4. Use `depends_on` to specify dependencies (reference phase numbers like "phase_1")
5. Keep tasks atomic and focused
""")

        return "\n\n".join(parts)

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """
        解析 LLM 响应

        Args:
            response: LLM 响应

        Returns:
            解析后的计划字典
        """
        # 获取响应文本
        if hasattr(response, "text"):
            text = response.text
        elif hasattr(response, "content"):
            text = response.content
        elif isinstance(response, dict):
            text = response.get("content", str(response))
        else:
            text = str(response)

        # 尝试提取 JSON
        # 查找 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个文本
            json_str = text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse plan JSON: %s", exc)
            # 返回默认计划
            return {
                "phases": [
                    {
                        "phase": 1,
                        "name": "Default execution",
                        "workers": [
                            {
                                "worker": "planner",
                                "task": "Analyze the task and determine the best approach",
                                "input": {"objective": "Unknown"},
                                "depends_on": [],
                            }
                        ],
                        "parallel": False,
                        "depends_on": [],
                    }
                ],
                "completion_criteria": "Task analysis completed",
            }

    def _validate_plan(
        self,
        plan: ExecutionPlan,
        available_workers: List[Dict[str, Any]],
    ) -> None:
        """
        验证执行计划

        Args:
            plan: 执行计划
            available_workers: 可用 Workers

        Raises:
            ValueError: 计划无效
        """
        worker_names = {w["name"] for w in available_workers}

        for phase in plan.phases:
            for assignment in phase.workers:
                if assignment.worker not in worker_names:
                    logger.warning(
                        "Unknown worker '%s' in plan, may cause execution failure",
                        assignment.worker
                    )

        # 检查依赖循环
        self._check_dependency_cycle(plan)

    def _check_dependency_cycle(self, plan: ExecutionPlan) -> None:
        """
        检查依赖循环

        Args:
            plan: 执行计划

        Raises:
            ValueError: 存在循环依赖
        """
        # 构建依赖图
        deps = {}
        for phase in plan.phases:
            phase_key = f"phase_{phase.phase}"
            deps[phase_key] = set(phase.depends_on)

        # DFS 检测循环
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for dep in deps.get(node, set()):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for phase_key in deps:
            if phase_key not in visited:
                if has_cycle(phase_key):
                    raise ValueError(f"Circular dependency detected in plan")

    async def _call_model(self, messages: List[Dict[str, str]]) -> Any:
        """
        调用模型并处理流式响应

        Args:
            messages: 消息列表

        Returns:
            模型响应（已提取文本内容）
        """
        result = self.model(messages)

        # 处理协程
        if asyncio.iscoroutine(result):
            result = await result

        # 处理异步生成器（流式响应）
        if isasyncgen(result):
            collected = None
            async for chunk in result:
                collected = chunk
            result = collected

        # 提取文本内容
        if result is not None:
            # 如果是 dict-like 对象，提取 content
            if hasattr(result, 'get'):
                content = result.get('content', '')
                if isinstance(content, list) and len(content) > 0:
                    # 内容是列表格式，提取第一个文本项
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            return item.get('text', '')
                    return str(content)
                return content
            # 如果有 text 属性
            if hasattr(result, 'text'):
                return result.text
            # 如果有 content 属性
            if hasattr(result, 'content'):
                return result.content

        return result

    def _load_prompt(self, filename: str) -> str:
        """
        加载提示词模板

        Args:
            filename: 文件名

        Returns:
            提示词内容
        """
        if self.prompts_dir:
            prompt_path = self.prompts_dir / filename
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")

        # 返回默认提示词
        return self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        """
        获取默认系统提示词

        Returns:
            默认提示词
        """
        return """You are a Task Planner specialized in decomposing complex tasks into executable worker assignments.

## Your Role

- Analyze user requests and break them down into manageable phases
- Assign appropriate workers to each task
- Identify dependencies between tasks
- Optimize execution order for efficiency
- Consider error scenarios and include validation steps

## Decomposition Principles

1. **Atomic Tasks**: Each worker assignment should be a single, focused task
2. **Clear Dependencies**: Explicitly define what each task depends on
3. **Parallel Opportunities**: Identify tasks that can run simultaneously
4. **Validation**: Include verification steps for critical operations
5. **Incremental Progress**: Structure phases to show incremental progress

## Worker Selection Guidelines

- Choose workers based on their capabilities (tools available)
- Use `planner` for initial analysis and planning
- Use `analyzer` for content/code analysis
- Use `executor` for executing operations
- Use `reporter` for generating reports and summaries
- Use `validator` for verification tasks

## Output Requirements

Always output a valid JSON execution plan with:
- Numbered phases in execution order
- Worker assignments with clear task descriptions
- Input data including references to previous phase outputs ($phase_N.output)
- Parallel flag for tasks that can run concurrently
- Completion criteria describing what constitutes task completion
"""
