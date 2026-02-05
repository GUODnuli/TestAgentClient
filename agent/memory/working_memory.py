"""
Working Memory (Layer 1)

工作记忆 - Worker 级别的短期记忆。
封装 AgentScope 的 InMemoryMemory，添加结果提取和协作记忆发布接口。
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import MemoryBase
from .models import (
    MemoryEntry,
    MemoryType,
    ContentType,
    SearchResult,
    MemoryStats
)
from .utils import generate_entry_id, extract_keywords, estimate_tokens

logger = logging.getLogger(__name__)


class WorkingMemory(MemoryBase):
    """
    工作记忆 (Layer 1: Worker-Scoped)

    特点：
    - 会话级别，Worker 任务完成即销毁
    - 存储当前 Worker 的执行上下文
    - 包含工具调用历史、中间推理结果
    - 任务完成时可提取关键结果发布到协作记忆

    封装 AgentScope 的 InMemoryMemory，提供额外功能：
    - 结构化的结果提取
    - 标签自动生成
    - 协作记忆发布接口
    """

    def __init__(
        self,
        worker_name: str,
        plan_id: Optional[str] = None,
        phase: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(MemoryType.WORKING, config)
        self.worker_name = worker_name
        self.plan_id = plan_id
        self.phase = phase

        # 内部存储
        self._entries: Dict[str, MemoryEntry] = {}
        self._message_history: List[Dict[str, Any]] = []  # 原始消息历史

        # AgentScope InMemoryMemory（可选集成）
        self._agentscope_memory = None

    def initialize(self) -> None:
        """初始化工作记忆"""
        try:
            from agentscope.memory import InMemoryMemory
            self._agentscope_memory = InMemoryMemory()
            logger.info(f"WorkingMemory initialized with AgentScope InMemoryMemory")
        except ImportError:
            logger.info(f"WorkingMemory initialized without AgentScope")

        self._initialized = True

    def add(self, entry: MemoryEntry) -> str:
        """添加记忆条目"""
        if not entry.entry_id:
            entry.entry_id = generate_entry_id()

        # 设置上下文信息
        entry.memory_type = MemoryType.WORKING
        entry.plan_id = entry.plan_id or self.plan_id
        entry.phase = entry.phase if entry.phase is not None else self.phase
        entry.worker = entry.worker or self.worker_name

        # 自动生成标签
        if not entry.tags and entry.content:
            content_str = str(entry.content)
            entry.tags = extract_keywords(content_str, max_keywords=5)

        self._entries[entry.entry_id] = entry
        logger.debug(f"Added entry to working memory: {entry.entry_id}")
        return entry.entry_id

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """
        添加对话消息（兼容 AgentScope 格式）

        Args:
            role: 角色 (user/assistant/system/tool)
            content: 消息内容
            **kwargs: 额外参数
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self._message_history.append(message)

        # 同步到 AgentScope memory
        if self._agentscope_memory:
            try:
                from agentscope.message import Msg
                msg = Msg(name=role, content=content, role=role)
                self._agentscope_memory.add(msg)
            except Exception as e:
                logger.debug(f"Failed to sync to AgentScope memory: {e}")

    def add_tool_result(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        success: bool = True
    ) -> str:
        """
        添加工具执行结果

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            tool_output: 工具输出
            success: 是否成功

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            memory_type=MemoryType.WORKING,
            content_type=ContentType.TOOL_EXECUTION,
            content={
                "tool_name": tool_name,
                "input": tool_input,
                "output": tool_output,
                "success": success
            },
            tags=[tool_name, "tool_execution"]
        )
        return self.add(entry)

    def add_reasoning(self, reasoning: str, step: Optional[int] = None) -> str:
        """
        添加推理过程

        Args:
            reasoning: 推理内容
            step: 推理步骤号

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            memory_type=MemoryType.WORKING,
            content_type=ContentType.RAW,
            content={
                "reasoning": reasoning,
                "step": step
            },
            tags=["reasoning"]
        )
        return self.add(entry)

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        return self._entries.get(entry_id)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        搜索工作记忆

        简单实现：关键词匹配
        """
        results = []
        query_lower = query.lower()

        for entry in self._entries.values():
            # 应用过滤器
            if filters:
                if not self._match_filters(entry, filters):
                    continue

            # 计算匹配得分
            content_str = str(entry.content).lower()
            score = 0

            if query_lower in content_str:
                score += 0.5

            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 0.2

            if score > 0:
                results.append(SearchResult(
                    entry=entry,
                    score=min(score, 1.0),
                    match_type="keyword"
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _match_filters(self, entry: MemoryEntry, filters: Dict[str, Any]) -> bool:
        """检查条目是否匹配过滤器"""
        for key, value in filters.items():
            entry_value = getattr(entry, key, None)
            if entry_value != value:
                return False
        return True

    def delete(self, entry_id: str) -> bool:
        """删除记忆条目"""
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def clear(self) -> None:
        """清空工作记忆"""
        self._entries.clear()
        self._message_history.clear()
        if self._agentscope_memory:
            self._agentscope_memory.clear()

    def export(self) -> Dict[str, Any]:
        """导出工作记忆"""
        return {
            "worker_name": self.worker_name,
            "plan_id": self.plan_id,
            "phase": self.phase,
            "entries": [e.model_dump() for e in self._entries.values()],
            "message_history": self._message_history
        }

    def load(self, data: Dict[str, Any]) -> None:
        """加载工作记忆"""
        self.worker_name = data.get("worker_name", self.worker_name)
        self.plan_id = data.get("plan_id", self.plan_id)
        self.phase = data.get("phase", self.phase)

        for entry_data in data.get("entries", []):
            entry = MemoryEntry(**entry_data)
            self._entries[entry.entry_id] = entry

        self._message_history = data.get("message_history", [])

    def get_stats(self) -> MemoryStats:
        """获取统计信息"""
        stats = MemoryStats(memory_type=MemoryType.WORKING)
        stats.total_entries = len(self._entries)

        # 按内容类型统计
        for entry in self._entries.values():
            ct = entry.content_type.value
            stats.entries_by_content_type[ct] = stats.entries_by_content_type.get(ct, 0) + 1

        # 时间范围
        if self._entries:
            timestamps = [e.timestamp for e in self._entries.values()]
            stats.oldest_entry = min(timestamps)
            stats.newest_entry = max(timestamps)

        return stats

    # ==================== 结果提取接口 ====================

    def extract_key_results(self) -> Dict[str, Any]:
        """
        提取关键结果，用于发布到协作记忆

        Returns:
            关键结果字典
        """
        results = {
            "worker": self.worker_name,
            "plan_id": self.plan_id,
            "phase": self.phase,
            "timestamp": datetime.now().isoformat(),
            "tool_executions": [],
            "findings": [],
            "errors": []
        }

        for entry in self._entries.values():
            if entry.content_type == ContentType.TOOL_EXECUTION:
                tool_data = entry.content
                results["tool_executions"].append({
                    "tool": tool_data.get("tool_name"),
                    "success": tool_data.get("success", True),
                    "summary": self._summarize_tool_output(tool_data)
                })

            elif entry.content_type in [
                ContentType.FILE_ANALYSIS,
                ContentType.API_EXTRACTION,
                ContentType.CODE_ANALYSIS
            ]:
                results["findings"].append({
                    "type": entry.content_type.value,
                    "content": entry.content,
                    "tags": entry.tags
                })

        return results

    def _summarize_tool_output(self, tool_data: Dict[str, Any]) -> str:
        """生成工具输出摘要"""
        output = tool_data.get("output", "")
        if isinstance(output, str) and len(output) > 200:
            return output[:200] + "..."
        return str(output)[:200]

    def get_message_history(self) -> List[Dict[str, Any]]:
        """获取消息历史"""
        return self._message_history.copy()

    def get_recent_entries(self, limit: int = 10) -> List[MemoryEntry]:
        """获取最近的条目"""
        entries = list(self._entries.values())
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def get_tool_executions(self) -> List[MemoryEntry]:
        """获取所有工具执行记录"""
        return [
            e for e in self._entries.values()
            if e.content_type == ContentType.TOOL_EXECUTION
        ]

    def get_context_for_llm(self, max_tokens: int = 4000) -> str:
        """
        生成用于 LLM 的上下文

        Args:
            max_tokens: 最大 token 数

        Returns:
            格式化的上下文字符串
        """
        context_parts = []
        total_tokens = 0

        # 添加最近的消息历史
        for msg in reversed(self._message_history[-20:]):
            msg_str = f"[{msg['role']}]: {msg['content']}"
            msg_tokens = estimate_tokens(msg_str)

            if total_tokens + msg_tokens > max_tokens:
                break

            context_parts.insert(0, msg_str)
            total_tokens += msg_tokens

        return "\n\n".join(context_parts)

    # ==================== AgentScope 兼容接口 ====================

    def get_agentscope_memory(self):
        """获取 AgentScope InMemoryMemory 实例"""
        return self._agentscope_memory

    def sync_from_agentscope(self) -> None:
        """从 AgentScope memory 同步消息"""
        if self._agentscope_memory is None:
            return

        try:
            for msg in self._agentscope_memory.get_memory():
                self.add_message(
                    role=msg.role,
                    content=msg.content,
                    name=msg.name
                )
        except Exception as e:
            logger.warning(f"Failed to sync from AgentScope: {e}")
