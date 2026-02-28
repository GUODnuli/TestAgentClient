# -*- coding: utf-8 -*-
"""
Coordinator Agent 入口文件

使用 Coordinator 模式分解任务并调度多个 Worker 执行。
"""
import asyncio
import io
import os
import socket
import sys

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    # Set console code page to UTF-8
    os.system('chcp 65001 >nul 2>&1')
    # Reconfigure stdout/stderr to use UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from datetime import datetime
from pathlib import Path
from typing import Optional

# Force IPv4 to avoid connection issues with Clash TUN Fake IP mode
_original_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(*args, **kwargs):
    results = _original_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in results if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else results


socket.getaddrinfo = _ipv4_only_getaddrinfo

# 确保项目根目录和 agent 目录都在 Python 路径中
project_root = Path(__file__).parent.parent
agent_dir = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

import json5
from agentscope.tool import Toolkit

# Base tools
from tool.base import (
    ToolConfig,
    execute_shell,
    read_file,
    write_file,
    edit_file,
    glob_files,
    grep_files,
    web_fetch,
)
from tool.utils import list_uploaded_files
from tool_registry import setup_toolkit
from mcp_loader import close_mcp_servers
from args import get_args
from model import get_model, get_model_non_streaming
from hook import AgentHooks

# Coordinator imports
from coordinator import Coordinator, CoordinatorConfig


def _create_progress_callback(studio_url: str, reply_id: str):
    """创建 Coordinator 进度回调函数"""
    import httpx

    # 用于追踪序列号
    sequence_counter = {"value": 0}

    def callback(event_type: str, data: dict):
        """将 Coordinator 事件推送到前端"""
        if not studio_url or not reply_id:
            return

        sequence_counter["value"] += 1
        events = []

        # 根据事件类型决定如何推送
        if event_type == "worker_text":
            # Worker 文本输出
            content = data.get("content", "")
            if content:
                events.append({
                    "type": "text",
                    "content": content,
                    "sequence": sequence_counter["value"],
                })

        elif event_type == "worker_thinking":
            # Worker 思考过程
            content = data.get("content", "")
            if content:
                events.append({
                    "type": "thinking",
                    "content": content,
                    "sequence": sequence_counter["value"],
                })

        elif event_type == "worker_tool_call":
            # Worker 工具调用 - 复用前端 ToolCallCard
            events.append({
                "type": "tool_call",
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "input": data.get("input", {}),
                "sequence": sequence_counter["value"],
            })

        elif event_type == "worker_tool_result":
            # Worker 工具执行结果 - 复用前端 ToolCallCard
            events.append({
                "type": "tool_result",
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "output": data.get("output", ""),
                "success": data.get("success", True),
                "sequence": sequence_counter["value"],
            })

        elif event_type == "phase_started":
            # Phase 开始 - 发送大标题到对话流
            phase_num = data.get("phase", 1)
            phase_name = data.get("name", f"Phase {phase_num}")
            workers = data.get("workers", [])
            workers_str = ", ".join(workers) if workers else ""

            # 生成 Markdown 格式的阶段标题
            title_text = f"\n\n---\n\n## 📋 阶段 {phase_num}: {phase_name}\n"
            if workers_str:
                title_text += f"*Workers: {workers_str}*\n"
            title_text += "\n"

            events.append({
                "type": "text",
                "content": title_text,
                "sequence": sequence_counter["value"],
            })

            # 同时发送 coordinator_event（用于更新侧边栏）
            sequence_counter["value"] += 1
            events.append({
                "type": "coordinator_event",
                "event_type": event_type,
                "data": data,
                "sequence": sequence_counter["value"],
            })

        elif event_type == "phase_completed":
            # Phase 完成 - 作为 coordinator_event（用于更新侧边栏）
            events.append({
                "type": "coordinator_event",
                "event_type": event_type,
                "data": data,
                "sequence": sequence_counter["value"],
            })

        elif event_type == "plan_created":
            # 执行计划创建 - 用于显示侧边栏
            events.append({
                "type": "coordinator_event",
                "event_type": event_type,
                "data": data,
                "sequence": sequence_counter["value"],
            })

        elif event_type == "task_tree_node_created":
            # 新任务树节点出现
            events.append({
                "type": "coordinator_event",
                "event_type": event_type,
                "data": data,   # {task_id, parent_id, description, worker_name, status, depth}
                "sequence": sequence_counter["value"],
            })

        elif event_type in (
            "task_tree_node_started",
            "task_tree_node_completed",
            "task_tree_node_failed",
            "task_tree_snapshot",
        ):
            # 任务树状态变更 / 全量快照
            events.append({
                "type": "coordinator_event",
                "event_type": event_type,
                "data": data,
                "sequence": sequence_counter["value"],
            })

        else:
            # 其他事件作为 coordinator_event
            events.append({
                "type": "coordinator_event",
                "event_type": event_type,
                "data": data,
                "sequence": sequence_counter["value"],
            })

        if not events:
            return

        payload = {
            "replyId": reply_id,
            "events": events,
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{studio_url}/trpc/pushMessageToChatAgent",
                    json=payload,
                )
        except Exception as e:
            print(f"[Hook Warning] Failed to push coordinator event: {e}")

    return callback


