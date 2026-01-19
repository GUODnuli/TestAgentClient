"""
聊天 Agent 服务

基于 AgentScope ReActAgent 实现 User-Assistant 对话功能。
支持计划模式（PlanNotebook）和 MCP 工具集成。
"""

import uuid
import time
import asyncio
from typing import Any, Dict, Generator, List, Optional, AsyncGenerator, Callable
from datetime import datetime

from backend.common.logger import get_logger
from backend.common.database import Database

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit
from agentscope.plan import PlanNotebook
import os


# ==================== 系统提示词 ====================

def _get_default_system_prompt() -> str:
    """获取默认系统提示词"""
    return """你是 MCP 接口测试智能体的 AI 助手。你的职责是：

1. 帮助用户理解和使用接口测试功能
2. 回答关于 API 测试、测试用例生成的问题
3. 提供测试相关的建议和最佳实践
4. 解释测试报告和结果

请用友好、专业的语气回复用户。如果用户的问题超出你的能力范围，请诚实告知。"""


def _get_planning_system_prompt() -> str:
    """获取计划模式的系统提示词"""
    return """你是 MCP 接口测试智能体的 AI 助手，当前处于**计划模式**。

在计划模式下，你需要：
1. 理解用户的测试需求
2. 制定详细的测试计划，分解为多个子任务
3. 使用可用的 MCP 工具执行各个步骤
4. 在执行过程中展示你的思考过程

可用的 MCP 工具：
- parse_document: 解析 API 文档（OpenAPI/Swagger、Postman、HAR、Word）
- generate_testcases: 为接口生成测试用例
- execute_tests: 执行测试用例
- analyze_report: 使用 LLM 分析测试报告

请在思考和规划时，先分析用户需求，然后制定清晰的步骤计划。"""


# ==================== MCP 工具注册 ====================

def register_mcp_tools(toolkit: Toolkit) -> Toolkit:
    """
    注册 MCP Server 工具到 Toolkit
    
    Args:
        toolkit: AgentScope Toolkit 实例
        
    Returns:
        注册了工具的 Toolkit
    """
    
    # 文档解析工具
    def parse_document(
        document_path: str,
        task_id: str = "",
        parse_strategy: str = "auto"
    ) -> Dict[str, Any]:
        """
        解析 API 文档
        
        Args:
            document_path: 文档文件路径
            task_id: 任务ID（可选）
            parse_strategy: 解析策略（auto/openapi/postman/har/word）
            
        Returns:
            解析结果，包含提取的接口信息
        """
        return {
            "status": "pending",
            "message": f"准备解析文档: {document_path}，策略: {parse_strategy}",
            "task_id": task_id or str(uuid.uuid4())
        }
    
    # 测试用例生成工具
    def generate_testcases(
        interface: Dict[str, Any],
        task_id: str = "",
        strategies: List[str] = None,
        count_per_strategy: int = 3
    ) -> Dict[str, Any]:
        """
        为接口生成测试用例
        
        Args:
            interface: 接口信息
            task_id: 任务ID（可选）
            strategies: 测试策略列表（positive/negative/boundary/security/performance）
            count_per_strategy: 每种策略生成的用例数量
            
        Returns:
            生成的测试用例
        """
        strategies = strategies or ["positive", "negative", "boundary"]
        return {
            "status": "pending",
            "message": f"准备生成测试用例，策略: {strategies}，每策略数量: {count_per_strategy}",
            "task_id": task_id or str(uuid.uuid4())
        }
    
    # 测试执行工具
    def execute_tests(
        testcases: List[Dict[str, Any]],
        task_id: str = "",
        engine: str = "requests",
        parallel: bool = False
    ) -> Dict[str, Any]:
        """
        执行测试用例
        
        Args:
            testcases: 测试用例列表
            task_id: 任务ID（可选）
            engine: 测试引擎（requests/httprunner）
            parallel: 是否并行执行
            
        Returns:
            测试执行结果
        """
        return {
            "status": "pending",
            "message": f"准备执行 {len(testcases)} 个测试用例，引擎: {engine}，并行: {parallel}",
            "task_id": task_id or str(uuid.uuid4())
        }
    
    # 报告分析工具
    def analyze_report(
        report_data: Dict[str, Any],
        task_id: str = ""
    ) -> Dict[str, Any]:
        """
        使用 LLM 分析测试报告
        
        Args:
            report_data: 测试报告数据
            task_id: 任务ID（可选）
            
        Returns:
            分析结果，包含失败原因、质量评估和改进建议
        """
        return {
            "status": "pending",
            "message": "准备分析测试报告",
            "task_id": task_id or str(uuid.uuid4())
        }
    
    # 注册工具函数
    toolkit.register_tool_function(parse_document)
    toolkit.register_tool_function(generate_testcases)
    toolkit.register_tool_function(execute_tests)
    toolkit.register_tool_function(analyze_report)
    
    return toolkit


