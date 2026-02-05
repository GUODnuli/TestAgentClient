"""
Memory System Module

三层记忆架构实现，基于 GAM (General Agentic Memory) 论文设计。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        三层记忆架构                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 1: 工作记忆 (Working Memory)                          │    │
│  │  存储: 当前 Worker 的执行上下文                               │    │
│  │  生命周期: Worker 任务完成即销毁                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓ 任务完成时提取关键结果                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 2: 协作记忆 (Collaborative Memory)                    │    │
│  │  存储: Phase 间共享的工作结果                                 │    │
│  │  生命周期: 整个 Plan 执行期间                                 │    │
│  │  解决问题: Worker 重复读取文件                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓ Plan 完成时提取有价值知识              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Layer 3: 全局记忆 (Global Memory)                           │    │
│  │  存储: 跨会话的持久化知识                                     │    │
│  │  生命周期: 永久                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## 快速使用

```python
from agent.memory import (
    WorkingMemory,
    CollaborativeMemory,
    GlobalMemory,
    MemoryManager
)

# 1. 创建记忆管理器
manager = MemoryManager(storage_path="./storage/memory")

# 2. Worker 使用工作记忆
working_mem = manager.create_working_memory(
    worker_name="analyzer",
    plan_id="plan_001",
    phase=1
)
working_mem.add_tool_result("read_file", {...}, "file content", success=True)

# 3. Phase 完成后发布到协作记忆
collab_mem = manager.get_collaborative_memory("plan_001")
collab_mem.publish_phase_output(
    phase=1,
    worker="analyzer",
    output_type=ContentType.FILE_ANALYSIS,
    content={"files": [...], "apis": [...]},
    tags=["api", "analysis"]
)

# 4. 后续 Phase 获取上下文
context = collab_mem.get_context_for_phase(phase=2)
# context["previous_outputs"] 包含 Phase 1 的输出，无需重新读取文件
```

## 模块组成

- **models**: 数据模型定义
- **base**: 抽象基类
- **working_memory**: 工作记忆实现
- **collaborative_memory**: 协作记忆实现
- **global_memory**: 全局记忆实现
- **page_store**: GAM Page Store 实现
- **memorizer**: GAM Memorizer 组件
- **researcher**: GAM Researcher 组件
- **retrieval**: 检索工具（向量搜索、BM25、Page-ID）
"""

from .models import (
    MemoryType,
    ContentType,
    Page,
    LightweightIndex,
    MemoryEntry,
    SearchQuery,
    SearchResult,
    MemoryStats,
    MemoryConfig
)

from .base import (
    MemoryBase,
    PageStoreBase,
    RetrieverBase,
    MemorizerBase,
    ResearcherBase
)

from .working_memory import WorkingMemory
from .collaborative_memory import CollaborativeMemory
from .global_memory import GlobalMemory
from .page_store import PageStore
from .memorizer import Memorizer
from .researcher import Researcher

from .retrieval import (
    VectorSearchRetriever,
    BM25Retriever,
    PageIDRetriever
)

from .utils import (
    segment_text,
    extract_keywords,
    generate_entry_id,
    generate_page_id,
    EmbeddingManager
)


