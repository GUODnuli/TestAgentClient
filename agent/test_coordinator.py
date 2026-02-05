# -*- coding: utf-8 -*-
"""
Coordinator 模式测试脚本

独立测试 Coordinator 的核心功能，不依赖完整的 Server 环境。
"""
import asyncio
import io
import os
import sys

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from pathlib import Path

# Setup paths
project_root = Path(__file__).parent.parent
agent_dir = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agentscope.tool import Toolkit

# Import coordinator components
from coordinator import Coordinator, CoordinatorConfig
from worker import WorkerLoader
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


def progress_callback(event_type: str, data: dict):
    """打印进度事件"""
    if event_type == "worker_message":
        # 显示 Worker 消息内容（截断显示）
        content = data.get('content', '')[:100]
        worker = data.get('worker', 'unknown')
        print(f"  [WORKER {worker}] {content}")
    else:
        print(f"  [EVENT] {event_type}: {data.get('status', data.get('phase', data.get('name', '')))}")


async def test_worker_loader():
    """测试 Worker 加载"""
    print("\n" + "=" * 60)
    print("测试 1: Worker 加载")
    print("=" * 60)

    agents_dir = project_root / ".testagent" / "agents"
    loader = WorkerLoader(agents_dir)
    workers = loader.load()

    print(f"找到 {len(workers)} 个 Workers:")
    for name, config in workers.items():
        print(f"  - {name}: mode={config.mode}, tools={config.tools[:3]}...")

    assert len(workers) >= 4, "应该至少有 4 个 Workers (planner, analyzer, executor, reporter)"
    print("✓ Worker 加载测试通过")
    return True


async def test_coordinator_init(model, worker_model=None):
    """测试 Coordinator 初始化"""
    print("\n" + "=" * 60)
    print("测试 2: Coordinator 初始化")
    print("=" * 60)

    # 创建工具集
    toolkit = Toolkit()
    base_tools = [
        execute_shell, read_file, write_file, edit_file,
        glob_files, grep_files, web_fetch,
    ]
    for tool_func in base_tools:
        toolkit.register_tool_function(tool_func)

    # 配置 Coordinator
    config = CoordinatorConfig(
        agents_dir=project_root / ".testagent" / "agents",
        skills_dir=project_root / ".testagent" / "skills",
        prompts_dir=project_root / "prompts" / "coordinator",
        max_phases=5,
        max_retries=2,
        timeout=300,
        max_parallel_workers=3,
    )

    # 创建 Coordinator (使用非流式 worker_model 用于 ReActAgent)
    coordinator = Coordinator(
        model=model,
        toolkit=toolkit,
        config=config,
        progress_callback=progress_callback,
        worker_model=worker_model,  # 非流式模型用于 Worker
    )

    # 初始化
    await coordinator.initialize()

    print(f"已加载 Workers: {list(coordinator._workers.keys())}")
    print(f"已加载 Skills: {[s.get('name') for s in coordinator._skills]}")

    assert len(coordinator._workers) >= 4, "应该至少有 4 个 Workers"
    print("✓ Coordinator 初始化测试通过")
    return coordinator, toolkit