# ==================== 会话管理 ====================

class Conversation:
    """
    对话会话类
    
    管理单个对话的消息历史，使用 AgentScope 的 Msg 和 InMemoryMemory。
    """
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.messages: List[Msg] = []
        self.memory = InMemoryMemory()
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        # 计划模式状态
        self.plan_mode = False
        self.plan_notebook: Optional[PlanNotebook] = None
    
    def add_message(self, message: Msg):
        """添加消息到会话"""
        self.messages.append(message)
        self.memory.add(message)
        self.updated_at = datetime.now().isoformat()
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取消息历史"""
        messages = self.messages[-limit:] if limit else self.messages
        return [self._msg_to_dict(msg) for msg in messages]
    
    def _msg_to_dict(self, msg: Msg) -> Dict[str, Any]:
        """将 Msg 转换为字典"""
        return {
            "name": msg.name,
            "role": msg.role,
            "content": msg.content,
            "timestamp": getattr(msg, 'timestamp', datetime.now().isoformat())
        }
    
    def get_memory(self) -> InMemoryMemory:
        """获取会话的 Memory 对象，用于 ReActAgent"""
        return self.memory
    
    def enable_plan_mode(self):
        """启用计划模式"""
        self.plan_mode = True
        if not self.plan_notebook:
            self.plan_notebook = PlanNotebook(max_subtasks=10)
    
    def disable_plan_mode(self):
        """禁用计划模式"""
        self.plan_mode = False
    
    def clear(self):
        """清空对话历史"""
        self.messages = []
        self.memory = InMemoryMemory()
        self.plan_mode = False
        self.plan_notebook = None
        self.updated_at = datetime.now().isoformat()


# ==================== Agent 创建 ====================

def create_react_agent(
    name: str = "Assistant",
    system_prompt: Optional[str] = None,
    memory: Optional[InMemoryMemory] = None,
    toolkit: Optional[Toolkit] = None,
    plan_notebook: Optional[PlanNotebook] = None,
    enable_thinking: bool = False
) -> ReActAgent:
    """
    创建 ReActAgent 实例
    
    Args:
        name: Agent 名称
        system_prompt: 系统提示词
        memory: 记忆对象
        toolkit: 工具集
        plan_notebook: 计划本（用于计划模式）
        enable_thinking: 是否启用思考过程
        
    Returns:
        ReActAgent 实例
    """
    # 获取 API Key，优先从环境变量获取
    api_key = os.environ.get("QWEN_API_KEY", "")
    model_name = os.environ.get("QWEN_MODEL", "qwen-max")
    
    # 创建模型
    model = DashScopeChatModel(
        model_name=model_name,
        api_key=api_key,
        stream=True,
        enable_thinking=enable_thinking,
    )
    
    # 准备工具集
    if toolkit is None:
        toolkit = Toolkit()
    
    # 创建 Agent
    agent_kwargs = {
        "name": name,
        "sys_prompt": system_prompt or _get_default_system_prompt(),
        "model": model,
        "formatter": DashScopeChatFormatter(),
        "toolkit": toolkit,
        "memory": memory or InMemoryMemory(),
    }
    
    # 如果有 plan_notebook，添加到参数中
    if plan_notebook is not None:
        agent_kwargs["plan_notebook"] = plan_notebook
    
    agent = ReActAgent(**agent_kwargs)
    
    return agent


def create_planning_agent(
    memory: Optional[InMemoryMemory] = None,
    plan_notebook: Optional[PlanNotebook] = None
) -> ReActAgent:
    """
    创建计划模式的 Agent
    
    Args:
        memory: 记忆对象
        plan_notebook: 计划本
        
    Returns:
        配置了计划功能的 ReActAgent
    """
    # 创建并注册 MCP 工具
    toolkit = Toolkit()
    register_mcp_tools(toolkit)
    
    return create_react_agent(
        name="PlanningAssistant",
        system_prompt=_get_planning_system_prompt(),
        memory=memory,
        toolkit=toolkit,
        plan_notebook=plan_notebook or PlanNotebook(max_subtasks=10),
        enable_thinking=True  # 计划模式启用思考过程
    )


# ==================== 聊天服务 ====================

class ChatService:
    """
    聊天服务
    
    管理多个对话会话，提供高层 API 接口。
    基于 AgentScope ReActAgent 实现。
    支持计划模式（/plan 命令）。
    """
    
    PLAN_COMMAND_PREFIX = "/plan"
    
    def __init__(self, database: Database, system_prompt: Optional[str] = None):
        """
        初始化聊天服务
        
        Args:
            database: 数据库实例
            system_prompt: 自定义系统提示词
        """
        self.logger = get_logger()
        self.database = database
        self.system_prompt = system_prompt or _get_default_system_prompt()
        
        # 会话存储（内存中，保留用于上下文管理）
        self.conversations: Dict[str, Conversation] = {}
        
        # 配置
        self.max_context_messages = 20  # 最大上下文消息数
        
        self.logger.info("ChatService 初始化完成（使用 ReActAgent，支持计划模式）")
    
    def _is_plan_command(self, message: str) -> bool:
        """检查消息是否是计划命令"""
        return message.strip().lower().startswith(self.PLAN_COMMAND_PREFIX)
    
    def _extract_plan_content(self, message: str) -> str:
        """提取计划命令的内容"""
        content = message.strip()[len(self.PLAN_COMMAND_PREFIX):].strip()
        return content if content else "请帮我制定一个测试计划"
    
    def _restore_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """从数据库恢复会话到内存"""
        try:
            db_conv = self.database.get_conversation(conversation_id)
            if not db_conv:
                return None
            
            conversation = Conversation(conversation_id)
            # 加载最近的历史消息作为上下文
            messages = self.database.list_conversation_messages(
                conversation_id, 
                limit=self.max_context_messages
            )
            
            for msg_data in messages:
                msg = Msg(
                    name="User" if msg_data['role'] == "user" else "Assistant",
                    role=msg_data['role'],
                    content=msg_data['content']
                )
                conversation.add_message(msg)
            
            self.conversations[conversation_id] = conversation
            self.logger.info(
                f"[ChatService] 从数据库恢复会话 | "
                f"conversation_id: {conversation_id} | 消息数: {len(messages)}"
            )
            return conversation
        except Exception as e:
            self.logger.error(f"[ChatService] 恢复会话失败: {str(e)}", exc_info=True)
            return None

    def _get_or_create_conversation(
        self, 
        message: str, 
        user_id: str, 
        conversation_id: Optional[str]
    ) -> tuple[str, Conversation]:
        """获取或创建会话"""
        if conversation_id and conversation_id in self.conversations:
            return conversation_id, self.conversations[conversation_id]
        
        if conversation_id:
            # 尝试从数据库恢复
            conversation = self._restore_conversation(conversation_id)
            if conversation:
                return conversation_id, conversation
            # 如果数据库也没有，创建新会话
            conversation = Conversation(conversation_id)
            self.conversations[conversation_id] = conversation
            self.logger.info(
                f"[ChatService] 创建新内存会话(ID已提供) | "
                f"conversation_id: {conversation_id}"
            )
            return conversation_id, conversation
        
        # 创建全新会话
        conversation_id = str(uuid.uuid4())
        # 创建数据库对话
        self.database.create_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            title=message[:50]  # 使用前50个字符作为标题
        )
        
        conversation = Conversation(conversation_id)
        self.conversations[conversation_id] = conversation
        self.logger.info(f"[ChatService] 初始化新会话 | conversation_id: {conversation_id}")
        return conversation_id, conversation

    def _extract_thinking_and_content(self, response_content: Any) -> tuple[str, str]:
        """
        从响应内容中提取思考过程和最终回复
        
        Args:
            response_content: 响应内容（可能是字符串、列表或其他格式）
            
        Returns:
            (thinking, content) 思考过程和最终内容的元组
        """
        thinking = ""
        content = ""
        
        if isinstance(response_content, list):
            # 处理列表格式（如 [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]）
            for item in response_content:
                if isinstance(item, dict):
                    if item.get("type") == "thinking" or "thinking" in item:
                        thinking += item.get("thinking", "")
                    elif item.get("type") == "text" or "text" in item:
                        content += item.get("text", "")
                else:
                    content += str(item)
        elif isinstance(response_content, dict):
            thinking = response_content.get("thinking", "")
            content = response_content.get("text", "") or response_content.get("content", "")
        elif isinstance(response_content, str):
            content = response_content
        else:
            content = str(response_content) if response_content else ""
        
        return thinking, content

    async def send_message(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息并获取回复（异步）
        
        Args:
            message: 用户消息
            user_id: 用户 ID
            conversation_id: 会话ID（可选，为空时创建新会话）
            
        Returns:
            包含回复和会话ID的字典
        """
        is_plan_mode = self._is_plan_command(message)
        actual_message = self._extract_plan_content(message) if is_plan_mode else message
        
        self.logger.info(
            f"[ChatService] 收到消息 | conversation_id: {conversation_id} | "
            f"消息长度: {len(message)} | 计划模式: {is_plan_mode}"
        )
        
        # 获取或创建会话
        conversation_id, conversation = self._get_or_create_conversation(
            message, user_id, conversation_id
        )
        
        # 如果是计划模式，启用计划功能
        if is_plan_mode:
            conversation.enable_plan_mode()
        
        # 保存用户消息到数据库
        user_message_id = str(uuid.uuid4())
        self.database.create_message(
            message_id=user_message_id,
            conversation_id=conversation_id,
            role="user",
            content=message
        )
        
        # 创建用户消息 Msg
        user_msg = Msg(name="User", role="user", content=actual_message)
        conversation.add_message(user_msg)
        
        thinking = ""
        reply_content = ""
        
        try:
            # 根据模式创建不同的 Agent
            if conversation.plan_mode:
                agent = create_planning_agent(
                    memory=conversation.get_memory(),
                    plan_notebook=conversation.plan_notebook
                )
            else:
                agent = create_react_agent(
                    name="Assistant",
                    system_prompt=self.system_prompt,
                    memory=conversation.get_memory()
                )
            
            # 调用 Agent 生成回复
            start_time = time.time()
            response_msg = await agent(user_msg)
            elapsed = time.time() - start_time
            
            self.logger.info(f"[ChatService] ReActAgent 调用成功 | 耗时: {elapsed:.2f}s")
            
            # 提取思考过程和回复内容
            if response_msg:
                thinking, reply_content = self._extract_thinking_and_content(response_msg.content)
            
            if not reply_content:
                reply_content = "抱歉，无法生成有效回复。"
            
        except Exception as e:
            self.logger.error(f"[ChatService] ReActAgent 调用失败: {str(e)}", exc_info=True)
            reply_content = f"抱歉，处理消息时发生错误: {str(e)}"
        
        # 保存助手消息到数据库
        assistant_message_id = str(uuid.uuid4())
        self.database.create_message(
            message_id=assistant_message_id,
            conversation_id=conversation_id,
            role="assistant",
            content=reply_content
        )
        
        # 创建助手回复 Msg 并添加到会话
        assistant_msg = Msg(name="Assistant", role="assistant", content=reply_content)
        conversation.add_message(assistant_msg)
        
        self.logger.info(
            f"[ChatService] 回复生成完成 | conversation_id: {conversation_id} | "
            f"回复长度: {len(reply_content)} | 思考长度: {len(thinking)}"
        )
        
        result = {
            "conversation_id": conversation_id,
            "reply": reply_content,
            "timestamp": datetime.now().isoformat(),
            "plan_mode": conversation.plan_mode
        }
        
        # 如果有思考过程，添加到结果中
        if thinking:
            result["thinking"] = thinking
        
        return result
    
    async def send_message_streaming(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        发送消息并获取流式回复（异步生成器）
        
        Args:
            message: 用户消息
            user_id: 用户 ID
            conversation_id: 会话ID（可选，为空时创建新会话）
            
        Yields:
            包含回复块的字典，支持 thinking 和 chunk 类型
        """
        is_plan_mode = self._is_plan_command(message)
        actual_message = self._extract_plan_content(message) if is_plan_mode else message
        
        self.logger.info(
            f"[ChatService] 收到消息（流式）| conversation_id: {conversation_id} | "
            f"消息长度: {len(message)} | 计划模式: {is_plan_mode}"
        )
        
        # 获取或创建会话
        conversation_id, conversation = self._get_or_create_conversation(
            message, user_id, conversation_id
        )
        
        # 如果是计划模式，启用计划功能
        if is_plan_mode:
            conversation.enable_plan_mode()
        
        # 保存用户消息到数据库
        user_message_id = str(uuid.uuid4())
        self.database.create_message(
            message_id=user_message_id,
            conversation_id=conversation_id,
            role="user",
            content=message
        )
        
        # 创建用户消息 Msg
        user_msg = Msg(name="User", role="user", content=actual_message)
        conversation.add_message(user_msg)
        
        # 先发送会话ID和模式信息
        yield {
            "type": "start",
            "conversation_id": conversation_id,
            "plan_mode": conversation.plan_mode
        }
        
        full_reply = []
        full_thinking = []
        
        try:
            # 根据模式创建不同的 Agent
            if conversation.plan_mode:
                agent = create_planning_agent(
                    memory=conversation.get_memory(),
                    plan_notebook=conversation.plan_notebook
                )
            else:
                agent = create_react_agent(
                    name="Assistant",
                    system_prompt=self.system_prompt,
                    memory=conversation.get_memory()
                )
            
            # 调用 Agent 生成回复
            start_time = time.time()
            response_msg = await agent(user_msg)
            
            if response_msg and response_msg.content:
                thinking, content = self._extract_thinking_and_content(response_msg.content)
                
                # 如果有思考过程，先发送思考内容
                if thinking:
                    full_thinking.append(thinking)
                    yield {
                        "type": "thinking",
                        "content": thinking
                    }
                
                # 发送回复内容
                if content:
                    full_reply.append(content)
                    yield {
                        "type": "chunk",
                        "content": content
                    }
            
            elapsed = time.time() - start_time
            self.logger.info(f"[ChatService] ReActAgent 调用成功 | 耗时: {elapsed:.2f}s")
            
        except Exception as e:
            self.logger.error(f"[ChatService] ReActAgent 调用失败: {str(e)}", exc_info=True)
            error_msg = f"抱歉，处理消息时发生错误: {str(e)}"
            full_reply.append(error_msg)
            yield {
                "type": "chunk",
                "content": error_msg
            }
        
        # 回复内容
        reply_content = "".join(full_reply)
        
        # 保存助手消息到数据库
        assistant_message_id = str(uuid.uuid4())
        self.database.create_message(
            message_id=assistant_message_id,
            conversation_id=conversation_id,
            role="assistant",
            content=reply_content
        )
        
        # 添加助手回复到会话
        assistant_msg = Msg(name="Assistant", role="assistant", content=reply_content)
        conversation.add_message(assistant_msg)
        
        self.logger.info(
            f"[ChatService] 流式回复完成 | conversation_id: {conversation_id} | "
            f"回复长度: {len(reply_content)}"
        )
        
        # 发送完成信号
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "plan_mode": conversation.plan_mode
        }

    def send_message_sync(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息并获取回复（同步包装器）
        
        用于兼容同步调用场景
        """
        return asyncio.run(self.send_message(message, user_id, conversation_id))

    def send_message_streaming_sync(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        发送消息并获取流式回复（同步包装器）
        
        用于兼容同步调用场景
        """
        async def collect():
            results = []
            async for item in self.send_message_streaming(message, user_id, conversation_id):
                results.append(item)
            return results
        
        for item in asyncio.run(collect()):
            yield item
