"""
聊天 Agent 服务

基于 Dify API 实现 User-Assistant 对话功能。
参考 AgentScope 的消息概念设计。
"""

import uuid
import time
from typing import Any, Dict, Generator, List, Optional
from datetime import datetime

from backend.common.dify_client import DifyClient, DifyAPIError
from backend.common.logger import get_logger


class Message:
    """
    消息类
    
    参考 AgentScope 的 Msg 概念，包含：
    - name: 发送者名称
    - role: 角色（user/assistant/system）
    - content: 消息内容
    - timestamp: 时间戳
    """
    
    def __init__(
        self,
        name: str,
        role: str,
        content: str,
        timestamp: Optional[str] = None
    ):
        self.name = name
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            name=data.get("name", ""),
            role=data.get("role", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp")
        )


class Conversation:
    """
    对话会话类
    
    管理单个对话的消息历史，参考 AgentScope 的 InMemoryMemory 概念。
    """
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.messages: List[Message] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
    
    def add_message(self, message: Message):
        """添加消息到会话"""
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取消息历史"""
        messages = self.messages[-limit:] if limit else self.messages
        return [msg.to_dict() for msg in messages]
    
    def get_context_for_llm(self, max_messages: int = 20) -> str:
        """
        获取用于 LLM 的上下文字符串
        
        将对话历史格式化为 LLM 可理解的格式
        """
        recent_messages = self.messages[-max_messages:]
        context_parts = []
        
        for msg in recent_messages:
            role_label = "用户" if msg.role == "user" else "助手"
            context_parts.append(f"{role_label}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def clear(self):
        """清空对话历史"""
        self.messages = []
        self.updated_at = datetime.now().isoformat()


class ChatAgent:
    """
    聊天 Agent
    
    负责处理用户消息并生成回复，参考 AgentScope 的 DialogAgent 概念。
    """
    
    def __init__(
        self,
        dify_client: DifyClient,
        system_prompt: Optional[str] = None
    ):
        self.dify_client = dify_client
        self.logger = get_logger()
        
        # 系统提示词
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        
        self.logger.info("ChatAgent 初始化完成")
    
    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """你是 MCP 接口测试智能体的 AI 助手。你的职责是：

1. 帮助用户理解和使用接口测试功能
2. 回答关于 API 测试、测试用例生成的问题
3. 提供测试相关的建议和最佳实践
4. 解释测试报告和结果

请用友好、专业的语气回复用户。如果用户的问题超出你的能力范围，请诚实告知。"""
    
    def reply(self, user_message: str, conversation_context: str = "") -> str:
        """
        生成回复
        
        Args:
            user_message: 用户消息
            conversation_context: 对话上下文
            
        Returns:
            助手回复
        """
        self.logger.info(f"[ChatAgent] 处理用户消息 | 长度: {len(user_message)}")
        
        try:
            # 构建完整的提示
            if conversation_context:
                full_prompt = f"""以下是之前的对话记录：
{conversation_context}

现在用户说：{user_message}

请根据上下文回复用户。"""
            else:
                full_prompt = user_message
            
            # 调用 Dify API
            start_time = time.time()
            
            response = self.dify_client.call_workflow(
                inputs={
                    "system_prompt": self.system_prompt,
                    "user_input": full_prompt
                },
                user="chat_user"
            )
            
            elapsed = time.time() - start_time
            self.logger.info(f"[ChatAgent] Dify API 调用成功 | 耗时: {elapsed:.2f}s")
            
            # 提取回复内容
            reply_content = self._extract_reply(response)
            
            return reply_content
        
        except DifyAPIError as e:
            self.logger.error(f"[ChatAgent] Dify API 调用失败: {str(e)}")
            return f"抱歉，服务暂时不可用。错误信息：{str(e)}"
        
        except Exception as e:
            self.logger.error(f"[ChatAgent] 生成回复失败: {str(e)}", exc_info=True)
            return "抱歉，处理消息时发生错误。请稍后重试。"
    
    def _extract_reply(self, response: Dict[str, Any]) -> str:
        """从 Dify 响应中提取回复内容"""
        outputs = response.get("data", {}).get("outputs", {})
        
        # 尝试多种可能的字段名
        for field in ["text", "output", "result", "reply", "response"]:
            if field in outputs:
                return str(outputs[field])
        
        # 如果没有找到预期字段，返回整个 outputs
        if outputs:
            return str(outputs)
        
        return "抱歉，无法生成有效回复。"
    
    def reply_streaming(
        self,
        user_message: str,
        conversation_context: str = ""
    ) -> Generator[str, None, None]:
        """
        生成流式回复
        
        Args:
            user_message: 用户消息
            conversation_context: 对话上下文
            
        Yields:
            回复的文本块
        """
        self.logger.info(f"[ChatAgent] 处理用户消息（流式）| 长度: {len(user_message)}")
        
        try:
            # 构建完整的提示
            if conversation_context:
                full_prompt = f"""以下是之前的对话记录：
{conversation_context}

现在用户说：{user_message}

