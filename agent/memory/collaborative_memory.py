"""
Collaborative Memory (Layer 2)

协作记忆 - Plan 级别的共享记忆。
用于解决多 Worker 协作时的信息共享问题，避免重复读取文件。
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import MemoryBase
from .models import (
    MemoryEntry,
    MemoryType,
    ContentType,
    SearchResult,
    MemoryStats,
    Page,
    LightweightIndex
)
from .page_store import PageStore
from .utils import (
    generate_entry_id,
    extract_keywords,
    save_json,
    load_json
)

logger = logging.getLogger(__name__)


class CollaborativeMemory(MemoryBase):
    """
    协作记忆 (Layer 2: Plan-Scoped)

    核心功能：
    - 存储 Phase 间共享的工作结果
    - 解决 Worker 重复读文件问题
    - 支持语义检索和标签检索

    存储结构：
    storage/memory/plans/{plan_id}/
    ├── pages.jsonl          # 完整页面数据
    ├── index.json           # 轻量级索引
    ├── chroma/              # 向量数据库
    └── phases/              # 按 Phase 组织的输出
        ├── phase_1.json
        ├── phase_2.json
        └── ...

    使用流程：
    1. Phase 1 Worker 完成后，将关键结果写入协作记忆
    2. Phase 2 Worker 启动时，Coordinator 从协作记忆中提取相关上下文
    3. Phase 2 Worker 无需重新读取原始文件
    """

    def __init__(
        self,
        plan_id: str,
        storage_path: str,
        objective: str = "",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(MemoryType.COLLABORATIVE, config)
        self.plan_id = plan_id
        self.storage_path = Path(storage_path) / "plans" / plan_id
        self.objective = objective

        # Page Store
        self.page_store: Optional[PageStore] = None

        # Phase 输出缓存
        self._phase_outputs: Dict[int, Dict[str, Any]] = {}

        # 元数据
        self._metadata_file = self.storage_path / "metadata.json"
        self._phases_dir = self.storage_path / "phases"

    def initialize(self) -> None:
        """初始化协作记忆"""
        # 创建目录
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._phases_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 Page Store
        self.page_store = PageStore(
            storage_path=self.storage_path,
            plan_id=self.plan_id,
            config=self.config
        )
        self.page_store.initialize()

        # 设置索引目标
        if self.page_store.index:
            self.page_store.index.objective = self.objective

        # 加载已有的 Phase 输出
        self._load_phase_outputs()

        # 保存元数据
        self._save_metadata()

        self._initialized = True
        logger.info(f"CollaborativeMemory initialized for plan: {self.plan_id}")

    def _save_metadata(self) -> None:
        """保存元数据"""
        metadata = {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "created_at": datetime.now().isoformat(),
            "phases": list(self._phase_outputs.keys())
        }
        save_json(metadata, self._metadata_file)

    def _load_phase_outputs(self) -> None:
        """加载已有的 Phase 输出"""
        if not self._phases_dir.exists():
            return

        for phase_file in self._phases_dir.glob("phase_*.json"):
            try:
                phase_num = int(phase_file.stem.split("_")[1])
                data = load_json(phase_file)
                if data:
                    self._phase_outputs[phase_num] = data
            except Exception as e:
                logger.warning(f"Failed to load phase file {phase_file}: {e}")

    # ==================== 核心接口 ====================

    def add(self, entry: MemoryEntry) -> str:
        """添加记忆条目"""
        if not entry.entry_id:
            entry.entry_id = generate_entry_id()

        entry.memory_type = MemoryType.COLLABORATIVE
        entry.plan_id = self.plan_id

        # 自动生成标签
        if not entry.tags:
            content_str = entry.summary or str(entry.content)
            entry.tags = extract_keywords(content_str, max_keywords=8)

        # 转换为 Page 并存储
        page = entry.to_page()
        self.page_store.add_page(page)

        logger.debug(f"Added entry to collaborative memory: {entry.entry_id}")
        return entry.entry_id

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        page = self.page_store.get_page(entry_id[:8])
        if page:
            return self._page_to_entry(page)
        return None

    def _page_to_entry(self, page: Page) -> MemoryEntry:
        """将 Page 转换为 MemoryEntry"""
        # Retrieve original content from metadata if available
        original_content = page.metadata.get("_original_content") if page.metadata else None
        content = original_content if original_content is not None else {"text": page.content}

        # Filter out internal metadata keys
        clean_metadata = {k: v for k, v in (page.metadata or {}).items() if not k.startswith("_")}

        return MemoryEntry(
            entry_id=page.source_id or page.page_id,
            memory_type=MemoryType.COLLABORATIVE,
            content_type=page.source_type or ContentType.RAW,
            plan_id=page.plan_id,
            phase=page.phase,
            worker=page.worker,
            content=content,
            timestamp=page.timestamp,
            tags=page.context_tags,
            embedding=page.embedding,
            metadata=clean_metadata
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """搜索协作记忆"""
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
        """清空协作记忆"""
        self.page_store.clear()
        self._phase_outputs.clear()

        # 删除 Phase 文件
        for phase_file in self._phases_dir.glob("phase_*.json"):
            phase_file.unlink()

    def export(self) -> Dict[str, Any]:
        """导出协作记忆"""
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "phase_outputs": self._phase_outputs,
            "page_store": self.page_store.export() if self.page_store else None
        }

    def load(self, data: Dict[str, Any]) -> None:
        """加载协作记忆"""
        self.plan_id = data.get("plan_id", self.plan_id)
        self.objective = data.get("objective", self.objective)
        self._phase_outputs = data.get("phase_outputs", {})

    # ==================== Phase 输出管理 ====================

    def publish_phase_output(
        self,
        phase: int,
        worker: str,
        output_type: ContentType,
        content: Dict[str, Any],
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None
    ) -> str:
        """
        发布 Phase 输出到协作记忆

        这是解决 "Worker 重复读文件" 问题的核心方法。
        Phase 完成时调用此方法，后续 Phase 可直接获取结果。

        Args:
            phase: Phase 编号
            worker: Worker 名称
            output_type: 输出类型
            content: 输出内容
            tags: 标签列表
            summary: 内容摘要

        Returns:
            entry_id
        """
        entry = MemoryEntry(
            entry_id=f"{self.plan_id}_p{phase}_{output_type.value}_{worker}",
            memory_type=MemoryType.COLLABORATIVE,
            content_type=output_type,
            plan_id=self.plan_id,
            phase=phase,
            worker=worker,
            content=content,
            summary=summary or self._generate_summary(content),
            tags=tags or [],
            timestamp=datetime.now()
        )

        # 添加到 Page Store
        entry_id = self.add(entry)

        # 更新 Phase 输出缓存
        if phase not in self._phase_outputs:
            self._phase_outputs[phase] = {
                "phase": phase,
                "outputs": [],
                "timestamp": datetime.now().isoformat()
            }

        self._phase_outputs[phase]["outputs"].append({
            "entry_id": entry_id,
            "worker": worker,
            "output_type": output_type.value,
            "tags": entry.tags,
            "summary": entry.summary
        })

        # 保存 Phase 文件
        self._save_phase_output(phase)

        # 更新索引
        if self.page_store.index:
            if phase not in self.page_store.index.phases_summary:
                self.page_store.index.phases_summary[str(phase)] = {
                    "name": f"Phase {phase}",
                    "status": "completed",
                    "key_outputs": []
                }
            self.page_store.index.phases_summary[str(phase)]["key_outputs"].append(
                output_type.value
            )

        logger.info(f"Published phase {phase} output: {output_type.value} from {worker}")
        return entry_id

    def _generate_summary(self, content: Dict[str, Any]) -> str:
        """生成内容摘要"""
        if isinstance(content, dict):
            # 尝试提取常见的摘要字段
            for key in ["summary", "description", "result", "output"]:
                if key in content:
                    val = content[key]
                    if isinstance(val, str):
                        return val[:500] if len(val) > 500 else val

            # 如果没有摘要字段，序列化前几个键
            keys = list(content.keys())[:5]
            return f"Contains: {', '.join(keys)}"

        return str(content)[:500]

    def _save_phase_output(self, phase: int) -> None:
        """保存 Phase 输出到文件"""
        phase_file = self._phases_dir / f"phase_{phase}.json"
        save_json(self._phase_outputs[phase], phase_file)

    # ==================== 上下文获取（供后续 Phase 使用）====================

    def get_context_for_phase(
        self,
        phase: int,
        query: Optional[str] = None,
        include_all_previous: bool = True
    ) -> Dict[str, Any]:
        """
        为新 Phase 获取上下文

        这是后续 Phase 避免重复读文件的关键方法。

        Args:
            phase: 当前 Phase 编号
            query: 可选的查询，用于相关性检索
            include_all_previous: 是否包含所有前序 Phase 的输出

        Returns:
            上下文字典，包含：
            - previous_outputs: 前序 Phase 的完整输出（包含实际内容）
            - relevant_content: 与查询相关的详细内容
            - available_data: 可用数据类型列表
        """
        context = {
            "plan_id": self.plan_id,
            "current_phase": phase,
            "previous_outputs": {},
            "relevant_content": [],
            "available_data": []
        }

        # 获取前序 Phase 的输出（包含完整内容）
        for prev_phase in range(1, phase):
            if prev_phase in self._phase_outputs:
                phase_data = self._phase_outputs[prev_phase]
                outputs_with_content = []

                for o in phase_data.get("outputs", []):
                    output_entry = {
                        "type": o["output_type"],
                        "worker": o["worker"],
                        "summary": o["summary"],
                        "entry_id": o["entry_id"]
                    }

                    # 获取完整内容
                    entry_id = o.get("entry_id", "")
                    if entry_id:
                        entry = self.get(entry_id)
                        if entry:
                            output_entry["content"] = entry.content

                    outputs_with_content.append(output_entry)

                context["previous_outputs"][prev_phase] = {
                    "outputs": outputs_with_content
                }

                # 收集可用数据类型
                for output in phase_data.get("outputs", []):
                    if output["output_type"] not in context["available_data"]:
                        context["available_data"].append(output["output_type"])

        # 如果有查询，进行相关性检索
        if query:
            # 只检索前序 Phase 的内容
            filters = {"phase": {"$lt": phase}} if phase > 1 else None
            search_results = self.search(query, top_k=5, filters=filters)

            for result in search_results:
                context["relevant_content"].append({
                    "entry_id": result.entry.entry_id,
                    "content_type": result.entry.content_type.value,
                    "content": result.entry.content,
                    "score": result.score,
                    "phase": result.entry.phase,
                    "worker": result.entry.worker
                })

        return context

    def get_phase_output(self, phase: int) -> Optional[Dict[str, Any]]:
        """获取指定 Phase 的完整输出"""
        return self._phase_outputs.get(phase)

    def get_output_by_type(
        self,
        content_type: ContentType,
        phase: Optional[int] = None
    ) -> List[MemoryEntry]:
        """
        按类型获取输出

        Args:
            content_type: 内容类型
            phase: 可选的 Phase 过滤

        Returns:
            记忆条目列表
        """
        results = []

        for page in self.page_store.iter_pages():
            if page.source_type == content_type:
                if phase is None or page.phase == phase:
                    results.append(self._page_to_entry(page))

        return results

    def get_file_analysis_results(self, phase: Optional[int] = None) -> List[Dict]:
        """获取文件分析结果（常用快捷方法）"""
        entries = self.get_output_by_type(ContentType.FILE_ANALYSIS, phase)
        return [e.content for e in entries]

    def get_api_extractions(self, phase: Optional[int] = None) -> List[Dict]:
        """获取 API 提取结果（常用快捷方法）"""
        entries = self.get_output_by_type(ContentType.API_EXTRACTION, phase)
        return [e.content for e in entries]

    def get_test_cases(self, phase: Optional[int] = None) -> List[Dict]:
        """获取测试用例（常用快捷方法）"""
        entries = self.get_output_by_type(ContentType.TEST_CASES, phase)
        return [e.content for e in entries]

    # ==================== 统计和信息 ====================

    def get_stats(self) -> MemoryStats:
        """获取统计信息"""
        stats = MemoryStats(memory_type=MemoryType.COLLABORATIVE)

        if self.page_store:
            page_stats = self.page_store.get_stats()
            stats.total_pages = page_stats["total_pages"]
            stats.total_entries = stats.total_pages

        # 按 Phase 统计
        for phase, data in self._phase_outputs.items():
            stats.entries_by_phase[phase] = len(data.get("outputs", []))

        return stats

    def get_summary(self) -> Dict[str, Any]:
        """获取协作记忆摘要"""
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "total_phases": len(self._phase_outputs),
            "phases": {
                phase: {
                    "output_count": len(data.get("outputs", [])),
                    "output_types": [o["output_type"] for o in data.get("outputs", [])]
                }
                for phase, data in self._phase_outputs.items()
            },
            "stats": self.page_store.get_stats() if self.page_store else {}
        }

    def close(self) -> None:
        """关闭协作记忆"""
        if self.page_store:
            self.page_store.close()
        self._save_metadata()
        logger.info(f"CollaborativeMemory closed for plan: {self.plan_id}")
