# -*- coding: utf-8 -*-
"""
Memory Base Classes

GAM 记忆系统的抽象基类，提供统一的接口规范。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Generator
from pathlib import Path

from .models import Page, LightweightIndex


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
