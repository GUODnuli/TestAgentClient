"""
Memory Base Classes

定义记忆系统的抽象基类，提供统一的接口规范。
所有记忆实现（工作记忆、协作记忆、全局记忆）都应继承此基类。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Generator
from pathlib import Path
from datetime import datetime
import json

from .models import (
    MemoryEntry,
    MemoryType,
    ContentType,
    SearchQuery,
    SearchResult,
    MemoryStats,
    Page,
    LightweightIndex
)


class MemoryBase(ABC):
    """
    记忆系统统一抽象基类

    提供三层记忆系统的统一接口：
    - Layer 1: WorkingMemory (Worker-Scoped)
    - Layer 2: CollaborativeMemory (Plan-Scoped)
    - Layer 3: GlobalMemory (Persistent)
    """

    def __init__(self, memory_type: MemoryType, config: Optional[Dict[str, Any]] = None):
        self.memory_type = memory_type
        self.config = config or {}
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """初始化记忆存储"""
        pass

    @abstractmethod
    def add(self, entry: MemoryEntry) -> str:
        """
        添加记忆条目

        Args:
            entry: 记忆条目

        Returns:
            entry_id: 记忆条目 ID
        """
        pass

    @abstractmethod
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        根据 ID 获取记忆条目

        Args:
            entry_id: 记忆条目 ID

        Returns:
            MemoryEntry 或 None
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        搜索记忆

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        pass

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """
        删除记忆条目

        Args:
            entry_id: 记忆条目 ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有记忆"""
        pass

    @abstractmethod
    def export(self) -> Dict[str, Any]:
        """
        导出记忆为可序列化格式

        Returns:
            包含所有记忆数据的字典
        """
        pass

    @abstractmethod
    def load(self, data: Dict[str, Any]) -> None:
        """
        从序列化数据加载记忆

        Args:
            data: 序列化的记忆数据
        """
        pass

    def add_batch(self, entries: List[MemoryEntry]) -> List[str]:
        """
        批量添加记忆条目

        Args:
            entries: 记忆条目列表

        Returns:
            entry_id 列表
        """
        return [self.add(entry) for entry in entries]

    def get_batch(self, entry_ids: List[str]) -> List[Optional[MemoryEntry]]:
        """
        批量获取记忆条目

        Args:
            entry_ids: 记忆条目 ID 列表

        Returns:
            MemoryEntry 列表（可能包含 None）
        """
        return [self.get(entry_id) for entry_id in entry_ids]

    def search_by_query(self, query: SearchQuery) -> List[SearchResult]:
        """
        使用 SearchQuery 对象搜索

        Args:
            query: SearchQuery 对象

        Returns:
            搜索结果列表
        """
        return self.search(
            query=query.query,
            top_k=query.top_k,
            filters=query.to_filters()
        )

    def get_stats(self) -> MemoryStats:
        """
        获取记忆统计信息

        Returns:
            MemoryStats 对象
        """
        # 默认实现，子类可覆盖以提供更详细的统计
        return MemoryStats(memory_type=self.memory_type)

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def __enter__(self):
        """上下文管理器入口"""
        if not self._initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        pass


class PageStoreBase(ABC):
    """
    Page Store 抽象基类

    基于 GAM 论文的设计，Page Store 用于存储完整的历史记录。
    采用 JIT (Just-in-Time) 原则，保持完整信息而非压缩摘要。
    """

    def __init__(self, storage_path: Path, config: Optional[Dict[str, Any]] = None):
        self.storage_path = Path(storage_path)
        self.config = config or {}
        self.index: Optional[LightweightIndex] = None

    @abstractmethod
    def initialize(self) -> None:
        """初始化存储"""
        pass

    @abstractmethod
    def add_page(self, page: Page) -> str:
        """
        添加页面

        Args:
            page: 页面对象

        Returns:
            page_id
        """
        pass

    @abstractmethod
    def get_page(self, page_id: str) -> Optional[Page]:
        """
        获取页面

        Args:
            page_id: 页面 ID

        Returns:
            Page 对象或 None
        """
        pass

    @abstractmethod
    def search_pages(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """
        搜索页面

        Args:
            query: 搜索查询
            top_k: 返回数量
            filters: 过滤条件

        Returns:
            (Page, score) 元组列表
        """
        pass

    @abstractmethod
    def delete_page(self, page_id: str) -> bool:
        """删除页面"""
        pass

    @abstractmethod
    def iter_pages(self) -> Generator[Page, None, None]:
        """迭代所有页面"""
        pass

    def get_pages_by_ids(self, page_ids: List[str]) -> List[Optional[Page]]:
        """批量获取页面"""
        return [self.get_page(pid) for pid in page_ids]

    def get_pages_by_tag(self, tag: str) -> List[Page]:
        """根据标签获取页面"""
        if self.index:
            page_ids = self.index.get_pages_by_tag(tag)
            pages = self.get_pages_by_ids(page_ids)
            return [p for p in pages if p is not None]
        return []

    def get_index(self) -> Optional[LightweightIndex]:
        """获取轻量级索引"""
        return self.index

    def update_index(self, page: Page) -> None:
        """更新索引"""
        if self.index:
            self.index.add_page_reference(page)


class RetrieverBase(ABC):
    """
    检索器抽象基类

    GAM 论文定义的三种检索工具的基类：
    - VectorSearch: 语义相似度检索
    - BM25Search: 关键词匹配检索
    - PageIDSearch: ID 直接访问
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def search(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
        **kwargs
    ) -> List[tuple]:
        """
        执行检索

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回数量
            **kwargs: 额外参数

        Returns:
            (doc_index, score) 元组列表
        """
        pass

    @abstractmethod
    def index_documents(self, documents: List[str], ids: Optional[List[str]] = None) -> None:
        """
        索引文档

        Args:
            documents: 文档列表
            ids: 文档 ID 列表
        """
        pass

    def get_name(self) -> str:
        """获取检索器名称"""
        return self.name