def _push_coordinator_result_to_frontend(studio_url: str, reply_id: str, result: dict):
    """将 Coordinator / AgentLoop 执行结果推送到前端"""
    import httpx

    if not studio_url or not reply_id:
        return

    # 支持 AgentLoop 结果格式和原始 Coordinator 结果格式
    is_loop_result = "iterations_run" in result

    summary_parts = []

    if is_loop_result:
        achieved = result.get("achieved", False)
        iterations_run = result.get("iterations_run", 1)
        error = result.get("error")

        summary_parts.append(f"## AgentLoop 执行完成\n")
        summary_parts.append(f"**状态**: {'已达成目标' if achieved else '目标未完全达成'}\n")
        summary_parts.append(f"**迭代次数**: {iterations_run}\n")

        if error:
            summary_parts.append(f"**错误**: {error}\n")

        # Final evaluation
        final_eval = result.get("final_evaluation", {})
        if final_eval:
            reason = final_eval.get("reason", "")
            confidence = final_eval.get("confidence", 0)
            if reason:
                summary_parts.append(f"**评估**: {reason} (置信度: {confidence:.0%})\n")

        # Completed tasks
        completed_tasks = result.get("completed_tasks", [])
        if completed_tasks:
            summary_parts.append(f"\n### 已完成任务 ({len(completed_tasks)} 项)\n")
            for task in completed_tasks[:10]:  # 最多显示 10 项
                summary_parts.append(f"- {task}\n")
            if len(completed_tasks) > 10:
                summary_parts.append(f"- ... 共 {len(completed_tasks)} 项\n")

        # Remaining gaps
        remaining = final_eval.get("remaining_gaps", [])
        if remaining:
            summary_parts.append(f"\n### 剩余工作\n")
            for gap in remaining:
                summary_parts.append(f"- {gap}\n")
    else:
        # Original coordinator format (backward compat)
        status = result.get("status", "unknown")
        error = result.get("error")

        summary_parts.append(f"## Coordinator 执行完成\n")
        summary_parts.append(f"**状态**: {status}\n")

        if error:
            summary_parts.append(f"**错误**: {error}\n")

        phase_results = result.get("phase_results", [])
        if phase_results:
            summary_parts.append(f"\n### 执行阶段 ({len(phase_results)} 个)\n")
            for i, phase in enumerate(phase_results, 1):
                phase_name = phase.get("phase_name", f"Phase {i}")
                phase_status = phase.get("status", "unknown")
                summary_parts.append(f"- **{phase_name}**: {phase_status}\n")

                worker_results = phase.get("worker_results", {})
                for worker_name, worker_result in worker_results.items():
                    worker_status = worker_result.get("status", "unknown")
                    summary_parts.append(f"  - {worker_name}: {worker_status}\n")

    summary_text = "".join(summary_parts)

    # 推送文本结果
    events = [{
        "type": "text",
        "content": summary_text,
        "sequence": 0,
    }]

    payload = {
        "replyId": reply_id,
        "events": events,
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{studio_url}/trpc/pushMessageToChatAgent",
                json=payload,
            )
    except Exception as e:
        print(f"[Hook Warning] Failed to push coordinator result: {e}")

    # 发送完成信号
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{studio_url}/trpc/pushFinishedSignalToChatAgent",
                json={"replyId": reply_id},
            )
    except Exception as e:
        print(f"[Hook Warning] Failed to push finished signal: {e}")