请根据上下文回复用户。"""
            else:
                full_prompt = user_message
            
            # 调用 Dify API（流式）
            for chunk in self.dify_client.call_workflow_streaming(
                inputs={
                    "system_prompt": self.system_prompt,
                    "user_input": full_prompt
                },
                user="chat_user"
            ):
                yield chunk
        
        except DifyAPIError as e:
            self.logger.error(f"[ChatAgent] Dify API 调用失败: {str(e)}")
            yield f"抱歉，服务暂时不可用。错误信息：{str(e)}"
        
        except Exception as e:
            self.logger.error(f"[ChatAgent] 生成回复失败: {str(e)}", exc_info=True)
            yield "抱歉，处理消息时发生错误。请稍后重试。"


class ChatService:
    """
    聊天服务
    
    管理多个对话会话，提供高层 API 接口。
    """
    
    def __init__(self, dify_config: Dict[str, Any], system_prompt: Optional[str] = None):
        """
        初始化聊天服务
        
        Args:
            dify_config: Dify 配置
            system_prompt: 自定义系统提示词
        """
        self.logger = get_logger()
        
        # 初始化 Dify 客户端
        self.dify_client = DifyClient(dify_config)
        
        # 初始化聊天 Agent
        self.chat_agent = ChatAgent(self.dify_client, system_prompt)
        
        # 会话存储（内存中）
        self.conversations: Dict[str, Conversation] = {}
        
        # 配置
        self.max_context_messages = 20  # 最大上下文消息数
        
        self.logger.info("ChatService 初始化完成")
    
    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息并获取回复
        
        Args:
            message: 用户消息
            conversation_id: 会话ID（可选，为空时创建新会话）
            
        Returns:
            包含回复和会话ID的字典
        """
        self.logger.info(
            f"[ChatService] 收到消息 | conversation_id: {conversation_id} | 消息长度: {len(message)}"
        )
        
        # 获取或创建会话
        if conversation_id and conversation_id in self.conversations:
            conversation = self.conversations[conversation_id]
        else:
            conversation_id = str(uuid.uuid4())
            conversation = Conversation(conversation_id)
            self.conversations[conversation_id] = conversation
            self.logger.info(f"[ChatService] 创建新会话 | conversation_id: {conversation_id}")
        
        # 添加用户消息
        user_msg = Message(name="User", role="user", content=message)
        conversation.add_message(user_msg)
        
        # 获取对话上下文
        context = conversation.get_context_for_llm(self.max_context_messages - 1)
        
        # 生成回复
        reply_content = self.chat_agent.reply(message, context)
        
        # 添加助手回复
        assistant_msg = Message(name="Assistant", role="assistant", content=reply_content)
        conversation.add_message(assistant_msg)
        
        self.logger.info(
            f"[ChatService] 回复生成完成 | conversation_id: {conversation_id} | 回复长度: {len(reply_content)}"
        )
        
        return {
            "conversation_id": conversation_id,
            "reply": reply_content,
            "timestamp": assistant_msg.timestamp
        }
    
    def send_message_streaming(
        self,
        message: str,
        conversation_id: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        发送消息并获取流式回复
        
        Args:
            message: 用户消息
            conversation_id: 会话ID（可选，为空时创建新会话）
            
        Yields:
            包含回复块的字典
        """
        self.logger.info(
            f"[ChatService] 收到消息（流式）| conversation_id: {conversation_id} | 消息长度: {len(message)}"
        )
        
        # 获取或创建会话
        if conversation_id and conversation_id in self.conversations:
            conversation = self.conversations[conversation_id]
        else:
            conversation_id = str(uuid.uuid4())
            conversation = Conversation(conversation_id)
            self.conversations[conversation_id] = conversation
            self.logger.info(f"[ChatService] 创建新会话 | conversation_id: {conversation_id}")
        
        # 添加用户消息
        user_msg = Message(name="User", role="user", content=message)
        conversation.add_message(user_msg)
        
        # 获取对话上下文
        context = conversation.get_context_for_llm(self.max_context_messages - 1)
        
        # 先发送会话ID
        yield {
            "type": "start",
            "conversation_id": conversation_id
        }
        
        # 收集完整回复
        full_reply = []
        
        # 流式生成回复
        for chunk in self.chat_agent.reply_streaming(message, context):
            full_reply.append(chunk)
            yield {
                "type": "chunk",
                "content": chunk
            }
        
        # 添加助手回复到会话
        reply_content = "".join(full_reply)
        assistant_msg = Message(name="Assistant", role="assistant", content=reply_content)
        conversation.add_message(assistant_msg)
        
        self.logger.info(
            f"[ChatService] 流式回复完成 | conversation_id: {conversation_id} | 回复长度: {len(reply_content)}"
        )
        
        # 发送完成信号
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "timestamp": assistant_msg.timestamp
        }
    
    def get_history(self, conversation_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        获取对话历史
        
        Args:
            conversation_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            对话历史
        """
        if conversation_id not in self.conversations:
            return {
                "success": False,
                "error": "会话不存在"
            }
        
        conversation = self.conversations[conversation_id]
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": conversation.get_history(limit),
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at
        }
    
    def clear_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        清空对话历史
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            操作结果
        """
        if conversation_id not in self.conversations:
            return {
                "success": False,
                "error": "会话不存在"
            }
        
        self.conversations[conversation_id].clear()
        self.logger.info(f"[ChatService] 清空会话 | conversation_id: {conversation_id}")
        
        return {
            "success": True,
            "message": "对话历史已清空"
        }
    
    def delete_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        删除会话
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            操作结果
        """
        if conversation_id not in self.conversations:
            return {
                "success": False,
                "error": "会话不存在"
            }
        
        del self.conversations[conversation_id]
        self.logger.info(f"[ChatService] 删除会话 | conversation_id: {conversation_id}")
        
        return {
            "success": True,
            "message": "会话已删除"
        }
    
    def list_conversations(self) -> Dict[str, Any]:
        """
        列出所有会话
        
        Returns:
            会话列表
        """
        conversations = []
        for conv_id, conv in self.conversations.items():
            conversations.append({
                "conversation_id": conv_id,
                "message_count": len(conv.messages),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at
            })
        
        return {
            "success": True,
            "conversations": conversations
        }
