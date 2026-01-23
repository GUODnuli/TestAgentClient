# -*- coding: utf-8 -*-
"""
ChatAgent 入口文件

作为子进程被 Server 启动，执行 ReActAgent 并通过 Hook 回传消息。
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from agentscope.plan import PlanNotebook
import json5
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import (
    Toolkit,
    execute_python_code,
    write_text_file,
    insert_text_file,
    view_text_file,
)
from tool.utils import (
    list_uploaded_files,
    safe_view_text_file
)
from tool.doc_parser import (
    read_document,
    extract_api_spec,
    validate_api_spec
)
from tool.case_generator import (
    generate_positive_cases,
    generate_negative_cases,
    generate_security_cases,
    apply_business_rules
)
from tool.test_executor import (
    execute_api_test,
    validate_response,
    capture_metrics
)
from tool.report_tools import (
    generate_test_report,
    diagnose_failures,
    suggest_improvements
)

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.agent.args import get_args
from backend.agent.model import get_model, get_formatter
from backend.agent.hook import AgentHooks, studio_pre_print_hook, studio_post_reply_hook


def _load_system_prompt() -> str:
    """加载系统提示词"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "chat_default.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    
    # 默认提示词
    return """You are an AI assistant for the MCP API Testing Agent system.

# Core Objectives
- Help users understand and utilize the API testing features
- Answer questions about API testing, test case generation, and execution
- Provide testing best practices and professional recommendations
- Explain test reports and results in detail

# Critical Principles (MUST FOLLOW)
1. **Safety First**: Before executing any operation, ensure its safety
   - Do not execute dangerous operations that may damage data or systems
   - For file modification, deletion and other operations, confirm user intent first
   - Pay attention to privacy and security when dealing with sensitive information
2. **Tool-Driven Capabilities**: You have ReAct capabilities and can invoke MCP tools (document parsing, test generation, execution, etc.)
   - **NEVER claim inability to access files**: When users mention uploaded files or need specific operations, you MUST attempt to call relevant tools (e.g., external MCP tools from connected servers)
   - Always try tool invocation first before claiming limitations
3. **No Assumptions**: All information must come from users or tool results

# Workflow Process
1. Analyze user request and formulate a plan
2. Execute the plan step by step

# Response Guidelines
- Use friendly and professional tone
- Be concise and focused on user's specific context
- Avoid repeating material verbatim; summarize in your own words
- When user intent is unclear, proactively ask clarifying questions
- Clearly distinguish between "generating code" and "executing code" requests

# About This System
This is an MCP-based intelligent API testing system that supports:
- Multi-format document parsing (OpenAPI/Swagger, Postman, HAR, Word)
- Automated test case generation
- Test execution and result analysis
- Intelligent test planning and strategy recommendations

# File Access Protocol
When the user mentions uploaded files:
1. Extract user_id and conversation_id from the [SYSTEM CONTEXT] block in your input
2. Call list_uploaded_files(user_id, conversation_id) to get the correct file paths
3. Use the returned paths with safe_view_text_file

# Tool Management Protocol

- You have the capability to dynamically manage tools and can activate required tool groups via `reset_equipped_tools`.
- When handling uploaded files:
  1. Call `reset_equipped_tools({"api_test_tools": true})`
  2. Wait for the returned tool usage instructions
  3. Use `list_uploaded_files` and `safe_view_text_file` according to the instructions
- Immediately deactivate the tool group after completion: `reset_equipped_tools({"api_test_tools": false})`"""

