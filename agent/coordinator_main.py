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

        elif event_type in ("phase_started", "phase_completed"):
            # Phase 状态变化作为 coordinator_event（用于更新侧边栏）
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
    """将 Coordinator 执行结果推送到前端"""
    import httpx

    if not studio_url or not reply_id:
        return

    # 生成结果摘要文本
    status = result.get("status", "unknown")
    objective = result.get("objective", "")
    error = result.get("error")

    # 构建结果摘要
    summary_parts = []
    summary_parts.append(f"## Coordinator 执行完成\n")
    summary_parts.append(f"**状态**: {status}\n")

    if error:
        summary_parts.append(f"**错误**: {error}\n")

    # 添加 Phase 结果摘要
    phase_results = result.get("phase_results", [])
    if phase_results:
        summary_parts.append(f"\n### 执行阶段 ({len(phase_results)} 个)\n")
        for i, phase in enumerate(phase_results, 1):
            phase_name = phase.get("phase_name", f"Phase {i}")
            phase_status = phase.get("status", "unknown")
            summary_parts.append(f"- **{phase_name}**: {phase_status}\n")

            # 添加 Worker 结果
            worker_results = phase.get("worker_results", {})
            for worker_name, worker_result in worker_results.items():
                worker_status = worker_result.get("status", "unknown")
                worker_output = worker_result.get("output", "")
                if worker_output and len(str(worker_output)) > 200:
                    worker_output = str(worker_output)[:200] + "..."
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

    # 执行 Coordinator
    result = await coordinator.execute(
        objective=objective,
        context={"workspace": args.workspace},
        session_id=args.conversation_id,
    )

    # 输出结果摘要
    print(f"[INFO] 执行结果: {result.get('status')}")
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
