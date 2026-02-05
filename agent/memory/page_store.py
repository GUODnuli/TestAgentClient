"""
Page Store Implementation

基于 GAM 论文的 Page Store 实现，用于存储完整的历史记录。
采用 JSONL 文件 + ChromaDB 向量索引的混合存储方案。
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime
import json

from .base import PageStoreBase
from .models import Page, LightweightIndex, ContentType
from .utils import (
    generate_page_id,
    append_to_jsonl,
    deserialize_from_jsonl,
    save_json,
    load_json,
    EmbeddingManager,
    apply_filters,
    estimate_tokens
)

logger = logging.getLogger(__name__)


class PageStore(PageStoreBase):
    """
    Page Store 实现

    存储结构：
    - pages.jsonl: 完整页面数据（JSONL 格式）
    - index.json: 轻量级索引
    - chroma/: ChromaDB 向量数据库目录

    采用 GAM 论文的 JIT 原则：
    - 离线保持完整历史 + 轻量索引
    - 在线时通过多种检索方式动态构建上下文
    """

    def __init__(
        self,
        storage_path: Path,
        plan_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(storage_path, config)
        self.storage_path = Path(storage_path)
        self.plan_id = plan_id or "default"

        # 文件路径
        self.pages_file = self.storage_path / "pages.jsonl"
        self.index_file = self.storage_path / "index.json"
        self.chroma_path = self.storage_path / "chroma"

        # 内存缓存
        self._page_cache: Dict[str, Page] = {}
        self._embedding_manager = EmbeddingManager()

        # ChromaDB 集合
        self._collection = None
        self._chroma_client = None

    def initialize(self) -> None:
        """初始化存储"""
        # 创建目录
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 加载或创建索引
        self._load_or_create_index()

        # 初始化向量数据库
        self._init_vector_db()

        # 加载现有页面到缓存
        self._load_pages_to_cache()

        logger.info(f"PageStore initialized at {self.storage_path}")

    def _load_or_create_index(self) -> None:
        """加载或创建轻量级索引"""
        index_data = load_json(self.index_file)
        if index_data:
            self.index = LightweightIndex(**index_data)
        else:
            self.index = LightweightIndex(
                plan_id=self.plan_id,
                objective="",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self._save_index()

    def _save_index(self) -> None:
        """保存索引到文件"""
        if self.index:
            save_json(self.index.model_dump(), self.index_file)

    def _init_vector_db(self) -> None:
        """初始化向量数据库"""
        try:
            import chromadb
            from chromadb.config import Settings

            self._chroma_client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=Settings(anonymized_telemetry=False)
            )

            self._collection = self._chroma_client.get_or_create_collection(
                name=f"pages_{self.plan_id}",
                metadata={"hnsw:space": "cosine"}
            )

            logger.info(f"ChromaDB initialized with collection: pages_{self.plan_id}")
        except ImportError:
            logger.warning("chromadb not installed, vector search disabled")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    def _load_pages_to_cache(self) -> None:
        """加载页面到内存缓存"""
        if not self.pages_file.exists():
            return

        for page_data in deserialize_from_jsonl(self.pages_file):
            try:
                page = Page(**page_data)
                self._page_cache[page.page_id] = page
            except Exception as e:
                logger.warning(f"Failed to load page: {e}")

    def add_page(self, page: Page) -> str:
        """
        添加页面

        Args:
            page: 页面对象

        Returns:
            page_id
        """
        # 生成 ID（如果没有）
        if not page.page_id:
            page.page_id = generate_page_id()

        # 设置 plan_id
        if not page.plan_id:
            page.plan_id = self.plan_id

        # 生成嵌入向量
        if page.embedding is None and self._embedding_manager:
            page.embedding = self._embedding_manager.encode_single(page.content)

        # 保存到 JSONL 文件
        append_to_jsonl(page.model_dump(), self.pages_file)

        # 添加到缓存
        self._page_cache[page.page_id] = page

        # 更新索引
        self.update_index(page)
        self._save_index()

        # 添加到向量数据库
        self._add_to_vector_db(page)

        logger.debug(f"Added page: {page.page_id}")
        return page.page_id

    def _add_to_vector_db(self, page: Page) -> None:
        """添加页面到向量数据库"""
        if self._collection is None:
            return

        try:
            # 准备元数据
            metadata = {
                "timestamp": page.timestamp.isoformat(),
                "plan_id": page.plan_id or "",
                "phase": page.phase if page.phase is not None else -1,
                "worker": page.worker or "",
                "source_type": page.source_type.value if page.source_type else "",
            }
            # 添加标签
            for i, tag in enumerate(page.context_tags[:10]):  # 最多 10 个标签
                metadata[f"tag_{i}"] = tag

            self._collection.add(
                ids=[page.page_id],
                documents=[page.content],
                embeddings=[page.embedding] if page.embedding else None,
                metadatas=[metadata]
            )
        except Exception as e:
            logger.warning(f"Failed to add page to vector DB: {e}")

    def get_page(self, page_id: str) -> Optional[Page]:
        """
        获取页面

        Args:
            page_id: 页面 ID

        Returns:
            Page 对象或 None
        """
        # 先从缓存获取
        if page_id in self._page_cache:
            return self._page_cache[page_id]

        # 从文件加载
        for page_data in deserialize_from_jsonl(self.pages_file):
            if page_data.get("page_id") == page_id:
                page = Page(**page_data)
                self._page_cache[page_id] = page
                return page

        return None

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
        results = []

        # 使用向量数据库搜索
        if self._collection is not None:
            try:
                # 构建 where 子句
                where = self._build_where_clause(filters) if filters else None

                query_result = self._collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where
                )

                if query_result and query_result['ids']:
                    for i, page_id in enumerate(query_result['ids'][0]):
                        page = self.get_page(page_id)
                        if page:
                            # ChromaDB 返回的是距离，转换为相似度
                            distance = query_result['distances'][0][i] if query_result['distances'] else 0
                            score = 1 - distance  # 余弦距离转相似度
                            results.append((page, score))
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # 如果向量搜索不可用或无结果，使用简单文本匹配
        if not results:
            results = self._text_search(query, top_k, filters)

        return results

    def _build_where_clause(self, filters: Dict[str, Any]) -> Optional[Dict]:
        """构建 ChromaDB where 子句"""
        conditions = []

        if "plan_id" in filters:
            conditions.append({"plan_id": {"$eq": filters["plan_id"]}})
        if "phase" in filters:
            if isinstance(filters["phase"], dict):
                if "$lt" in filters["phase"]:
                    conditions.append({"phase": {"$lt": filters["phase"]["$lt"]}})
                if "$lte" in filters["phase"]:
                    conditions.append({"phase": {"$lte": filters["phase"]["$lte"]}})
            else:
                conditions.append({"phase": {"$eq": filters["phase"]}})
        if "worker" in filters:
            conditions.append({"worker": {"$eq": filters["worker"]}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _text_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[tuple]:
        """简单文本匹配搜索"""
        results = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for page in self._page_cache.values():
            # 应用过滤器
            if filters:
                page_dict = page.model_dump()
                if not self._match_filter(page_dict, filters):
                    continue

            # 计算匹配得分
            content_lower = page.content.lower()
            score = 0

            # 完整查询匹配
            if query_lower in content_lower:
                score += 0.5

            # 词项匹配
            for term in query_terms:
                if term in content_lower:
                    score += 0.1

            # 标签匹配
            for tag in page.context_tags:
                if query_lower in tag.lower():
                    score += 0.2

            if score > 0:
                results.append((page, min(score, 1.0)))

        # 按得分排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _match_filter(self, page_dict: Dict, filters: Dict[str, Any]) -> bool:
        """检查页面是否匹配过滤条件"""
        for key, condition in filters.items():
            value = page_dict.get(key)
            if isinstance(condition, dict):
                for op, op_value in condition.items():
                    if op == "$lt" and (value is None or value >= op_value):
                        return False
                    if op == "$lte" and (value is None or value > op_value):
                        return False
                    if op == "$gt" and (value is None or value <= op_value):
                        return False
                    if op == "$gte" and (value is None or value < op_value):
                        return False
            elif value != condition:
                return False
        return True

    def delete_page(self, page_id: str) -> bool:
        """
        删除页面

        注意：由于使用 JSONL 追加存储，实际删除需要重写文件
        """
        if page_id not in self._page_cache:
            return False

        # 从缓存移除
        del self._page_cache[page_id]

        # 从向量数据库移除
        if self._collection is not None:
            try:
                self._collection.delete(ids=[page_id])
            except Exception as e:
                logger.warning(f"Failed to delete from vector DB: {e}")

        # 重写 JSONL 文件
        self._rewrite_pages_file()

        return True

    def _rewrite_pages_file(self) -> None:
        """重写页面文件（移除已删除的页面）"""
        if not self.pages_file.exists():
            return

        # 临时文件
        temp_file = self.pages_file.with_suffix('.jsonl.tmp')

        with open(temp_file, 'w', encoding='utf-8') as f:
            for page in self._page_cache.values():
                json_str = json.dumps(page.model_dump(), ensure_ascii=False, default=str)
                f.write(json_str + '\n')

        # 替换原文件
        temp_file.replace(self.pages_file)

    def iter_pages(self) -> Generator[Page, None, None]:
        """迭代所有页面"""
        for page in self._page_cache.values():
            yield page

    def get_pages_by_phase(self, phase: int) -> List[Page]:
        """获取指定 Phase 的所有页面"""
        return [p for p in self._page_cache.values() if p.phase == phase]

    def get_pages_by_worker(self, worker: str) -> List[Page]:
        """获取指定 Worker 的所有页面"""
        return [p for p in self._page_cache.values() if p.worker == worker]

    def get_recent_pages(self, limit: int = 10) -> List[Page]:
        """获取最近的页面"""
        pages = list(self._page_cache.values())
        pages.sort(key=lambda p: p.timestamp, reverse=True)
        return pages[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_tokens = sum(estimate_tokens(p.content) for p in self._page_cache.values())

        phases = {}
        workers = {}
        content_types = {}

        for page in self._page_cache.values():
            if page.phase is not None:
                phases[page.phase] = phases.get(page.phase, 0) + 1
            if page.worker:
                workers[page.worker] = workers.get(page.worker, 0) + 1
            if page.source_type:
                ct = page.source_type.value
                content_types[ct] = content_types.get(ct, 0) + 1

        return {
            "total_pages": len(self._page_cache),
            "total_tokens_estimate": total_tokens,
            "pages_by_phase": phases,
            "pages_by_worker": workers,
            "pages_by_content_type": content_types,
            "index_tags": len(self.index.searchable_tags) if self.index else 0
        }

    def clear(self) -> None:
        """清空所有数据"""
        self._page_cache.clear()

        # 删除文件
        if self.pages_file.exists():
            self.pages_file.unlink()

        # 清空向量数据库
        if self._collection is not None:
            try:
                self._chroma_client.delete_collection(f"pages_{self.plan_id}")
                self._collection = self._chroma_client.get_or_create_collection(
                    name=f"pages_{self.plan_id}",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning(f"Failed to clear vector DB: {e}")

        # 重置索引
        self.index = LightweightIndex(
            plan_id=self.plan_id,
            objective="",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self._save_index()

        logger.info(f"PageStore cleared: {self.storage_path}")

    def export(self) -> Dict[str, Any]:
        """导出所有数据"""
        return {
            "plan_id": self.plan_id,
            "index": self.index.model_dump() if self.index else None,
            "pages": [p.model_dump() for p in self._page_cache.values()],
            "stats": self.get_stats()
        }

    def close(self) -> None:
        """关闭存储（保存索引）"""
        self._save_index()
        logger.info(f"PageStore closed: {self.storage_path}")
