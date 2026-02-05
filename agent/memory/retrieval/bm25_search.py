"""
BM25 Search Retriever

基于 BM25 算法的关键词匹配检索工具。
适合精确术语查找和关键词搜索场景。
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import math

from ..base import RetrieverBase

logger = logging.getLogger(__name__)


class BM25Retriever(RetrieverBase):
    """
    BM25 关键词匹配检索器

    适用场景：
    - 精确术语查找
    - 关键词搜索
    - 专有名词检索

    特点：
    - 基于词频和文档频率
    - 对长文档有更好的归一化
    - 适合精确匹配场景
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("bm25_search", config)

        # BM25 参数
        self.k1 = config.get("k1", 1.5) if config else 1.5  # 词频饱和参数
        self.b = config.get("b", 0.75) if config else 0.75  # 文档长度归一化参数

        # 索引数据
        self._documents: List[str] = []
        self._doc_ids: List[str] = []
        self._tokenized_docs: List[List[str]] = []

        # 统计数据
        self._doc_freqs: Dict[str, int] = {}  # 文档频率
        self._avg_doc_len: float = 0.0
        self._doc_lengths: List[int] = []

        # 是否使用 rank_bm25 库
        self._bm25 = None
        self._use_library = False

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

        self._documents = documents
        self._doc_ids = ids or [f"doc_{i}" for i in range(len(documents))]

        # 尝试使用 rank_bm25 库
        try:
            from rank_bm25 import BM25Okapi
            self._tokenized_docs = [self._tokenize(doc) for doc in documents]
            self._bm25 = BM25Okapi(self._tokenized_docs, k1=self.k1, b=self.b)
            self._use_library = True
            logger.info(f"Indexed {len(documents)} documents using rank_bm25")
        except ImportError:
            # 回退到自实现
            self._build_index(documents)
            self._use_library = False
            logger.info(f"Indexed {len(documents)} documents using built-in BM25")

    def _tokenize(self, text: str) -> List[str]:
        """
        分词

        支持中英文混合文本
        """
        # 英文：按空格和标点分割
        # 中文：按字符分割
        tokens = []

        # 提取英文单词
        english_words = re.findall(r'[a-zA-Z]+', text.lower())
        tokens.extend(english_words)

        # 提取中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)

        # 提取数字
        numbers = re.findall(r'\d+', text)
        tokens.extend(numbers)

        return tokens

    def _build_index(self, documents: List[str]) -> None:
        """构建 BM25 索引（自实现）"""
        self._tokenized_docs = [self._tokenize(doc) for doc in documents]
        self._doc_lengths = [len(tokens) for tokens in self._tokenized_docs]
        self._avg_doc_len = sum(self._doc_lengths) / len(self._doc_lengths) if self._doc_lengths else 0

        # 计算文档频率
        self._doc_freqs = {}
        for tokens in self._tokenized_docs:
            seen = set()
            for token in tokens:
                if token not in seen:
                    self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1
                    seen.add(token)

    def search(
        self,
        query: str,
        documents: Optional[List[str]] = None,
        top_k: int = 5,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        执行 BM25 搜索

        Args:
            query: 查询文本
            documents: 可选的文档列表
            top_k: 返回数量

        Returns:
            (doc_index, score) 元组列表
        """
        if documents is not None:
            self.index_documents(documents)

        if not self._documents:
            return []

        query_tokens = self._tokenize(query)

        if self._use_library and self._bm25:
            # 使用 rank_bm25 库
            scores = self._bm25.get_scores(query_tokens)
            results = [(i, score) for i, score in enumerate(scores) if score > 0]
        else:
            # 使用自实现
            results = self._compute_scores(query_tokens)

        # 按得分排序
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def _compute_scores(self, query_tokens: List[str]) -> List[Tuple[int, float]]:
        """计算 BM25 得分（自实现）"""
        n_docs = len(self._documents)
        results = []

        for doc_idx, doc_tokens in enumerate(self._tokenized_docs):
            score = 0.0
            doc_len = self._doc_lengths[doc_idx]

            # 统计词频
            term_freqs = Counter(doc_tokens)

            for token in query_tokens:
                if token not in term_freqs:
                    continue

                # 词频
                tf = term_freqs[token]

                # 文档频率
                df = self._doc_freqs.get(token, 0)

                # IDF
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)

                # BM25 得分
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_len)
                score += idf * numerator / denominator

            if score > 0:
                results.append((doc_idx, score))

        return results

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

    def clear(self) -> None:
        """清空索引"""
        self._documents = []
        self._doc_ids = []
        self._tokenized_docs = []
        self._doc_freqs = {}
        self._avg_doc_len = 0.0
        self._doc_lengths = []
        self._bm25 = None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "total_documents": len(self._documents),
            "vocabulary_size": len(self._doc_freqs),
            "avg_doc_length": self._avg_doc_len,
            "use_library": self._use_library,
            "k1": self.k1,
            "b": self.b
        }
