"""
Memory System Data Models

定义记忆系统中使用的所有数据模型，基于 Pydantic 实现数据验证。
参考 GAM (General Agentic Memory) 论文和 AgentScope Memory 设计。
"""

from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid


class MemoryType(str, Enum):
    """记忆类型枚举"""
    WORKING = "working"           # Layer 1: 工作记忆 (Worker-Scoped)
    COLLABORATIVE = "collaborative"  # Layer 2: 协作记忆 (Plan-Scoped)
    GLOBAL = "global"             # Layer 3: 全局记忆 (Persistent)


class ContentType(str, Enum):
    """内容类型枚举"""
    # 分析类
    FILE_ANALYSIS = "file_analysis"         # 文件分析结果
    CODE_ANALYSIS = "code_analysis"         # 代码分析结果
    API_EXTRACTION = "api_extraction"       # API 提取结果
    REQUIREMENT_ANALYSIS = "requirement_analysis"  # 需求分析

    # 执行类
    TASK_RESULT = "task_result"             # 任务执行结果
    TEST_CASES = "test_cases"               # 测试用例
    TEST_RESULT = "test_result"             # 测试结果
    TOOL_EXECUTION = "tool_execution"       # 工具执行记录

    # 知识类
    USER_PREFERENCE = "user_preference"     # 用户偏好
    PROJECT_KNOWLEDGE = "project_knowledge" # 项目知识
    ERROR_PATTERN = "error_pattern"         # 错误模式
    SUCCESS_PATTERN = "success_pattern"     # 成功模式

    # 通用
    CONVERSATION = "conversation"           # 对话记录
    SUMMARY = "summary"                     # 摘要
    RAW = "raw"                             # 原始数据


class Page(BaseModel):
    """
    GAM Page Store 中的单个页面

    Page 是记忆存储的基本单元，包含完整的对话片段或工作结果。
    采用 GAM 论文的设计，保留完整信息而非压缩摘要。
    """
    model_config = ConfigDict(ser_json_timedelta='iso8601')

    page_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = Field(..., description="页面内容（完整文本）")
    timestamp: datetime = Field(default_factory=datetime.now)
    context_tags: List[str] = Field(default_factory=list, description="上下文标签，便于检索")
    embedding: Optional[List[float]] = Field(default=None, description="向量嵌入")

    # 元数据
    source_type: Optional[ContentType] = None
    source_id: Optional[str] = None  # 关联的 entry_id
    plan_id: Optional[str] = None
    phase: Optional[int] = None
    worker: Optional[str] = None

    # 附加信息
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer('timestamp')
    def serialize_datetime(self, v: datetime) -> str:
        return v.isoformat()


class LightweightIndex(BaseModel):
    """
    轻量级索引

    GAM 论文核心设计：离线保持简单但有用的轻量级记忆 + 完整历史存储。
    此索引用于快速定位相关 Page，而非存储完整内容。
    """
    model_config = ConfigDict(ser_json_timedelta='iso8601')

    plan_id: str
    objective: str = Field(default="", description="Plan 目标描述")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Phase 摘要
    phases_summary: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="各 Phase 的简要信息，格式: {phase_num: {name, status, key_outputs}}"
    )

    # 搜索辅助
    searchable_tags: List[str] = Field(default_factory=list, description="可搜索的标签集合")
    key_entities: List[str] = Field(default_factory=list, description="关键实体列表")

    # 页面索引
    page_index: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="标签到 page_id 的映射，格式: {tag: [page_id1, page_id2]}"
    )

    # 统计信息
    total_pages: int = 0
    total_tokens_estimate: int = 0

    def add_page_reference(self, page: Page) -> None:
        """添加页面引用到索引"""
        for tag in page.context_tags:
            if tag not in self.page_index:
                self.page_index[tag] = []
            if page.page_id not in self.page_index[tag]:
                self.page_index[tag].append(page.page_id)

        # 更新标签集合
        self.searchable_tags = list(set(self.searchable_tags + page.context_tags))
        self.total_pages += 1
        self.updated_at = datetime.now()

    def get_pages_by_tag(self, tag: str) -> List[str]:
        """根据标签获取页面 ID 列表"""
        return self.page_index.get(tag, [])

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, v: datetime) -> str:
        return v.isoformat()


