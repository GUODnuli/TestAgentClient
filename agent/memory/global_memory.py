"""
Global Memory (Layer 3)

全局记忆 - 持久化的跨会话记忆。
存储项目知识、成功模式、用户偏好等长期有价值的信息。
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base import MemoryBase
from .models import (
    MemoryEntry,
    MemoryType,
    ContentType,
    SearchResult,
    MemoryStats,
    Page
)
from .page_store import PageStore
from .utils import (
    generate_entry_id,
    extract_keywords,
    save_json,
    load_json,
    compute_text_hash
)

logger = logging.getLogger(__name__)


class GlobalMemory(MemoryBase):
    """
    全局记忆 (Layer 3: Persistent)

    特点：
    - 跨会话持久化
    - 存储长期有价值的知识
    - 支持知识积累和检索
    - 自动清理过期内容

    存储内容类型：
    - 项目结构理解
    - API 文档摘要
    - 成功的测试模式
    - 用户偏好
    - 错误处理经验

    存储结构：
    storage/memory/global/
    ├── pages.jsonl          # 完整页面数据
    ├── index.json           # 轻量级索引
    ├── chroma/              # 向量数据库
    ├── metadata.json        # 元数据
    └── categories/          # 按类别组织
        ├── project_knowledge.json
        ├── patterns.json
        └── preferences.json
    """

    def __init__(
        self,
        storage_path: str,
        retention_days: int = 90,
        max_entries: int = 10000,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(MemoryType.GLOBAL, config)
        self.storage_path = Path(storage_path) / "global"
        self.retention_days = retention_days
        self.max_entries = max_entries

        # Page Store
        self.page_store: Optional[PageStore] = None

        # 分类存储
        self._categories_dir = self.storage_path / "categories"
        self._metadata_file = self.storage_path / "metadata.json"

        # 内存缓存（按类别）
        self._category_cache: Dict[str, List[Dict]] = {}

        # 去重哈希表
        self._content_hashes: set = set()

    def initialize(self) -> None:
        """初始化全局记忆"""
        # 创建目录
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._categories_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 Page Store
        self.page_store = PageStore(
            storage_path=self.storage_path,
            plan_id="global",
            config=self.config
        )
        self.page_store.initialize()

        # 加载分类数据
        self._load_categories()

        # 加载内容哈希（用于去重）
        self._load_content_hashes()

        # 执行过期清理
        self._cleanup_expired()

        self._initialized = True
        logger.info(f"GlobalMemory initialized at {self.storage_path}")

    def _load_categories(self) -> None:
        """加载分类数据"""
        for category_file in self._categories_dir.glob("*.json"):
            category = category_file.stem
            data = load_json(category_file)
            if data:
                self._category_cache[category] = data.get("entries", [])

    def _save_category(self, category: str) -> None:
        """保存分类数据"""
        category_file = self._categories_dir / f"{category}.json"
        save_json({
            "category": category,
            "updated_at": datetime.now().isoformat(),
            "entries": self._category_cache.get(category, [])
        }, category_file)

    def _load_content_hashes(self) -> None:
        """加载内容哈希"""
        for page in self.page_store.iter_pages():
            content_hash = compute_text_hash(page.content)
            self._content_hashes.add(content_hash)

    def _cleanup_expired(self) -> None:
        """清理过期内容"""
        if self.retention_days <= 0:
            return

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        expired_count = 0

        for page in list(self.page_store.iter_pages()):
            if page.timestamp < cutoff_date:
                self.page_store.delete_page(page.page_id)
                expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired entries from global memory")

    # ==================== 核心接口 ====================

    def add(self, entry: MemoryEntry) -> str:
        """添加记忆条目"""
        # 检查去重
        content_str = str(entry.content)
        content_hash = compute_text_hash(content_str)
        if content_hash in self._content_hashes:
            logger.debug(f"Duplicate content detected, skipping: {entry.entry_id}")
            return ""

        if not entry.entry_id:
            entry.entry_id = generate_entry_id()

        entry.memory_type = MemoryType.GLOBAL

        # 自动生成标签
        if not entry.tags:
            entry.tags = extract_keywords(content_str, max_keywords=10)

        # 转换为 Page 并存储
        page = entry.to_page()
        self.page_store.add_page(page)

        # 记录哈希
        self._content_hashes.add(content_hash)

        # 按类别存储
        category = self._get_category(entry.content_type)
        if category not in self._category_cache:
            self._category_cache[category] = []

        self._category_cache[category].append({
            "entry_id": entry.entry_id,
            "content_type": entry.content_type.value,
            "summary": entry.summary,
            "tags": entry.tags,
            "timestamp": entry.timestamp.isoformat()
        })
        self._save_category(category)

        # 检查容量限制
        self._check_capacity()

        logger.debug(f"Added entry to global memory: {entry.entry_id}")
        return entry.entry_id

    def _get_category(self, content_type: ContentType) -> str:
        """根据内容类型获取分类"""
        category_map = {
            ContentType.PROJECT_KNOWLEDGE: "project_knowledge",
            ContentType.USER_PREFERENCE: "preferences",
            ContentType.SUCCESS_PATTERN: "patterns",
            ContentType.ERROR_PATTERN: "patterns",
            ContentType.API_EXTRACTION: "api_knowledge",
            ContentType.FILE_ANALYSIS: "project_knowledge",
            ContentType.CODE_ANALYSIS: "project_knowledge",
        }
        return category_map.get(content_type, "general")

    def _check_capacity(self) -> None:
        """检查并处理容量限制"""
        stats = self.page_store.get_stats()
        if stats["total_pages"] > self.max_entries:
            # 删除最旧的 10% 条目
            to_delete = int(self.max_entries * 0.1)
            pages = list(self.page_store.iter_pages())
            pages.sort(key=lambda p: p.timestamp)

            for page in pages[:to_delete]:
                self.page_store.delete_page(page.page_id)

            logger.info(f"Capacity limit reached, removed {to_delete} oldest entries")

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        page = self.page_store.get_page(entry_id[:8])
        if page:
            return self._page_to_entry(page)
        return None

    def _page_to_entry(self, page: Page) -> MemoryEntry:
        """将 Page 转换为 MemoryEntry"""
        return MemoryEntry(
            entry_id=page.source_id or page.page_id,
            memory_type=MemoryType.GLOBAL,
            content_type=page.source_type or ContentType.RAW,
            content={"text": page.content},
            timestamp=page.timestamp,
            tags=page.context_tags,
            embedding=page.embedding,
            metadata=page.metadata
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """搜索全局记忆"""
        results = []

        page_results = self.page_store.search_pages(query, top_k, filters)
        for page, score in page_results:
            entry = self._page_to_entry(page)
            results.append(SearchResult(
                entry=entry,
                score=score,
                match_type="hybrid"
            ))

        return results

    def delete(self, entry_id: str) -> bool:
        """删除记忆条目"""
        return self.page_store.delete_page(entry_id[:8])

    def clear(self) -> None:
        """清空全局记忆"""
        self.page_store.clear()
        self._category_cache.clear()
        self._content_hashes.clear()

        for category_file in self._categories_dir.glob("*.json"):
            category_file.unlink()

    def export(self) -> Dict[str, Any]:
        """导出全局记忆"""
        return {
            "page_store": self.page_store.export() if self.page_store else None,
            "categories": self._category_cache,
            "stats": self.get_stats().model_dump()
        }

    def load(self, data: Dict[str, Any]) -> None:
        """加载全局记忆"""
        self._category_cache = data.get("categories", {})
        for category in self._category_cache:
            self._save_category(category)

    # ==================== 知识管理接口 ====================

    def add_project_knowledge(
        self,
        knowledge: Dict[str, Any],
        tags: Optional[List[str]] = None,
        source: Optional[str] = None
    ) -> str:
        """
        添加项目知识

        Args:
            knowledge: 知识内容（如项目结构、架构信息等）
            tags: 标签
            source: 知识来源

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            memory_type=MemoryType.GLOBAL,
            content_type=ContentType.PROJECT_KNOWLEDGE,
            content=knowledge,
            tags=tags or [],
            metadata={"source": source} if source else {}
        )
        return self.add(entry)

    def add_success_pattern(
        self,
        pattern: Dict[str, Any],
        context: str,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        添加成功模式

        Args:
            pattern: 模式内容（如成功的测试策略、代码模式等）
            context: 模式适用的上下文
            tags: 标签

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            memory_type=MemoryType.GLOBAL,
            content_type=ContentType.SUCCESS_PATTERN,
            content={
                "pattern": pattern,
                "context": context
            },
            tags=tags or ["success_pattern"],
            summary=f"Success pattern for: {context}"
        )
        return self.add(entry)

    def add_error_pattern(
        self,
        error: str,
        solution: str,
        context: str,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        添加错误处理模式

        Args:
            error: 错误描述
            solution: 解决方案
            context: 错误发生的上下文
            tags: 标签

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            memory_type=MemoryType.GLOBAL,
            content_type=ContentType.ERROR_PATTERN,
            content={
                "error": error,
                "solution": solution,
                "context": context
            },
            tags=tags or ["error_pattern"],
            summary=f"Error: {error[:100]}..."
        )
        return self.add(entry)

    def add_user_preference(
        self,
        preference_key: str,
        preference_value: Any,
        description: Optional[str] = None
    ) -> str:
        """
        添加用户偏好

        Args:
            preference_key: 偏好键
            preference_value: 偏好值
            description: 描述

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            memory_type=MemoryType.GLOBAL,
            content_type=ContentType.USER_PREFERENCE,
            content={
                "key": preference_key,
                "value": preference_value,
                "description": description
            },
            tags=["user_preference", preference_key],
            summary=f"Preference: {preference_key}"
        )
        return self.add(entry)

    # ==================== 知识检索接口 ====================

    def get_project_knowledge(self, query: Optional[str] = None, top_k: int = 10) -> List[Dict]:
        """获取项目知识"""
        if query:
            results = self.search(query, top_k, {
                "content_type": {"$in": [ContentType.PROJECT_KNOWLEDGE.value]}
            })
            return [r.entry.content for r in results]

        # 返回所有项目知识
        entries = self._category_cache.get("project_knowledge", [])
        return entries[:top_k]

    def get_patterns(
        self,
        pattern_type: str = "all",
        query: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """
        获取模式

        Args:
            pattern_type: "success", "error", 或 "all"
            query: 可选的搜索查询
            top_k: 返回数量

        Returns:
            模式列表
        """
        content_types = []
        if pattern_type in ["success", "all"]:
            content_types.append(ContentType.SUCCESS_PATTERN.value)
        if pattern_type in ["error", "all"]:
            content_types.append(ContentType.ERROR_PATTERN.value)

        if query:
            results = self.search(query, top_k, {
                "content_type": {"$in": content_types}
            })
            return [r.entry.content for r in results]

        # 返回分类缓存中的模式
        patterns = self._category_cache.get("patterns", [])
        return patterns[:top_k]

    def get_user_preferences(self) -> Dict[str, Any]:
        """获取所有用户偏好"""
        preferences = {}
        for entry_info in self._category_cache.get("preferences", []):
            entry = self.get(entry_info["entry_id"])
            if entry:
                content = entry.content
                if "key" in content:
                    preferences[content["key"]] = content.get("value")
        return preferences

    def find_similar_errors(self, error: str, top_k: int = 5) -> List[Dict]:
        """
        查找类似的错误处理经验

        Args:
            error: 当前错误描述
            top_k: 返回数量

        Returns:
            相似错误及其解决方案列表
        """
        results = self.search(error, top_k, {
            "content_type": {"$in": [ContentType.ERROR_PATTERN.value]}
        })
        return [
            {
                "error": r.entry.content.get("error"),
                "solution": r.entry.content.get("solution"),
                "context": r.entry.content.get("context"),
                "similarity": r.score
            }
            for r in results
        ]

    # ==================== 统计信息 ====================

    def get_stats(self) -> MemoryStats:
        """获取统计信息"""
        stats = MemoryStats(memory_type=MemoryType.GLOBAL)

        if self.page_store:
            page_stats = self.page_store.get_stats()
            stats.total_pages = page_stats["total_pages"]
            stats.total_entries = stats.total_pages
            stats.entries_by_content_type = page_stats.get("pages_by_content_type", {})

        return stats

    def get_summary(self) -> Dict[str, Any]:
        """获取全局记忆摘要"""
        return {
            "total_entries": sum(len(entries) for entries in self._category_cache.values()),
            "categories": {
                category: len(entries)
                for category, entries in self._category_cache.items()
            },
            "retention_days": self.retention_days,
            "max_entries": self.max_entries,
            "stats": self.page_store.get_stats() if self.page_store else {}
        }

    def close(self) -> None:
        """关闭全局记忆"""
        if self.page_store:
            self.page_store.close()
        logger.info(f"GlobalMemory closed")