async def run_coordinator(args, toolkit: Toolkit, model, worker_model=None):
    """使用 Coordinator 分解任务并调度 Workers"""
    # 配置 Coordinator
    memory_storage_path = str(project_root / "storage" / "memory")
    config = CoordinatorConfig(
        agents_dir=project_root / ".testagent" / "agents",
        skills_dir=project_root / ".testagent" / "skills",
        prompts_dir=project_root / "prompts" / "coordinator",
        max_phases=10,
        max_retries=3,
        timeout=1800,
        max_parallel_workers=5,
        # 记忆系统配置
        memory_enabled=True,
        memory_storage_path=memory_storage_path,
    )

    # 创建进度回调
    progress_callback = _create_progress_callback(args.studio_url, args.reply_id)

    # 创建 Coordinator
    coordinator = Coordinator(
        model=model,
        toolkit=toolkit,
        config=config,
        progress_callback=progress_callback,
        worker_model=worker_model,  # 非流式模型用于 Worker
    )

    # 初始化（加载 Workers 和 Skills）
    await coordinator.initialize()

    print("[OK] Coordinator 初始化完成")

    # 解析用户查询
    if args.query_from_stdin:
        query_str = sys.stdin.readline().strip()
        print(f"[INFO] 从 stdin 读取到: {query_str[:100]}...")
        query = json5.loads(query_str)
    else:
        query = json5.loads(args.query)

    # 提取目标文本
    # query 格式可能是:
    # - 数组: [{"type": "text", "text": "..."}]
    # - 字典: {"content": "..."} 或 {"text": "..."}
    # - 字符串: "..."
    if isinstance(query, list):
        # 从数组中提取所有 text 内容
        texts = []
        for item in query:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        objective = "\n".join(texts)
    elif isinstance(query, dict):
        objective = query.get("content", query.get("text", str(query)))
    else:
        objective = str(query)

    print(f"[INFO] 用户目标: {objective[:100]}...")

    # 配置 Hook（用于推送结果到前端）
    AgentHooks.url = args.studio_url
    AgentHooks.reply_id = args.reply_id

    # 使用 AgentLoop 驱动 Coordinator 多轮执行
    from loop.agent_loop import AgentLoop
    from loop.goal_evaluator import GoalEvaluator

    goal_evaluator = GoalEvaluator(model=model)

    max_loop_iterations = getattr(args, "max_loop_iterations", 1)
    agent_loop = AgentLoop(
        coordinator=coordinator,
        goal_evaluator=goal_evaluator,
        max_iterations=max_loop_iterations,
        confidence_threshold=0.7,
    )

    result = await agent_loop.run(
        objective=objective,
        context={"workspace": args.workspace},
        session_id=args.conversation_id,
    )

    # 输出结果摘要
    print(f"[INFO] 执行结果: achieved={result.get('achieved')}, iterations={result.get('iterations_run')}")
    if result.get("error"):
        print(f"[ERROR] {result['error']}")

    # 将结果推送到前端
    _push_coordinator_result_to_frontend(args.studio_url, args.reply_id, result)

    return result


