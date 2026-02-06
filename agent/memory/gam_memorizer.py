# -*- coding: utf-8 -*-
"""
GAM Memorizer - LLM 驱动的会话记忆化组件

基于 GAM 论文 (arxiv:2511.18423) 实现的离线阶段组件。
负责在 Worker 执行完成后，使用 LLM 生成结构化的记忆。

职责:
1. 接收 Worker 完整会话序列 (text, thinking, tool_use, tool_result)
2. LLM 生成 SessionMemo (轻量摘要)
3. LLM 分段生成 Pages (详细内容)
4. 存储到 PageStore 和 LightweightIndex

运行时机: Phase 完成后，对每个成功的 Worker 调用
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from inspect import isasyncgen
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import PageStoreBase
from .models import ContentType, Page, SessionMemo
from .utils import estimate_tokens, extract_keywords, generate_page_id, segment_text

logger = logging.getLogger(__name__)


class GAMMemorizer:
    """
    GAM 离线阶段 - LLM 驱动的会话记忆化

    主入口方法: process_session()
    """

    def __init__(
        self,
        page_store: PageStoreBase,
        model: Any,  # ChatModelBase 或类似接口
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化 GAMMemorizer

        Args:
            page_store: Page 存储实例
            model: LLM 模型实例 (需要支持异步调用)
            config: 配置选项
        """
        self.page_store = page_store
        self.model = model
        self.config = config or {}

        # 配置
        self.memo_max_length = self.config.get("memo_max_length", 500)
        self.page_max_length = self.config.get("page_max_length", 2000)
        self.page_overlap = self.config.get("page_overlap", 200)
        self.max_tags = self.config.get("max_tags", 10)

        # Memo 存储 (session_id -> SessionMemo)
        self.memo_store: Dict[str, SessionMemo] = {}

        # Prompt 模板路径
        self.prompts_dir = Path(self.config.get("prompts_dir", "prompts/memory"))

        # 统计
        self._sessions_processed = 0
        self._memos_created = 0
        self._pages_created = 0

    async def process_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Tuple[SessionMemo, List[Page]]:
        """
        处理完整会话 - 主入口

        Args:
            session_id: 会话 ID (格式: plan_phase_worker)
            messages: 消息列表 (包含 text, thinking, tool_use, tool_result)
            context: 上下文信息 (plan_id, phase, worker, objective)

        Returns:
            (SessionMemo, List[Page]) 元组
        """
        logger.info(f"GAMMemorizer: Processing session {session_id}")

        # 1. 格式化消息为文本
        session_text = self._format_messages(messages)
        if not session_text.strip():
            logger.warning(f"GAMMemorizer: Empty session content for {session_id}")
            # 创建空的 memo
            memo = SessionMemo(
                session_id=session_id,
                session_memo="空会话，无内容",
                plan_id=context.get("plan_id"),
                phase=context.get("phase"),
                worker=context.get("worker")
            )
            self.memo_store[session_id] = memo
            return memo, []

        # 2. LLM 生成 Session Memo
        memo = await self._generate_memo(session_id, session_text, context)

        # 3. LLM 分段生成 Pages
        pages = await self._generate_pages(session_id, session_text, messages, context, memo)

        # 4. 关联 memo 和 pages
        memo.page_ids = [p.page_id for p in pages]

        # 5. 存储
        self.memo_store[session_id] = memo
        for page in pages:
            self.page_store.add_page(page)

        # 更新统计
        self._sessions_processed += 1
        self._memos_created += 1
        self._pages_created += len(pages)

        logger.info(
            f"GAMMemorizer: Session {session_id} processed - "
            f"memo={memo.memo_id}, pages={len(pages)}"
        )

        return memo, pages

    def _format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        格式化消息列表为可读文本

        Args:
            messages: 消息列表

        Returns:
            格式化后的文本
        """
        parts = []

        for msg in messages:
            msg_type = msg.get("type", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            if msg_type == "text":
                if isinstance(content, dict):
                    text = content.get("text", "")
                else:
                    text = str(content) if content else ""
                if text:
                    parts.append(f"[TEXT] {text}")

            elif msg_type == "thinking":
                if isinstance(content, dict):
                    thinking = content.get("thinking", "")
                else:
                    thinking = str(content) if content else ""
                if thinking:
                    parts.append(f"[THINKING] {thinking}")

            elif msg_type == "tool_use":
                if isinstance(content, dict):
                    tool_name = content.get("name", "unknown")
                    tool_input = content.get("input", {})
                    tool_id = content.get("id", "")
                    input_str = json.dumps(tool_input, ensure_ascii=False, indent=2)[:500]
                    parts.append(f"[TOOL_CALL] {tool_name} (id={tool_id})\nInput: {input_str}")

            elif msg_type == "tool_result":
                if isinstance(content, dict):
                    tool_name = content.get("name", "unknown")
                    output = content.get("output", "")
                    tool_id = content.get("id", "")
                    if isinstance(output, list):
                        output_str = "\n".join(
                            item.get("text", str(item)) if isinstance(item, dict) else str(item)
                            for item in output
                        )[:1000]
                    else:
                        output_str = str(output)[:1000] if output else ""
                    parts.append(f"[TOOL_RESULT] {tool_name} (id={tool_id})\nOutput: {output_str}")

        return "\n\n".join(parts)

    async def _generate_memo(
        self,
        session_id: str,
        session_text: str,
        context: Dict[str, Any]
    ) -> SessionMemo:
        """
        使用 LLM 生成 Session Memo

        Args:
            session_id: 会话 ID
            session_text: 格式化后的会话文本
            context: 上下文信息

        Returns:
            SessionMemo 实例
        """
        # 构建 prompt
        prompt = self._build_memo_prompt(session_text, context)

        try:
            # 调用 LLM
            response = await self._call_model(prompt)

            # 解析响应
            memo_data = self._parse_memo_response(response)

            # 创建 SessionMemo
            memo = SessionMemo(
                session_id=session_id,
                session_memo=memo_data.get("session_memo", "会话摘要生成失败"),
                key_entities=memo_data.get("key_entities", []),
                key_actions=memo_data.get("key_actions", []),
                outcome_summary=memo_data.get("outcome_summary", ""),
                plan_id=context.get("plan_id"),
                phase=context.get("phase"),
                worker=context.get("worker")
            )

            return memo

        except Exception as e:
            logger.error(f"GAMMemorizer: Failed to generate memo for {session_id}: {e}")

            # 回退到简单摘要
            keywords = extract_keywords(session_text, max_keywords=5)
            return SessionMemo(
                session_id=session_id,
                session_memo=session_text[:200] + "..." if len(session_text) > 200 else session_text,
                key_entities=keywords,
                key_actions=[],
                outcome_summary="LLM 摘要生成失败，使用简单截断",
                plan_id=context.get("plan_id"),
                phase=context.get("phase"),
                worker=context.get("worker")
            )

    def _build_memo_prompt(self, session_text: str, context: Dict[str, Any]) -> str:
        """构建 Memo 生成的 prompt"""
        # 截断过长的内容
        truncated_text = session_text[:4000] if len(session_text) > 4000 else session_text

        return f"""你是记忆系统助手。分析以下 Worker 会话并生成简洁的 memo。

