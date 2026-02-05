"""
Page-ID Search Retriever

基于 Page ID 的直接访问检索工具。
用于快速获取已知页面的内容。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from ..base import RetrieverBase, PageStoreBase

logger = logging.getLogger(__name__)


class PageIDRetriever(RetrieverBase):
    """
    Page-ID 直接访问检索器

    适用场景：
    - 已知页面 ID 的快速获取
    - 根据索引中的引用获取详细内容
    - 批量页面获取

    特点：
    - O(1) 时间复杂度
    - 无需搜索，直接定位
    - 适合已知目标的检索
    """

    def __init__(
        self,
        page_store: Optional[PageStoreBase] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("page_id_search", config)
        self.page_store = page_store

        # 内存 ID -> 文档映射（如果不使用 PageStore）
        self._id_to_doc: Dict[str, str] = {}
        self._id_to_index: Dict[str, int] = {}

    def set_page_store(self, page_store: PageStoreBase) -> None:
        """设置 Page Store"""
        self.page_store = page_store

    def index_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None
    ) -> None:
        """
        索引文档

        Args:
            documents: 文档列表
            ids: 文档 ID 列表
        """
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]

        self._id_to_doc = {doc_id: doc for doc_id, doc in zip(ids, documents)}
        self._id_to_index = {doc_id: i for i, doc_id in enumerate(ids)}

        logger.info(f"Indexed {len(documents)} documents for Page-ID search")

    def search(
        self,
        query: str,
        documents: Optional[List[str]] = None,
        top_k: int = 5,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        根据 ID 搜索

        注意：对于 Page-ID 检索，query 应该是以逗号分隔的 ID 列表

        Args:
            query: 逗号分隔的 ID 列表
            documents: 可选的文档列表
            top_k: 返回数量

        Returns:
            (doc_index, score) 元组列表，score 总是 1.0
        """
        if documents is not None:
            self.index_documents(documents)

        # 解析 ID 列表
        page_ids = [pid.strip() for pid in query.split(",") if pid.strip()]

        results = []
        for page_id in page_ids[:top_k]:
            if page_id in self._id_to_index:
                results.append((self._id_to_index[page_id], 1.0))

        return results

    def get_by_id(self, page_id: str) -> Optional[str]:
        """
        根据 ID 获取文档

        Args:
            page_id: 页面 ID

        Returns:
            文档内容或 None
        """
        # 先从 PageStore 获取
        if self.page_store:
            page = self.page_store.get_page(page_id)
            if page:
                return page.content

        # 从内存映射获取
        return self._id_to_doc.get(page_id)

    def get_by_ids(self, page_ids: List[str]) -> Dict[str, Optional[str]]:
        """
        批量获取文档

        Args:
            page_ids: 页面 ID 列表

        Returns:
            ID -> 文档内容的映射
        """
        results = {}
        for page_id in page_ids:
            results[page_id] = self.get_by_id(page_id)
        return results

    def exists(self, page_id: str) -> bool:
        """检查 ID 是否存在"""
        if self.page_store:
            return self.page_store.get_page(page_id) is not None
        return page_id in self._id_to_doc

    def list_ids(self) -> List[str]:
        """列出所有 ID"""
        if self.page_store:
            return [page.page_id for page in self.page_store.iter_pages()]
        return list(self._id_to_doc.keys())

    def clear(self) -> None:
        """清空索引"""
        self._id_to_doc = {}
        self._id_to_index = {}

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = 0
        if self.page_store:
            total = self.page_store.get_stats().get("total_pages", 0)
        else:
            total = len(self._id_to_doc)

        return {
            "name": self.name,
            "total_documents": total,
            "has_page_store": self.page_store is not None
        }


class HybridRetriever:
    """
    混合检索器

    组合多种检索策略，实现 GAM 论文中的多工具组合检索。
    组合策略: 多工具组合 > 任意单工具 或 双工具组合
    """

    def __init__(
        self,
        retrievers: List[RetrieverBase],
        weights: Optional[Dict[str, float]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化混合检索器

        Args:
            retrievers: 检索器列表
            weights: 检索器权重，格式: {retriever_name: weight}
            config: 配置
        """
        self.retrievers = {r.get_name(): r for r in retrievers}
        self.weights = weights or {
            "vector_search": 0.5,
            "bm25_search": 0.3,
            "page_id_search": 0.2
        }
        self.config = config or {}

    def search(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
        use_retrievers: Optional[List[str]] = None
    ) -> List[Tuple[int, float]]:
        """
        执行混合检索

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回数量
            use_retrievers: 指定使用的检索器

        Returns:
            (doc_index, score) 元组列表
        """
        # 确定使用的检索器
        active_retrievers = use_retrievers or list(self.retrievers.keys())

        # 收集所有结果
        all_scores: Dict[int, List[Tuple[str, float]]] = {}

        for retriever_name in active_retrievers:
            if retriever_name not in self.retrievers:
                continue

            retriever = self.retrievers[retriever_name]
            weight = self.weights.get(retriever_name, 0.5)

            # 索引文档
            retriever.index_documents(documents)

            # 执行搜索
            results = retriever.search(query, top_k=top_k * 2)  # 多取一些以便合并

            for doc_idx, score in results:
                if doc_idx not in all_scores:
                    all_scores[doc_idx] = []
                all_scores[doc_idx].append((retriever_name, score * weight))

        # 合并得分
        final_scores = []
        for doc_idx, scores in all_scores.items():
            # 使用加权平均
            total_weight = sum(self.weights.get(name, 0.5) for name, _ in scores)
            total_score = sum(score for _, score in scores)
            final_score = total_score / total_weight if total_weight > 0 else 0
            final_scores.append((doc_idx, final_score))

        # 按得分排序
        final_scores.sort(key=lambda x: x[1], reverse=True)

        return final_scores[:top_k]

    def search_with_documents(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """搜索并返回文档内容"""
        results = self.search(query, documents, top_k)
        return [(documents[idx], score) for idx, score in results]

    def add_retriever(self, retriever: RetrieverBase, weight: float = 0.5) -> None:
        """添加检索器"""
        self.retrievers[retriever.get_name()] = retriever
        self.weights[retriever.get_name()] = weight

    def set_weight(self, retriever_name: str, weight: float) -> None:
        """设置检索器权重"""
        self.weights[retriever_name] = weight

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "retrievers": list(self.retrievers.keys()),
            "weights": self.weights,
            "retriever_stats": {
                name: r.get_stats()
                for name, r in self.retrievers.items()
            }
        }
