"""
GAM Memorizer Component

基于 GAM 论文的 Memorizer 组件实现。
负责后台持续运行，在每次交互后更新记忆。

职责：
1. 创建轻量级摘要（关键信息摘要）
2. 将完整对话分段存档到 Page Store
3. 为每个页面添加上下文标签，便于检索
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import MemorizerBase, PageStoreBase
from .models import Page, ContentType
from .utils import (
    segment_text,
    extract_keywords,
    generate_page_id,
    estimate_tokens
)

logger = logging.getLogger(__name__)


class Memorizer(MemorizerBase):
    """
    GAM Memorizer 组件

    运行时机: 后台持续运行，在每次交互后更新

    主要功能：
    - 自动分段长文本
    - 提取上下文标签
    - 生成内容摘要
    - 存档到 Page Store
    """

    def __init__(
        self,
        page_store: PageStoreBase,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(page_store, config)

        # 配置
        self.max_page_length = config.get("max_page_length", 2000) if config else 2000
        self.overlap_length = config.get("overlap_length", 200) if config else 200
        self.max_tags = config.get("max_tags", 10) if config else 10

        # LLM 接口（用于智能摘要，可选）
        self._llm = None

        # 统计
        self._pages_created = 0
        self._total_content_processed = 0

    def set_llm(self, llm) -> None:
        """设置 LLM 接口（用于智能摘要）"""
        self._llm = llm

    def memorize(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Page:
        """
        将内容记忆化

        Args:
            content: 要记忆的内容
            context: 上下文信息，包含：
                - plan_id: Plan ID
                - phase: Phase 编号
                - worker: Worker 名称
                - content_type: 内容类型
                - tags: 预设标签

        Returns:
            创建的 Page 对象
        """
        context = context or {}

        # 提取标签
        tags = context.get("tags", [])
        auto_tags = self.extract_tags(content)
        all_tags = list(set(tags + auto_tags))[:self.max_tags]

        # 生成摘要
        summary = self.summarize(content)

        # 创建 Page
        page = Page(
            page_id=generate_page_id(),
            content=content,
            timestamp=datetime.now(),
            context_tags=all_tags,
            source_type=context.get("content_type"),
            plan_id=context.get("plan_id"),
            phase=context.get("phase"),
            worker=context.get("worker"),
            metadata={
                "summary": summary,
                "original_length": len(content),
                "token_estimate": estimate_tokens(content)
            }
        )

        # 存储到 Page Store
        self.page_store.add_page(page)
        self._pages_created += 1
        self._total_content_processed += len(content)

        logger.debug(f"Memorized content to page: {page.page_id}")
        return page

    def memorize_long_content(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Page]:
        """
        记忆化长内容（自动分段）

        Args:
            content: 长内容
            context: 上下文信息

        Returns:
            创建的 Page 列表
        """
        context = context or {}

        # 分段
        segments = segment_text(
            content,
            max_length=self.max_page_length,
            overlap=self.overlap_length
        )

        pages = []
        for i, segment in enumerate(segments):
            # 为每个分段添加序号
            segment_context = context.copy()
            segment_context["segment_index"] = i
            segment_context["total_segments"] = len(segments)

            page = self.memorize(segment, segment_context)
            pages.append(page)

        logger.info(f"Memorized long content into {len(pages)} pages")
        return pages

    def memorize_conversation(
        self,
        messages: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Page]:
        """
        记忆化对话历史

        Args:
            messages: 消息列表，格式: [{"role": str, "content": str}, ...]
            context: 上下文信息

        Returns:
            创建的 Page 列表
        """
        context = context or {}
        context["content_type"] = ContentType.CONVERSATION

        pages = []
        current_batch = []
        current_length = 0

        for msg in messages:
            msg_text = f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
            msg_length = len(msg_text)

            # 如果当前批次加上新消息超过限制，先保存当前批次
            if current_length + msg_length > self.max_page_length and current_batch:
                batch_content = "\n\n".join(current_batch)
                page = self.memorize(batch_content, context)
                pages.append(page)
                current_batch = []
                current_length = 0

            current_batch.append(msg_text)
            current_length += msg_length

        # 保存最后一个批次
        if current_batch:
            batch_content = "\n\n".join(current_batch)
            page = self.memorize(batch_content, context)
            pages.append(page)

        return pages

    def memorize_tool_execution(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        success: bool,
        context: Optional[Dict[str, Any]] = None
    ) -> Page:
        """
        记忆化工具执行

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            tool_output: 工具输出
            success: 是否成功
            context: 上下文信息

        Returns:
            创建的 Page
        """
        context = context or {}
        context["content_type"] = ContentType.TOOL_EXECUTION
        context["tags"] = context.get("tags", []) + [tool_name, "tool_execution"]

        content = f"""Tool: {tool_name}