## 会话上下文
- Plan ID: {context.get('plan_id', 'N/A')}
- 目标: {context.get('objective', 'N/A')}
- Phase: {context.get('phase', 'N/A')}
- Worker: {context.get('worker', 'N/A')}

## 会话内容
{truncated_text}

## 任务
生成 JSON 格式的 memo，包含:
1. session_memo: 1-3 句话总结关键目的和结果
2. key_entities: 重要实体列表 (文件路径、函数名、API端点、类名等)
3. key_actions: 主要操作列表 (如：读取文件、分析代码、执行测试等)
4. outcome_summary: 完成了什么或学到了什么

只输出 JSON，不要其他内容:
```json
{{
  "session_memo": "...",
  "key_entities": ["entity1", "entity2", ...],
  "key_actions": ["action1", "action2", ...],
  "outcome_summary": "..."
}}
```"""

    def _parse_memo_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 返回的 memo JSON"""
        # 尝试从响应中提取 JSON
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取 {} 之间的内容
        brace_match = re.search(r'\{.*\}', response, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("GAMMemorizer: Failed to parse memo response, using fallback")
        return {
            "session_memo": response[:200],
            "key_entities": [],
            "key_actions": [],
            "outcome_summary": ""
        }

    async def _generate_pages(
        self,
        session_id: str,
        session_text: str,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any],
        memo: SessionMemo
    ) -> List[Page]:
        """
        分段生成 Pages

        Args:
            session_id: 会话 ID
            session_text: 格式化后的会话文本
            messages: 原始消息列表
            context: 上下文信息
            memo: 已生成的 SessionMemo

        Returns:
            Page 列表
        """
        pages = []

        # 分段
        segments = segment_text(
            session_text,
            max_length=self.page_max_length,
            overlap=self.page_overlap
        )

        for i, segment in enumerate(segments):
            # 为每个分段生成标签
            tags = self._generate_tags_for_segment(segment, memo, i, len(segments))

            # 创建 Page
            page = Page(
                page_id=generate_page_id(),
                content=segment,
                timestamp=datetime.now(),
                context_tags=tags,
                source_type=ContentType.CONVERSATION,
                source_id=session_id,
                plan_id=context.get("plan_id"),
                phase=context.get("phase"),
                worker=context.get("worker"),
                metadata={
                    "session_id": session_id,
                    "memo_id": memo.memo_id,
                    "segment_index": i,
                    "total_segments": len(segments),
                    "token_estimate": estimate_tokens(segment)
                }
            )

            pages.append(page)

        return pages

    def _generate_tags_for_segment(
        self,
        segment: str,
        memo: SessionMemo,
        segment_index: int,
        total_segments: int
    ) -> List[str]:
        """为分段生成标签"""
        tags = []

        # 添加 memo 中的关键实体（过滤出现在本段的）
        segment_lower = segment.lower()
        for entity in memo.key_entities:
            if entity.lower() in segment_lower:
                tags.append(entity)

        # 添加 memo 中的关键操作
        for action in memo.key_actions[:3]:
            tags.append(action)

        # 提取本段的关键词
        segment_keywords = extract_keywords(segment, max_keywords=5)
        tags.extend(segment_keywords)

        # 添加分段位置标签
        if segment_index == 0:
            tags.append("segment:start")
        elif segment_index == total_segments - 1:
            tags.append("segment:end")

        # 去重并限制数量
        return list(set(tags))[:self.max_tags]

    async def _call_model(self, prompt: str) -> str:
        """
        调用 LLM 模型

        处理流式和非流式响应。

        Args:
            prompt: 提示文本

        Returns:
            模型响应文本
        """
        from agentscope.message import Msg

        # 构建消息
        messages = [Msg(name="user", content=prompt, role="user")]

        # 调用模型
        result = self.model(messages)

        # 处理异步结果
        if asyncio.iscoroutine(result):
            result = await result

        # 处理流式响应
        if isasyncgen(result):
            collected = None
            async for chunk in result:
                collected = chunk
            result = collected

        # 提取文本内容
        if result is None:
            return ""

        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # 从内容块中提取文本
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        texts.append(block)
                return " ".join(texts)

        return str(result) if result else ""

    def get_memo(self, session_id: str) -> Optional[SessionMemo]:
        """获取指定会话的 Memo"""
        return self.memo_store.get(session_id)

    def get_all_memos(self) -> List[SessionMemo]:
        """获取所有 Memos"""
        return list(self.memo_store.values())

    def get_memos_by_plan(self, plan_id: str) -> List[SessionMemo]:
        """获取指定 Plan 的所有 Memos"""
        return [m for m in self.memo_store.values() if m.plan_id == plan_id]

    def get_memos_by_phase(self, plan_id: str, phase: int) -> List[SessionMemo]:
        """获取指定 Phase 的所有 Memos"""
        return [
            m for m in self.memo_store.values()
            if m.plan_id == plan_id and m.phase == phase
        ]

    def search_memos(
        self,
        query: str,
        plan_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[Tuple[SessionMemo, float]]:
        """
        搜索 Memos

        简单的关键词匹配搜索。

        Args:
            query: 查询文本
            plan_id: 可选的 Plan ID 过滤
            top_k: 返回数量

        Returns:
            (SessionMemo, score) 元组列表
        """
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        results = []
        for memo in self.memo_store.values():
            # 过滤 Plan
            if plan_id and memo.plan_id != plan_id:
                continue

            # 计算得分
            score = 0.0
            search_text = memo.to_search_text().lower()

            # 完整查询匹配
            if query_lower in search_text:
                score += 0.5

            # 词项匹配
            for term in query_terms:
                if term in search_text:
                    score += 0.1

            # 实体匹配
            for entity in memo.key_entities:
                if query_lower in entity.lower():
                    score += 0.2

            if score > 0:
                results.append((memo, min(score, 1.0)))

        # 排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "sessions_processed": self._sessions_processed,
            "memos_created": self._memos_created,
            "pages_created": self._pages_created,
            "memo_store_size": len(self.memo_store)
        }

    def clear(self) -> None:
        """清空存储"""
        self.memo_store.clear()
        self._sessions_processed = 0
        self._memos_created = 0
        self._pages_created = 0