async def main():
    """主入口函数"""
    args = get_args()

    print("=" * 60)
    print("ChatAgent 启动 (Coordinator Mode)")
    print(f"会话 ID: {args.conversation_id}")
    print(f"回复 ID: {args.reply_id}")
    print(f"Server URL: {args.studio_url}")
    print(f"工作区: {args.workspace}")
    print(f"写权限: {args.writePermission}")
    print("=" * 60)

    # 初始化 ToolConfig
    ToolConfig.init(workspace=args.workspace, write_permission=args.writePermission)

    # 添加 storage 子目录为允许访问的路径
    storage_chat_dir = project_root / "storage" / "chat"
    storage_cache_dir = project_root / "storage" / "cache"
    if storage_chat_dir.exists():
        ToolConfig.get().add_allowed_path(storage_chat_dir)
    if storage_cache_dir.exists():
        ToolConfig.get().add_allowed_path(storage_cache_dir)
    elif args.writePermission:
        storage_cache_dir.mkdir(parents=True, exist_ok=True)
        ToolConfig.get().add_allowed_path(storage_cache_dir)

    # 添加额外允许路径（用于挂载的被测项目目录）
    # 参考 Claude Code 的做法：通过环境变量声明可访问的项目路径
    extra_paths = os.environ.get("WORKSPACE_EXTRA_PATHS", "")
    if extra_paths:
        for p in extra_paths.split(":"):
            p = p.strip()
            if p and Path(p).exists():
                ToolConfig.get().add_allowed_path(Path(p))
                print(f"[OK] 已添加额外允许路径: {p}")

    # 配置 Hook
    AgentHooks.url = args.studio_url
    AgentHooks.reply_id = args.reply_id

    # 初始化工具集
    toolkit = Toolkit()

    # 注册 base tools
    base_tools = [
        execute_shell,
        read_file,
        write_file,
        edit_file,
        glob_files,
        grep_files,
        web_fetch,
        list_uploaded_files,
    ]
    for tool_func in base_tools:
        toolkit.register_tool_function(tool_func)

    # 配置 MCP 和 skill tools
    settings_path = str(project_root / ".testagent" / "settings.json")
    toolkit, mcp_clients = await setup_toolkit(toolkit, settings_path=settings_path)

    # 注册 reset_equipped_tools 到基础工具组，允许所有 Worker 动态激活/停用工具组
    # 这是 AgentScope 内置方法，Worker 调用 reset_equipped_tools(group_name=True) 即可激活对应工具组
    toolkit.register_tool_function(toolkit.reset_equipped_tools)

    # 注册输出目录工具（如果配置了输出目录）
    if getattr(args, "output_dir", "") and getattr(args, "user_id", ""):
        from tool.base.write_output_file import make_write_output_file
        from tool.base.read_output_file import make_read_output_file
        _out_ctx = dict(
            user_id=args.user_id,
            conversation_id=args.conversation_id,
            output_dir=args.output_dir,
        )
        toolkit.register_tool_function(make_write_output_file(**_out_ctx))
        read_output_tool, list_output_tool = make_read_output_file(**_out_ctx)
        toolkit.register_tool_function(read_output_tool)
        toolkit.register_tool_function(list_output_tool)
        print(f"[OK] 输出目录工具已注册 (write/read/list)，路径: {args.output_dir}/{args.user_id}/{args.conversation_id}")

    # 获取模型
    # 流式模型用于 Coordinator 的直接 LLM 调用（任务规划、评估等）
    model = get_model(
        args.llmProvider,
        args.modelName,
        args.apiKey,
        args.clientKwargs,
        args.generateKwargs
    )

    # 非流式模型用于 Worker（ReActAgent 需要非流式响应）
    worker_model = get_model_non_streaming(
        args.llmProvider,
        args.modelName,
        args.apiKey,
        args.clientKwargs,
        args.generateKwargs
    )

    try:
        await run_coordinator(args, toolkit, model, worker_model)

    except Exception as e:
        print(f"[ERROR] Coordinator 执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理 MCP 连接
        await close_mcp_servers(mcp_clients)

    print("=" * 60)
    print("ChatAgent 执行完毕")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