Status: {"Success" if success else "Failed"}

Input:
{self._format_dict(tool_input)}

Output:
{self._format_output(tool_output)}
"""

        return self.memorize(content, context)

    def _format_dict(self, d: Dict[str, Any], indent: int = 2) -> str:
        """格式化字典"""
        lines = []
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{' ' * indent}{key}:")
                lines.append(self._format_dict(value, indent + 2))
            else:
                lines.append(f"{' ' * indent}{key}: {value}")
        return "\n".join(lines)

    def _format_output(self, output: Any) -> str:
        """格式化输出"""
        if isinstance(output, str):
            return output[:2000] if len(output) > 2000 else output
        elif isinstance(output, dict):
            return self._format_dict(output)
        else:
            output_str = str(output)
            return output_str[:2000] if len(output_str) > 2000 else output_str

    def extract_tags(self, content: str) -> List[str]:
        """
        从内容中提取标签

        使用多种策略：
        1. 关键词提取
        2. 实体识别（简单规则）
        3. 代码相关标签
        """
        tags = []

        # 基础关键词提取
        keywords = extract_keywords(content, max_keywords=5)
        tags.extend(keywords)

        # 提取代码相关标签
        code_tags = self._extract_code_tags(content)
        tags.extend(code_tags)

        # 提取特殊实体
        entity_tags = self._extract_entities(content)
        tags.extend(entity_tags)

        # 去重并限制数量
        return list(set(tags))[:self.max_tags]

    def _extract_code_tags(self, content: str) -> List[str]:
        """提取代码相关标签"""
        tags = []

        # 检测编程语言
        if re.search(r'\bdef\s+\w+\s*\(', content):
            tags.append("python")
        if re.search(r'\bfunction\s+\w+\s*\(', content):
            tags.append("javascript")
        if re.search(r'\bclass\s+\w+', content):
            tags.append("class")
        if re.search(r'\basync\s+', content):
            tags.append("async")

        # 检测 API 相关
        if re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+/', content, re.IGNORECASE):
            tags.append("api")
        if re.search(r'https?://', content):
            tags.append("url")

        # 检测测试相关
        if re.search(r'\b(test|spec|assert|expect)\b', content, re.IGNORECASE):
            tags.append("test")

        return tags

    def _extract_entities(self, content: str) -> List[str]:
        """提取命名实体（简单规则）"""
        tags = []

        # 提取文件路径
        paths = re.findall(r'[\w/\\]+\.\w{2,4}', content)
        for path in paths[:3]:
            ext = path.split('.')[-1].lower()
            if ext in ['py', 'js', 'ts', 'json', 'yaml', 'yml', 'md']:
                tags.append(ext)

        # 提取函数名模式
        functions = re.findall(r'\b(get|set|create|update|delete|fetch|send|handle)_?\w+', content, re.IGNORECASE)
        for func in functions[:3]:
            tags.append(func.lower()[:20])

        return tags

    def summarize(self, content: str) -> str:
        """
        生成内容摘要

        如果设置了 LLM，使用 LLM 生成摘要；
        否则使用简单的提取策略。
        """
        # 如果有 LLM，使用 LLM 摘要
        if self._llm:
            try:
                return self._llm_summarize(content)
            except Exception as e:
                logger.warning(f"LLM summarization failed: {e}")

        # 简单摘要策略
        return self._simple_summarize(content)

    def _llm_summarize(self, content: str) -> str:
        """使用 LLM 生成摘要"""
        prompt = f"""请为以下内容生成一个简短的摘要（不超过100字）：

{content[:3000]}

摘要："""
        response = self._llm(prompt)
        return response[:200] if len(response) > 200 else response

    def _simple_summarize(self, content: str) -> str:
        """简单摘要策略"""
        # 取前几行作为摘要
        lines = content.split('\n')
        summary_lines = []
        total_length = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if total_length + len(line) > 200:
                break
            summary_lines.append(line)
            total_length += len(line)

        if summary_lines:
            return " ".join(summary_lines)

        # 如果没有有意义的行，截取开头
        return content[:200].strip() + "..." if len(content) > 200 else content

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "pages_created": self._pages_created,
            "total_content_processed": self._total_content_processed,
            "avg_page_length": (
                self._total_content_processed / self._pages_created
                if self._pages_created > 0 else 0
            )
        }