async def test_task_planning(coordinator):
    """测试任务规划（通过 TaskPlanner 直接测试）"""
    print("\n" + "=" * 60)
    print("测试 3: 任务规划 (LLM 调用)")
    print("=" * 60)

    # 简单的测试任务
    objective = "分析当前目录下的 README.md 文件，总结其主要内容"

    print(f"任务目标: {objective}")
    print("正在调用 LLM 进行任务分解...")

    try:
        # 直接使用 TaskPlanner 测试，避免依赖 coordinator 内部状态
        from coordinator.task_planner import TaskPlanner

        planner = TaskPlanner(
            model=coordinator.model,
            prompts_dir=coordinator.config.prompts_dir,
        )

        # 获取 Worker 和 Skill 摘要
        worker_summary = coordinator._worker_loader.get_worker_summary()
        skill_summary = coordinator._skills

        plan = await planner.create_plan(
            objective=objective,
            context={"workspace": str(project_root)},
            available_workers=worker_summary,
            available_skills=skill_summary,
        )

        print(f"\n生成的执行计划:")
        print(f"  - 阶段数: {len(plan.phases)}")
        print(f"  - 完成条件: {plan.completion_criteria[:50]}..." if plan.completion_criteria else "  - 完成条件: (无)")

        for phase in plan.phases:
            print(f"\n  Phase {phase.phase}: {phase.name}")
            print(f"    并行: {phase.parallel}")
            for worker in phase.workers:
                print(f"    - Worker: {worker.worker}")
                print(f"      任务: {worker.task[:50]}...")

        print("\n✓ 任务规划测试通过")
        return plan

    except Exception as e:
        print(f"\n✗ 任务规划失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_full_execution(coordinator):
    """测试完整执行流程"""
    print("\n" + "=" * 60)
    print("测试 4: 完整执行流程")
    print("=" * 60)

    # 简单的任务
    objective = "列出当前项目的主要目录结构"

    print(f"任务目标: {objective}")
    print("开始执行...")

    try:
        result = await coordinator.execute(
            objective=objective,
            context={"workspace": str(project_root)},
            session_id="test_session",
        )

        print(f"\n执行结果:")
        print(f"  - 状态: {result.get('status')}")
        print(f"  - 任务 ID: {result.get('task_id')}")

        if result.get('error'):
            print(f"  - 错误: {result.get('error')}")

        phase_results = result.get('phase_results', [])
        print(f"  - 完成阶段数: {len(phase_results)}")

        for pr in phase_results:
            print(f"\n    Phase: {pr.get('phase_name')}")
            print(f"    状态: {pr.get('status')}")
            for wname, wr in pr.get('worker_results', {}).items():
                print(f"      - {wname}: {wr.get('status')}")

        if result.get('status') in ('completed', 'success'):
            print("\n✓ 完整执行测试通过")
        else:
            print(f"\n⚠ 执行完成但状态为: {result.get('status')}")

        return result

    except Exception as e:
        print(f"\n✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("Coordinator 模式测试")
    print("=" * 60)

    # 检查环境变量
    api_key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('LLM_API_KEY')
    if not api_key:
        print("\n⚠ 未找到 API Key 环境变量")
        print("请设置 DASHSCOPE_API_KEY 或 LLM_API_KEY")
        print("\n将跳过需要 LLM 的测试...")
        model = None
        worker_model = None
    else:
        print(f"\n使用 API Key: {api_key[:8]}...")
        # 初始化模型（流式用于 Coordinator 的规划/评估）
        from model import get_model, get_model_non_streaming
        model = get_model(
            llm_provider="dashscope",
            model_name="qwen-plus",
            api_key=api_key,
        )
        # 非流式模型用于 Worker（ReActAgent 需要同步响应）
        worker_model = get_model_non_streaming(
            llm_provider="dashscope",
            model_name="qwen-plus",
            api_key=api_key,
        )

    # 初始化 ToolConfig
    ToolConfig.init(workspace=str(project_root), write_permission=False)

    results = {}

    # 测试 1: Worker 加载
    try:
        results['worker_loader'] = await test_worker_loader()
    except Exception as e:
        print(f"✗ Worker 加载测试失败: {e}")
        results['worker_loader'] = False

    if model:
        # 测试 2: Coordinator 初始化
        try:
            coordinator, toolkit = await test_coordinator_init(model, worker_model)
            results['coordinator_init'] = True
        except Exception as e:
            print(f"✗ Coordinator 初始化测试失败: {e}")
            import traceback
            traceback.print_exc()
            results['coordinator_init'] = False
            coordinator = None

        if coordinator:
            # 测试 3: 任务规划
            try:
                plan = await test_task_planning(coordinator)
                results['task_planning'] = plan is not None
            except Exception as e:
                print(f"✗ 任务规划测试失败: {e}")
                results['task_planning'] = False

            # 测试 4: 完整执行
            try:
                exec_result = await test_full_execution(coordinator)
                results['full_execution'] = exec_result is not None
            except Exception as e:
                print(f"✗ 完整执行测试失败: {e}")
                results['full_execution'] = False
    else:
        print("\n跳过 LLM 相关测试 (无 API Key)")
        results['coordinator_init'] = 'skipped'
        results['task_planning'] = 'skipped'
        results['full_execution'] = 'skipped'

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, passed in results.items():
        if passed == 'skipped':
            status = "⊘ 跳过"
        elif passed:
            status = "✓ 通过"
        else:
            status = "✗ 失败"
        print(f"  {test_name}: {status}")

    # 返回是否全部通过
    all_passed = all(v in (True, 'skipped') for v in results.values())
    if all_passed:
        print("\n✓ 所有测试通过!")
    else:
        print("\n✗ 部分测试失败")

    return all_passed


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