class MemorizerBase(ABC):
    """
    Memorizer 抽象基类

    GAM 论文的 Memorizer 组件，负责：
    1. 创建轻量级摘要（关键信息摘要）
    2. 将完整对话分段存档到 Page Store
    3. 为每个页面添加上下文标签，便于检索

    运行时机: 后台持续运行，在每次交互后更新
    """

    def __init__(self, page_store: PageStoreBase, config: Optional[Dict[str, Any]] = None):
        self.page_store = page_store
        self.config = config or {}

    @abstractmethod
    def memorize(self, content: str, context: Optional[Dict[str, Any]] = None) -> Page:
        """
        将内容记忆化

        Args:
            content: 要记忆的内容
            context: 上下文信息

        Returns:
            创建的 Page 对象
        """
        pass

    @abstractmethod
    def extract_tags(self, content: str) -> List[str]:
        """
        从内容中提取标签

        Args:
            content: 内容文本

        Returns:
            标签列表
        """
        pass

    @abstractmethod
    def summarize(self, content: str) -> str:
        """
        生成内容摘要

        Args:
            content: 内容文本

        Returns:
            摘要文本
        """
        pass


class ResearcherBase(ABC):
    """
    Researcher 抽象基类

    GAM 论文的 Researcher 组件，负责：
    1. 分析用户查询，规划搜索策略
    2. 使用三种工具进行深度检索
    3. 迭代验证和反思搜索结果
    4. 整合信息构建优化上下文

    运行时机: 仅在收到特定请求时激活
    """

    def __init__(
        self,
        page_store: PageStoreBase,
        retrievers: List[RetrieverBase],
        config: Optional[Dict[str, Any]] = None
    ):
        self.page_store = page_store
        self.retrievers = {r.get_name(): r for r in retrievers}
        self.config = config or {}

    @abstractmethod
    def research(
        self,
        query: str,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        执行深度研究

        Args:
            query: 研究查询
            max_iterations: 最大迭代次数

        Returns:
            研究结果，包含：
            - context: 整合的上下文
            - sources: 来源页面列表
            - strategy: 使用的搜索策略
        """
        pass

    @abstractmethod
    def plan_search_strategy(self, query: str) -> Dict[str, Any]:
        """
        规划搜索策略

        Args:
            query: 查询文本

        Returns:
            搜索策略，包含使用的检索器和参数
        """
        pass

    @abstractmethod
    def validate_results(
        self,
        query: str,
        results: List[Page]
    ) -> tuple:
        """
        验证搜索结果

        Args:
            query: 原始查询
            results: 搜索结果

        Returns:
            (is_sufficient: bool, feedback: str)
        """
        pass

    @abstractmethod
    def integrate_context(self, pages: List[Page], query: str) -> str:
        """
        整合上下文

        Args:
            pages: 相关页面列表
            query: 原始查询

        Returns:
            整合后的上下文文本
        """
        pass