class MemoryManager:
    """
    记忆系统管理器

    统一管理三层记忆，提供便捷的创建和访问接口。
    """

    def __init__(
        self,
        storage_path: str = "./storage/memory",
        config: dict = None
    ):
        """
        初始化记忆管理器

        Args:
            storage_path: 存储根目录
            config: 配置字典
        """
        from pathlib import Path

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.config = config or {}

        # 缓存
        self._working_memories: dict = {}
        self._collaborative_memories: dict = {}
        self._global_memory: GlobalMemory = None

    def create_working_memory(
        self,
        worker_name: str,
        plan_id: str = None,
        phase: int = None
    ) -> WorkingMemory:
        """
        创建工作记忆

        Args:
            worker_name: Worker 名称
            plan_id: Plan ID
            phase: Phase 编号

        Returns:
            WorkingMemory 实例
        """
        key = f"{plan_id}_{phase}_{worker_name}"
        if key not in self._working_memories:
            memory = WorkingMemory(
                worker_name=worker_name,
                plan_id=plan_id,
                phase=phase,
                config=self.config.get("working", {})
            )
            memory.initialize()
            self._working_memories[key] = memory

        return self._working_memories[key]

    def get_collaborative_memory(
        self,
        plan_id: str,
        objective: str = ""
    ) -> CollaborativeMemory:
        """
        获取或创建协作记忆

        Args:
            plan_id: Plan ID
            objective: Plan 目标描述

        Returns:
            CollaborativeMemory 实例
        """
        if plan_id not in self._collaborative_memories:
            memory = CollaborativeMemory(
                plan_id=plan_id,
                storage_path=str(self.storage_path),
                objective=objective,
                config=self.config.get("collaborative", {})
            )
            memory.initialize()
            self._collaborative_memories[plan_id] = memory

        return self._collaborative_memories[plan_id]

    def get_global_memory(self) -> GlobalMemory:
        """
        获取全局记忆

        Returns:
            GlobalMemory 实例
        """
        if self._global_memory is None:
            global_config = self.config.get("global_memory", {})
            self._global_memory = GlobalMemory(
                storage_path=str(self.storage_path),
                retention_days=global_config.get("retention_days", 90),
                max_entries=global_config.get("max_entries", 10000),
                config=global_config
            )
            self._global_memory.initialize()

        return self._global_memory

    def publish_to_collaborative(
        self,
        plan_id: str,
        phase: int,
        worker: str,
        output_type: ContentType,
        content: dict,
        tags: list = None
    ) -> str:
        """
        发布输出到协作记忆的便捷方法

        Args:
            plan_id: Plan ID
            phase: Phase 编号
            worker: Worker 名称
            output_type: 输出类型
            content: 输出内容
            tags: 标签

        Returns:
            entry_id
        """
        collab_mem = self.get_collaborative_memory(plan_id)
        return collab_mem.publish_phase_output(
            phase=phase,
            worker=worker,
            output_type=output_type,
            content=content,
            tags=tags
        )

    def get_context_for_worker(
        self,
        plan_id: str,
        phase: int,
        query: str = None
    ) -> dict:
        """
        为 Worker 获取上下文的便捷方法

        Args:
            plan_id: Plan ID
            phase: 当前 Phase 编号
            query: 可选的查询

        Returns:
            上下文字典
        """
        collab_mem = self.get_collaborative_memory(plan_id)
        return collab_mem.get_context_for_phase(phase, query)

    def search_all(
        self,
        query: str,
        top_k: int = 10,
        include_global: bool = True
    ) -> list:
        """
        跨所有记忆层搜索

        Args:
            query: 搜索查询
            top_k: 返回数量
            include_global: 是否包含全局记忆

        Returns:
            搜索结果列表
        """
        all_results = []

        # 搜索所有协作记忆
        for collab_mem in self._collaborative_memories.values():
            results = collab_mem.search(query, top_k=top_k // 2)
            all_results.extend(results)

        # 搜索全局记忆
        if include_global:
            global_mem = self.get_global_memory()
            results = global_mem.search(query, top_k=top_k // 2)
            all_results.extend(results)

        # 按得分排序
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]

    def cleanup_working_memories(self, plan_id: str = None) -> int:
        """
        清理工作记忆

        Args:
            plan_id: 可选的 Plan ID，如果提供则只清理该 Plan 的工作记忆

        Returns:
            清理的记忆数量
        """
        count = 0
        keys_to_remove = []

        for key in self._working_memories:
            if plan_id is None or key.startswith(f"{plan_id}_"):
                self._working_memories[key].clear()
                keys_to_remove.append(key)
                count += 1

        for key in keys_to_remove:
            del self._working_memories[key]

        return count

    def close_collaborative_memory(self, plan_id: str) -> None:
        """
        关闭协作记忆

        Args:
            plan_id: Plan ID
        """
        if plan_id in self._collaborative_memories:
            self._collaborative_memories[plan_id].close()
            del self._collaborative_memories[plan_id]

    def close(self) -> None:
        """关闭所有记忆"""
        # 关闭工作记忆
        for memory in self._working_memories.values():
            memory.clear()
        self._working_memories.clear()

        # 关闭协作记忆
        for memory in self._collaborative_memories.values():
            memory.close()
        self._collaborative_memories.clear()

        # 关闭全局记忆
        if self._global_memory:
            self._global_memory.close()
            self._global_memory = None

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {
            "working_memories": len(self._working_memories),
            "collaborative_memories": len(self._collaborative_memories),
            "has_global_memory": self._global_memory is not None
        }

        if self._global_memory:
            stats["global_memory_stats"] = self._global_memory.get_stats().model_dump()

        return stats


# 导出列表
__all__ = [
    # 类型和模型
    "MemoryType",
    "ContentType",
    "Page",
    "LightweightIndex",
    "MemoryEntry",
    "SearchQuery",
    "SearchResult",
    "MemoryStats",
    "MemoryConfig",

    # 基类
    "MemoryBase",
    "PageStoreBase",
    "RetrieverBase",
    "MemorizerBase",
    "ResearcherBase",

    # 核心实现
    "WorkingMemory",
    "CollaborativeMemory",
    "GlobalMemory",
    "PageStore",
    "Memorizer",
    "Researcher",

    # 检索器
    "VectorSearchRetriever",
    "BM25Retriever",
    "PageIDRetriever",

    # 管理器
    "MemoryManager",

    # 工具函数
    "segment_text",
    "extract_keywords",
    "generate_entry_id",
    "generate_page_id",
    "EmbeddingManager"
]