class MemoryEntry(BaseModel):
    """
    通用记忆条目

    这是三层记忆系统的统一数据格式，支持不同类型的记忆存储。
    """
    model_config = ConfigDict(ser_json_timedelta='iso8601')

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType
    content_type: ContentType

    # 来源信息
    plan_id: Optional[str] = None
    phase: Optional[int] = None
    worker: Optional[str] = None

    # 内容
    content: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None  # 内容摘要（用于快速预览）

    # 时间信息
    timestamp: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间（可选）

    # 检索辅助
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None

    # 关联信息
    related_entries: List[str] = Field(default_factory=list, description="关联的其他记忆 ID")
    source_files: List[str] = Field(default_factory=list, description="来源文件路径")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_page(self) -> Page:
        """转换为 Page 格式"""
        content_str = self.summary or str(self.content)
        # Store original content in metadata for later retrieval
        page_metadata = self.metadata.copy() if self.metadata else {}
        page_metadata["_original_content"] = self.content
        return Page(
            page_id=self.entry_id[:8],
            content=content_str,
            timestamp=self.timestamp,
            context_tags=self.tags,
            embedding=self.embedding,
            source_type=self.content_type,
            source_id=self.entry_id,
            plan_id=self.plan_id,
            phase=self.phase,
            worker=self.worker,
            metadata=page_metadata
        )

    @field_serializer('timestamp', 'expires_at')
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if v else None


class SearchQuery(BaseModel):
    """搜索查询参数"""
    query: str = Field(..., description="搜索查询文本")
    top_k: int = Field(default=5, ge=1, le=100)

    # 过滤条件
    memory_types: Optional[List[MemoryType]] = None
    content_types: Optional[List[ContentType]] = None
    plan_id: Optional[str] = None
    phase: Optional[int] = None
    phase_range: Optional[tuple] = None  # (min_phase, max_phase)
    worker: Optional[str] = None
    tags: Optional[List[str]] = None

    # 时间范围
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # 搜索选项
    use_vector: bool = True
    use_bm25: bool = True
    vector_weight: float = Field(default=0.7, ge=0, le=1)

    def to_filters(self) -> Dict[str, Any]:
        """转换为过滤器字典"""
        filters = {}
        if self.memory_types:
            filters["memory_type"] = {"$in": [t.value for t in self.memory_types]}
        if self.content_types:
            filters["content_type"] = {"$in": [t.value for t in self.content_types]}
        if self.plan_id:
            filters["plan_id"] = self.plan_id
        if self.phase is not None:
            filters["phase"] = self.phase
        if self.phase_range:
            filters["phase"] = {"$gte": self.phase_range[0], "$lte": self.phase_range[1]}
        if self.worker:
            filters["worker"] = self.worker
        if self.tags:
            filters["tags"] = {"$contains": self.tags}
        return filters


class SearchResult(BaseModel):
    """搜索结果"""
    entry: MemoryEntry
    score: float = Field(default=0.0, description="相关性得分")
    match_type: str = Field(default="hybrid", description="匹配类型: vector/bm25/hybrid")
    highlights: List[str] = Field(default_factory=list, description="匹配高亮片段")


class MemoryStats(BaseModel):
    """记忆统计信息"""
    memory_type: MemoryType
    total_entries: int = 0
    total_pages: int = 0
    total_size_bytes: int = 0
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None

    # 按类型统计
    entries_by_content_type: Dict[str, int] = Field(default_factory=dict)
    entries_by_phase: Dict[int, int] = Field(default_factory=dict)
    entries_by_worker: Dict[str, int] = Field(default_factory=dict)


class MemoryConfig(BaseModel):
    """记忆系统配置"""
    enabled: bool = True
    storage_path: str = "./storage/memory"

    # 各层配置
    working: Dict[str, Any] = Field(default_factory=lambda: {"enabled": True})
    collaborative: Dict[str, Any] = Field(default_factory=lambda: {
        "enabled": True,
        "auto_publish": True,
        "max_pages_per_plan": 1000
    })
    global_memory: Dict[str, Any] = Field(default_factory=lambda: {
        "enabled": True,
        "retention_days": 90,
        "max_entries": 10000
    })

    # 检索配置
    retrieval: Dict[str, Any] = Field(default_factory=lambda: {
        "default_top_k": 5,
        "vector_weight": 0.7,
        "bm25_weight": 0.3,
        "min_score_threshold": 0.3
    })

    # 嵌入模型配置
    embedding: Dict[str, Any] = Field(default_factory=lambda: {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dimension": 384,
        "batch_size": 32
    })
