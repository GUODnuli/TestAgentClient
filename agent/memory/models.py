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


class GAMConfig(BaseModel):
    """GAM 记忆系统配置"""
    enabled: bool = True
    storage_path: str = "./storage/memory"

    # GAM 参数
    max_iterations: int = 3
    min_confidence: float = 0.7
    memo_max_length: int = 500
    page_max_length: int = 2000
    page_overlap: int = 200

    # 检索配置
    retrieval: Dict[str, Any] = Field(default_factory=lambda: {
        "default_top_k": 10,
        "vector_weight": 0.6,
        "bm25_weight": 0.4,
        "min_score_threshold": 0.3
    })

    # 嵌入模型配置
    embedding: Dict[str, Any] = Field(default_factory=lambda: {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dimension": 384,
        "batch_size": 32
    })


class SessionMemo(BaseModel):
    """
    GAM Session Memo - 轻量级会话摘要

    用于快速检索历史会话。由 GAMMemorizer 在 Worker 执行完成后
    通过 LLM 生成，包含会话的关键信息摘要。

    存储位置: LightweightIndex 中的 memo_store
    """
    model_config = ConfigDict(ser_json_timedelta='iso8601')

    # 标识
    session_id: str = Field(..., description="会话 ID，格式: plan_phase_worker")
    memo_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])

    # LLM 生成的内容
    session_memo: str = Field(..., description="LLM 生成的简洁摘要 (1-3 句话)")
    key_entities: List[str] = Field(default_factory=list, description="关键实体 (文件、函数、API等)")
    key_actions: List[str] = Field(default_factory=list, description="主要操作")
    outcome_summary: str = Field(default="", description="结果摘要: 完成了什么或学到了什么")

    # 元数据
    timestamp: datetime = Field(default_factory=datetime.now)
    plan_id: Optional[str] = None
    phase: Optional[int] = None
    worker: Optional[str] = None

    # 关联的 Page IDs
    page_ids: List[str] = Field(default_factory=list, description="关联的详细 Page 列表")

    # 向量嵌入 (用于语义检索)
    embedding: Optional[List[float]] = Field(default=None, description="memo 内容的向量嵌入")

    @field_serializer('timestamp')
    def serialize_datetime(self, v: datetime) -> str:
        return v.isoformat()

    def to_search_text(self) -> str:
        """转换为可搜索的文本"""
        parts = [self.session_memo]
        if self.key_entities:
            parts.append(f"Entities: {', '.join(self.key_entities)}")
        if self.key_actions:
            parts.append(f"Actions: {', '.join(self.key_actions)}")
        if self.outcome_summary:
            parts.append(f"Outcome: {self.outcome_summary}")
        return " | ".join(parts)


class PreconstructedMemory(BaseModel):
    """
    GAM 预构建记忆 - 在线阶段检索结果

    由 GAMResearcher 的 Deep-Research 循环生成，包含检索到的
    相关历史记忆和整合后的上下文，供 Worker 使用。
    """
    model_config = ConfigDict(ser_json_timedelta='iso8601')

    # 查询信息
    query: str = Field(..., description="原始查询/目标")

    # 检索结果
    retrieved_memos: List[SessionMemo] = Field(default_factory=list, description="检索到的 Session Memos")
    retrieved_pages: List[Page] = Field(default_factory=list, description="检索到的详细 Pages")

    # LLM 整合的上下文
    context_summary: str = Field(default="", description="LLM 整合的连贯上下文")

    # 搜索元数据
    search_strategy: Dict[str, Any] = Field(default_factory=dict, description="使用的搜索策略")
    iterations: int = Field(default=0, description="Deep-Research 迭代次数")

    # 评估结果
    is_sufficient: bool = Field(default=False, description="信息是否充分")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 (0.0-1.0)")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)

    @field_serializer('created_at')
    def serialize_datetime(self, v: datetime) -> str:
        return v.isoformat()

    def get_context_for_worker(self) -> Dict[str, Any]:
        """获取传递给 Worker 的上下文"""
        return {
            "gam_context": self.context_summary,
            "confidence": self.confidence_score,
            "retrieved_memo_count": len(self.retrieved_memos),
            "retrieved_page_count": len(self.retrieved_pages),
            "is_sufficient": self.is_sufficient,
            # 提取关键实体供 Worker 参考
            "key_entities": list(set(
                entity
                for memo in self.retrieved_memos
                for entity in memo.key_entities
            ))[:20],
            # 提取关键文件供 Worker 参考（避免重复读取）
            "processed_files": list(set(
                entity
                for memo in self.retrieved_memos
                for entity in memo.key_entities
                if entity.endswith(('.py', '.ts', '.js', '.json', '.yaml', '.yml', '.md'))
            ))[:50]
        }

    def has_relevant_context(self) -> bool:
        """检查是否有相关上下文"""
        return bool(self.retrieved_memos or self.retrieved_pages or self.context_summary)