async def main():
    """主入口函数"""
    args = get_args()
    
    print("=" * 60)
    print("ChatAgent 启动")
    print(f"会话 ID: {args.conversation_id}")
    print(f"回复 ID: {args.reply_id}")
    print(f"Server URL: {args.studio_url}")
    print("=" * 60)
    
    # 配置 Hook
    AgentHooks.url = args.studio_url
    AgentHooks.reply_id = args.reply_id
    
    # 注册类级 Hook
    ReActAgent.register_class_hook(
        "pre_print",
        "studio_pre_print_hook",
        studio_pre_print_hook
    )
    ReActAgent.register_class_hook(
        "post_reply",
        "studio_post_reply_hook",
        studio_post_reply_hook
    )
    
    # 初始化工具集
    toolkit = Toolkit()
    # TODO: 注册 MCP 工具
    toolkit.register_tool_function(write_text_file)
    toolkit.register_tool_function(insert_text_file)
    # 注意：不再直接注册 view_text_file，改用带安全校验的 safe_view_text_file
    toolkit.register_tool_function(safe_view_text_file)

    # ===== 注册 API 测试工具 =====
    # 文档解析工具
    toolkit.register_tool_function(read_document)
    toolkit.register_tool_function(extract_api_spec)
    toolkit.register_tool_function(validate_api_spec)
    
    # 用例生成工具
    toolkit.register_tool_function(generate_positive_cases)
    toolkit.register_tool_function(generate_negative_cases)
    toolkit.register_tool_function(generate_security_cases)
    toolkit.register_tool_function(apply_business_rules)
    
    # 测试执行工具
    toolkit.register_tool_function(execute_api_test)
    toolkit.register_tool_function(validate_response)
    toolkit.register_tool_function(capture_metrics)
    
    # 报告生成工具
    toolkit.register_tool_function(generate_test_report)
    toolkit.register_tool_function(diagnose_failures)
    toolkit.register_tool_function(suggest_improvements)

    # 接口测试工具组
    toolkit.create_tool_group(
        group_name="api_test_tools",
        description="用于 API 测试的文件操作工具集。当用户提及上传的文档时，首先使用工具发现可用文件，然后访问文件内容。",
        notes="""# File Operation Guidelines
When users mention uploaded documents:
1. **ALWAYS FIRST** call `list_uploaded_files(user_id, conversation_id)` to discover available files
   - Extract user_id and conversation_id from [SYSTEM CONTEXT]
2. Then use the returned file paths with `safe_view_text_file(file_path)`
3. Never assume file paths - always use the paths returned by list_uploaded_files

# Workflow
- Use list_uploaded_files(user_id, conversation_id) to discover uploaded documents
- Use safe_view_text_file(file_path) to read file contents with discovered paths
- Process and analyze file contents to answer user queries

# Error Handling
- If you encounter FunctionInactiveError when calling a tool, it means the tool group is not activated
- Use `equip_tool_group(tool_group_name)` to activate the corresponding tool group
- Example: If list_uploaded_files raises FunctionInactiveError, call `equip_tool_group("api_test_tools")` 

# Workflow Example
User: "分析我上传的接口文档"
Agent should:
1. Call list_uploaded_files(user_id="...", conversation_id="...")
2. Get response: "- api_spec.docx (path: user_id/conv_id/api_spec.docx)"
3. Call safe_view_text_file("user_id/conv_id/api_spec.docx")

# Context Information
- user_id and conversation_id are provided in [SYSTEM CONTEXT] block
- Extract these values from the context to call list_uploaded_files

# Security
- All file paths are validated to prevent directory traversal attacks
- Only files within storage/chat directory can be accessed"""
    )
    toolkit.register_tool_function(
        list_uploaded_files, group_name="api_test_tools"
    )
    
    # 获取模型
    model = get_model(
        args.llmProvider,
        args.modelName,
        args.apiKey,
        args.clientKwargs,
        args.generateKwargs
    )
    formatter = get_formatter(args.llmProvider)
    
    # 加载系统提示词
    system_prompt = _load_system_prompt()
    system_prompt += f"\n\n# 当前时间\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    # 加载自定义plan to hint
    from plan import (
        plan_to_hint,
        api_test_plan_to_hint
    )
    plan_to_hint = plan_to_hint.CustomPlanToHint()
    api_test_plan_to_hint = api_test_plan_to_hint.ApiTestPlanToHint()
    
    # 创建 ReActAgent
    agent = ReActAgent(
        name="ChatAgent",
        sys_prompt=system_prompt,
        model=model,
        formatter=formatter,
        toolkit=toolkit,
        memory=InMemoryMemory(),
        max_iters=50,
        plan_notebook=PlanNotebook(max_subtasks=50, plan_to_hint=plan_to_hint),
        enable_meta_tool=True
    )
    
    print("[OK] Agent 初始化完成")
    
    try:
        # 解析用户查询
        if args.query_from_stdin:
            # 从 stdin 读取 query
            query_str = sys.stdin.readline().strip()
            print(f"[INFO] 从 stdin 读取到: {query_str[:100]}...")
            query = json5.loads(query_str)
        else:
            # 从命令行参数读取
            query = json5.loads(args.query)
        
        print(f"[INFO] 用户查询: {str(query)[:100]}...")
        
        # 执行 Agent
        await agent(Msg("user", query, "user"))
        
    except Exception as e:
        print(f"[ERROR] Agent 执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print("ChatAgent 执行完毕")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
