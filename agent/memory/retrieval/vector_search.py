"""
Vector Search Retriever

基于向量语义相似度的检索工具。
使用 sentence-transformers 生成嵌入，支持 ChromaDB 和内存索引。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from ..base import RetrieverBase
from ..utils import EmbeddingManager, cosine_similarity

logger = logging.getLogger(__name__)


class VectorSearchRetriever(RetrieverBase):
    """
    向量语义搜索检索器

    适用场景：
    - 主题相关性检索
    - 语义相似的内容查找
    - 模糊匹配

    特点：
    - 基于语义相似度，而非关键词匹配
    - 支持跨语言检索（取决于嵌入模型）
    - 适合长文本和概念性查询
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("vector_search", config)

        self._embedding_manager = EmbeddingManager()

        # 内存索引
        self._documents: List[str] = []
        self._doc_ids: List[str] = []
        self._embeddings: List[List[float]] = []

        # ChromaDB 集合（可选）
        self._collection = None
        self._use_chromadb = config.get("use_chromadb", False) if config else False

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
        if not documents:
            return

        # 生成 ID
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]

        # 生成嵌入
        embeddings = self._embedding_manager.encode(documents)
        if embeddings is None:
            logger.warning("Failed to generate embeddings, falling back to simple matching")
            self._documents = documents
            self._doc_ids = ids
            self._embeddings = []
            return

        self._documents = documents
        self._doc_ids = ids
        self._embeddings = embeddings

        logger.info(f"Indexed {len(documents)} documents for vector search")

    def search(
        self,
        query: str,
        documents: Optional[List[str]] = None,
        top_k: int = 5,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        执行向量搜索

        Args:
            query: 查询文本
            documents: 可选的文档列表（如果提供，则临时索引）
            top_k: 返回数量
            **kwargs: 额外参数

        Returns:
            (doc_index, score) 元组列表
        """
        # 如果提供了新文档，临时索引
        if documents is not None:
            self.index_documents(documents)

        if not self._documents:
            return []

        # 生成查询嵌入
        query_embedding = self._embedding_manager.encode_single(query)

        if query_embedding is None or not self._embeddings:
            # 回退到简单文本匹配
            return self._simple_search(query, top_k)

        # 计算相似度
        scores = []
        for i, doc_embedding in enumerate(self._embeddings):
            similarity = cosine_similarity(query_embedding, doc_embedding)
            scores.append((i, similarity))

        # 按相似度排序
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    def _simple_search(self, query: str, top_k: int) -> List[Tuple[int, float]]:
        """简单文本匹配（回退方案）"""
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        scores = []
        for i, doc in enumerate(self._documents):
            doc_lower = doc.lower()
            score = 0

            # 完整查询匹配
            if query_lower in doc_lower:
                score += 0.5

            # 词项匹配
            for term in query_terms:
                if term in doc_lower:
                    score += 0.1

            if score > 0:
                scores.append((i, min(score, 1.0)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def search_with_documents(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        搜索并返回文档内容

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回数量

        Returns:
            (document, score) 元组列表
        """
        self.index_documents(documents)
        results = self.search(query, top_k=top_k)

        return [(self._documents[idx], score) for idx, score in results]

    def get_document(self, index: int) -> Optional[str]:
        """获取指定索引的文档"""
        if 0 <= index < len(self._documents):
            return self._documents[index]
        return None

    def get_document_by_id(self, doc_id: str) -> Optional[str]:
        """根据 ID 获取文档"""
        if doc_id in self._doc_ids:
            idx = self._doc_ids.index(doc_id)
            return self._documents[idx]
        return None

    def clear(self) -> None:
        """清空索引"""
        self._documents = []
        self._doc_ids = []
        self._embeddings = []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "total_documents": len(self._documents),
            "has_embeddings": len(self._embeddings) > 0,
            "embedding_dimension": self._embedding_manager.get_dimension()
        }
