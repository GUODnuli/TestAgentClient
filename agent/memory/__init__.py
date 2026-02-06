# -*- coding: utf-8 -*-
"""
GAM Memory System Module

基于 GAM (General Agentic Memory) 论文设计的记忆系统。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GAM 记忆系统架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐ │
│  │     离线阶段 (Memorizer)     │    │     在线阶段 (Researcher)    │ │
│  │                             │    │                             │ │
│  │  输入: Worker 会话序列       │    │  输入: 用户查询 + 预构建记忆  │ │
│  │        ↓                    │    │        ↓                    │ │
│  │  LLM 生成:                  │    │  Deep-Research 循环:        │ │
│  │  • Session Memo (轻量摘要)   │    │  1. Planning (规划搜索)     │ │
│  │  • Pages (详细分段内容)      │    │  2. Searching (多工具检索)  │ │
│  │        ↓                    │    │  3. Reflection (反思评估)   │ │
│  │  存储:                      │    │        ↓                    │ │
│  │  • Memo → memo_store        │    │  输出: PreconstructedMemory │ │
│  │  • Pages → PageStore        │    │                             │ │
│  └─────────────────────────────┘    └─────────────────────────────┘ │
│                                                                      │
│                    ┌─────────────────────────────┐                  │
│                    │      Page Store             │                  │
│                    │  ├─ pages.jsonl (完整内容)  │                  │
│                    │  ├─ index.json (轻量索引)   │                  │
│                    │  └─ chroma/ (向量数据库)    │                  │
│                    └─────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

## 快速使用

```python
from agent.memory import MemoryManager, SessionMemo, PreconstructedMemory

# 1. 创建记忆管理器（带 LLM 模型）
manager = MemoryManager(
    storage_path="./storage/memory",
    model=llm_model
)

# 2. Phase 完成后，处理 Worker 会话
memo, pages = await manager.gam_process_session(
    session_id="plan1_p1_analyzer",
    messages=[...],  # Worker 的消息列表
    context={"plan_id": "plan1", "phase": 1, "worker": "analyzer"}
)

# 3. 下一个 Phase 开始前，获取历史上下文
pre_memory = await manager.gam_deep_research(
    query="实现用户认证功能",
    plan_id="plan1"
)
# pre_memory.context_summary 包含整合的历史上下文
# pre_memory.get_context_for_worker() 返回传递给 Worker 的上下文
```
"""

from typing import Any, Dict, List, Optional

from .models import (
    ContentType,
    GAMConfig,
    LightweightIndex,
    Page,
    PreconstructedMemory,
    SessionMemo,
)

from .base import (
    PageStoreBase,
    RetrieverBase,
)

from .page_store import PageStore
from .gam_memorizer import GAMMemorizer
from .gam_researcher import GAMResearcher

from .retrieval import (
    VectorSearchRetriever,
    BM25Retriever,
    PageIDRetriever,
)

from .utils import (
    segment_text,
    extract_keywords,
    generate_page_id,
    EmbeddingManager,
)


class MemoryManager:
    """
    GAM 记忆系统管理器

    统一管理 GAM 组件，提供便捷的创建和访问接口。

    组件:
    - GAMMemorizer: LLM 驱动的会话记忆化（离线阶段）
    - GAMResearcher: LLM 驱动的深度研究（在线阶段）
    - PageStore: 完整历史记录存储
    """

    def __init__(
        self,
        storage_path: str = "./storage/memory",
        config: Optional[Dict[str, Any]] = None,
        model: Optional[Any] = None
    ):
        """
        初始化记忆管理器

        Args:
            storage_path: 存储根目录
            config: 配置字典
            model: LLM 模型实例 (用于 GAM 组件)
        """
        from pathlib import Path

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.config = config or {}
        self.model = model

        # GAM 组件（懒加载）
        self._gam_memorizer: Optional[GAMMemorizer] = None
        self._gam_researcher: Optional[GAMResearcher] = None
        self._gam_page_store: Optional[PageStore] = None

        # 共享的 memo 存储
        self._memo_store: Dict[str, SessionMemo] = {}

    def _get_page_store(self, plan_id: str = "default") -> PageStore:
        """获取或创建 PageStore"""
        if self._gam_page_store is None:
            gam_storage = self.storage_path / "gam"
            self._gam_page_store = PageStore(
                storage_path=gam_storage,
                plan_id=plan_id,
                config=self.config.get("gam", {})
            )
            self._gam_page_store.initialize()
        return self._gam_page_store

    @property
    def gam_memorizer(self) -> Optional[GAMMemorizer]:
        """
        获取 GAMMemorizer 实例（懒加载）

        Returns:
            GAMMemorizer 实例，如果没有 model 则返回 None
        """
        if self._gam_memorizer is None and self.model is not None:
            self._gam_memorizer = GAMMemorizer(
                page_store=self._get_page_store(),
                model=self.model,
                config=self.config.get("gam", {})
            )
            # 共享 memo_store
            self._gam_memorizer.memo_store = self._memo_store
        return self._gam_memorizer

    @property
    def gam_researcher(self) -> Optional[GAMResearcher]:
        """
        获取 GAMResearcher 实例（懒加载）

        Returns:
            GAMResearcher 实例，如果没有 model 则返回 None
        """
        if self._gam_researcher is None and self.model is not None:
            self._gam_researcher = GAMResearcher(
                page_store=self._get_page_store(),
                memo_store=self._memo_store,
                model=self.model,
                config=self.config.get("gam", {})
            )
        return self._gam_researcher

    def set_model(self, model: Any) -> None:
        """
        设置 LLM 模型（用于延迟初始化 GAM 组件）

        Args:
            model: LLM 模型实例
        """
        self.model = model
        # 重置 GAM 组件以便使用新模型
        self._gam_memorizer = None
        self._gam_researcher = None

    async def gam_process_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> tuple:
        """
        使用 GAMMemorizer 处理 Worker 会话（离线阶段）

        Args:
            session_id: 会话 ID (格式: plan_phase_worker)
            messages: 消息列表 (text, thinking, tool_use, tool_result)
            context: 上下文信息 (plan_id, phase, worker, objective)

        Returns:
            (SessionMemo, List[Page]) 元组
        """
        if self.gam_memorizer is None:
            raise RuntimeError("GAMMemorizer not available (model not set)")
        return await self.gam_memorizer.process_session(session_id, messages, context)

    async def gam_deep_research(
        self,
        query: str,
        plan_id: Optional[str] = None
    ) -> PreconstructedMemory:
        """
        使用 GAMResearcher 执行深度研究（在线阶段）

        Args:
            query: 查询/目标
            plan_id: 可选的 Plan ID 过滤

        Returns:
            PreconstructedMemory 实例
        """
        if self.gam_researcher is None:
            raise RuntimeError("GAMResearcher not available (model not set)")
        return await self.gam_researcher.deep_research(query, plan_id)

    def gam_quick_search(
        self,
        query: str,
        plan_id: Optional[str] = None,
        top_k: int = 10
    ) -> PreconstructedMemory:
        """
        使用 GAMResearcher 快速搜索（不进行深度研究）

        Args:
            query: 查询文本
            plan_id: Plan ID 过滤
            top_k: 返回数量

        Returns:
            PreconstructedMemory 实例
        """
        if self.gam_researcher is None:
            raise RuntimeError("GAMResearcher not available (model not set)")
        return self.gam_researcher.quick_search(query, plan_id, top_k)

    def get_memo(self, session_id: str) -> Optional[SessionMemo]:
        """获取指定会话的 Memo"""
        return self._memo_store.get(session_id)

    def get_all_memos(self, plan_id: Optional[str] = None) -> List[SessionMemo]:
        """获取所有 Memos（可选按 plan_id 过滤）"""
        if plan_id:
            return [m for m in self._memo_store.values() if m.plan_id == plan_id]
        return list(self._memo_store.values())

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "memo_store_size": len(self._memo_store),
            "has_page_store": self._gam_page_store is not None,
            "has_memorizer": self._gam_memorizer is not None,
            "has_researcher": self._gam_researcher is not None,
        }

        if self._gam_memorizer:
            stats["memorizer_stats"] = self._gam_memorizer.get_stats()

        if self._gam_researcher:
            stats["researcher_stats"] = self._gam_researcher.get_stats()

        if self._gam_page_store:
            stats["page_store_stats"] = self._gam_page_store.get_stats()

        return stats

    def close(self) -> None:
        """关闭记忆系统"""
        if self._gam_page_store:
            self._gam_page_store.close()
            self._gam_page_store = None

        self._memo_store.clear()
        self._gam_memorizer = None
        self._gam_researcher = None


# 导出列表
__all__ = [
    # 数据模型
    "ContentType",
    "GAMConfig",
    "Page",
    "LightweightIndex",
    "SessionMemo",
    "PreconstructedMemory",

    # 基类
    "PageStoreBase",
    "RetrieverBase",

    # GAM 核心组件
    "PageStore",
    "GAMMemorizer",
    "GAMResearcher",

    # 检索器
    "VectorSearchRetriever",
    "BM25Retriever",
    "PageIDRetriever",

    # 管理器
    "MemoryManager",

    # 工具函数
    "segment_text",
    "extract_keywords",
    "generate_page_id",
    "EmbeddingManager",
]
