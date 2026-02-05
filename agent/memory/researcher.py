"""
GAM Researcher Component

基于 GAM 论文的 Researcher 组件实现。
负责在线深度检索和上下文构建。

职责：
1. 分析用户查询，规划搜索策略
2. 使用三种工具进行深度检索
3. 迭代验证和反思搜索结果
4. 整合信息构建优化上下文
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import ResearcherBase, RetrieverBase, PageStoreBase
from .models import Page, SearchQuery
from .retrieval import VectorSearchRetriever, BM25Retriever, PageIDRetriever

logger = logging.getLogger(__name__)


class Researcher(ResearcherBase):
    """
    GAM Researcher 组件

    运行时机: 仅在收到特定请求时激活

    深度研究流程：
    1. 查询分析 - 理解用户意图
    2. 策略规划 - 决定搜索方法
    3. 多工具检索 - 向量 + BM25 + Page-ID
    4. 结果验证 - 检查信息充分性
    5. 反思调整 - 调整搜索策略（如不充分）
    6. 上下文整合 - 构建最终响应上下文
    """

    def __init__(
        self,
        page_store: PageStoreBase,
        retrievers: Optional[List[RetrieverBase]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        # 初始化默认检索器
        if retrievers is None:
            retrievers = [
                VectorSearchRetriever(config),
                BM25Retriever(config),
                PageIDRetriever(page_store, config)
            ]

        super().__init__(page_store, retrievers, config)

        # 配置
        self.max_iterations = config.get("max_iterations", 3) if config else 3
        self.min_results = config.get("min_results", 3) if config else 3
        self.min_score_threshold = config.get("min_score_threshold", 0.3) if config else 0.3

        # LLM 接口（用于智能分析，可选）
        self._llm = None

        # 研究历史
        self._research_history: List[Dict[str, Any]] = []

    def set_llm(self, llm) -> None:
        """设置 LLM 接口"""
        self._llm = llm

    def research(
        self,
        query: str,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行深度研究

        Args:
            query: 研究查询
            max_iterations: 最大迭代次数

        Returns:
            研究结果，包含：
            - context: 整合的上下文
            - sources: 来源页面列表
            - strategy: 使用的搜索策略
            - iterations: 迭代次数
        """
        max_iterations = max_iterations or self.max_iterations

        # 记录开始
        research_record = {
            "query": query,
            "start_time": datetime.now().isoformat(),
            "iterations": [],
            "final_results": []
        }

        # 1. 规划搜索策略
        strategy = self.plan_search_strategy(query)
        research_record["strategy"] = strategy

        all_pages: List[Page] = []
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            iteration_record = {
                "iteration": iteration,
                "strategy": strategy.copy(),
                "results_count": 0
            }

            # 2. 执行多工具检索
            new_pages = self._execute_search(query, strategy)
            iteration_record["results_count"] = len(new_pages)

            # 合并结果（去重）
            existing_ids = {p.page_id for p in all_pages}
            for page in new_pages:
                if page.page_id not in existing_ids:
                    all_pages.append(page)
                    existing_ids.add(page.page_id)

            # 3. 验证结果
            is_sufficient, feedback = self.validate_results(query, all_pages)
            iteration_record["is_sufficient"] = is_sufficient
            iteration_record["feedback"] = feedback

            research_record["iterations"].append(iteration_record)

            if is_sufficient:
                break

            # 4. 反思并调整策略
            strategy = self._refine_strategy(strategy, feedback, all_pages)

        # 5. 整合上下文
        context = self.integrate_context(all_pages, query)

        # 记录结果
        research_record["final_results"] = [p.page_id for p in all_pages]
        research_record["end_time"] = datetime.now().isoformat()
        self._research_history.append(research_record)

        return {
            "context": context,
            "sources": all_pages,
            "strategy": strategy,
            "iterations": iteration,
            "total_pages": len(all_pages)
        }

    def plan_search_strategy(self, query: str) -> Dict[str, Any]:
        """
        规划搜索策略

        分析查询特点，决定使用哪些检索器及其参数。
        """
        strategy = {
            "use_vector": True,
            "use_bm25": True,
            "use_page_id": False,
            "vector_weight": 0.5,
            "bm25_weight": 0.5,
            "top_k": 10,
            "query_type": "general"
        }

        # 分析查询特点
        query_lower = query.lower()

        # 检测精确查询（包含引号或特定术语）
        if '"' in query or "'" in query:
            strategy["use_bm25"] = True
            strategy["bm25_weight"] = 0.7
            strategy["vector_weight"] = 0.3
            strategy["query_type"] = "exact"

        # 检测概念性查询
        concept_words = ["what", "why", "how", "explain", "describe", "什么", "为什么", "如何", "解释"]
        if any(word in query_lower for word in concept_words):
            strategy["use_vector"] = True
            strategy["vector_weight"] = 0.7
            strategy["bm25_weight"] = 0.3
            strategy["query_type"] = "conceptual"

        # 检测 ID 引用
        if "page_id:" in query_lower or "id:" in query_lower:
            strategy["use_page_id"] = True
            strategy["query_type"] = "page_reference"

        # 如果有 LLM，使用 LLM 优化策略
        if self._llm:
            strategy = self._llm_plan_strategy(query, strategy)

        return strategy

    def _llm_plan_strategy(self, query: str, base_strategy: Dict) -> Dict:
        """使用 LLM 优化搜索策略"""
        try:
            prompt = f"""分析以下查询，优化搜索策略：

查询: {query}

当前策略:
- 使用向量搜索: {base_strategy['use_vector']}
- 使用BM25搜索: {base_strategy['use_bm25']}
- 向量权重: {base_strategy['vector_weight']}
- BM25权重: {base_strategy['bm25_weight']}

请判断这是什么类型的查询（精确/概念/混合），并建议权重调整。
只返回JSON格式的建议。"""

            # 这里简化处理，实际应解析 LLM 返回
            return base_strategy
        except Exception as e:
            logger.warning(f"LLM strategy planning failed: {e}")
            return base_strategy

    def _execute_search(
        self,
        query: str,
        strategy: Dict[str, Any]
    ) -> List[Page]:
        """执行多工具检索"""
        all_results: Dict[str, float] = {}  # page_id -> score
        top_k = strategy.get("top_k", 10)

        # 获取所有页面内容
        pages_list = list(self.page_store.iter_pages())
        if not pages_list:
            return []

        documents = [p.content for p in pages_list]
        page_id_map = {i: p for i, p in enumerate(pages_list)}

        # 向量搜索
        if strategy.get("use_vector") and "vector_search" in self.retrievers:
            vector_retriever = self.retrievers["vector_search"]
            vector_retriever.index_documents(documents)
            vector_results = vector_retriever.search(query, top_k=top_k)

            vector_weight = strategy.get("vector_weight", 0.5)
            for idx, score in vector_results:
                page_id = pages_list[idx].page_id
                all_results[page_id] = all_results.get(page_id, 0) + score * vector_weight

        # BM25 搜索
        if strategy.get("use_bm25") and "bm25_search" in self.retrievers:
            bm25_retriever = self.retrievers["bm25_search"]
            bm25_retriever.index_documents(documents)
            bm25_results = bm25_retriever.search(query, top_k=top_k)

            bm25_weight = strategy.get("bm25_weight", 0.5)
            for idx, score in bm25_results:
                page_id = pages_list[idx].page_id
                # 归一化 BM25 得分
                normalized_score = min(score / 10.0, 1.0)
                all_results[page_id] = all_results.get(page_id, 0) + normalized_score * bm25_weight

        # Page-ID 搜索
        if strategy.get("use_page_id") and "page_id_search" in self.retrievers:
            # 从查询中提取 page_id
            import re
            page_ids = re.findall(r'(?:page_id:|id:)\s*(\w+)', query, re.IGNORECASE)
            for page_id in page_ids:
                page = self.page_store.get_page(page_id)
                if page:
                    all_results[page_id] = 1.0  # 直接引用得分最高

        # 按得分排序并返回页面
        sorted_results = sorted(all_results.items(), key=lambda x: x[1], reverse=True)

        result_pages = []
        for page_id, score in sorted_results[:top_k]:
            if score >= self.min_score_threshold:
                page = self.page_store.get_page(page_id)
                if page:
                    result_pages.append(page)

        return result_pages

    def validate_results(
        self,
        query: str,
        results: List[Page]
    ) -> tuple:
        """
        验证搜索结果

        检查结果是否充分回答查询。
        """
        # 基本数量检查
        if len(results) < self.min_results:
            return False, f"结果数量不足（{len(results)} < {self.min_results}）"

        # 检查结果相关性（简单启发式）
        query_terms = set(query.lower().split())
        relevant_count = 0

        for page in results:
            content_lower = page.content.lower()
            matches = sum(1 for term in query_terms if term in content_lower)
            if matches >= len(query_terms) * 0.3:
                relevant_count += 1

        if relevant_count < self.min_results:
            return False, f"相关结果不足（{relevant_count} < {self.min_results}）"

        # 如果有 LLM，使用 LLM 验证
        if self._llm:
            return self._llm_validate(query, results)

        return True, "结果验证通过"

    def _llm_validate(self, query: str, results: List[Page]) -> tuple:
        """使用 LLM 验证结果"""
        try:
            context = "\n\n".join([p.content[:500] for p in results[:5]])
            prompt = f"""判断以下搜索结果是否能充分回答查询：

查询: {query}

搜索结果摘要:
{context}

请回答：
1. 结果是否充分？(是/否)
2. 如果不充分，缺少什么信息？"""

            # 简化处理
            return True, "结果验证通过"
        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
            return True, "验证跳过（LLM 不可用）"

    def _refine_strategy(
        self,
        current_strategy: Dict[str, Any],
        feedback: str,
        current_results: List[Page]
    ) -> Dict[str, Any]:
        """
        反思并调整搜索策略

        根据反馈调整检索参数。
        """
        new_strategy = current_strategy.copy()

        # 如果结果不足，扩大搜索范围
        if "不足" in feedback:
            new_strategy["top_k"] = min(new_strategy.get("top_k", 10) * 2, 50)

        # 如果相关性低，调整权重
        if "相关" in feedback:
            # 增加 BM25 权重以获取更精确的匹配
            new_strategy["bm25_weight"] = min(new_strategy.get("bm25_weight", 0.5) + 0.1, 0.8)
            new_strategy["vector_weight"] = 1 - new_strategy["bm25_weight"]

        return new_strategy

    def integrate_context(self, pages: List[Page], query: str) -> str:
        """
        整合上下文

        将多个页面的内容整合为连贯的上下文。
        """
        if not pages:
            return "未找到相关信息。"

        # 按相关性和时间排序
        # 这里简化为按时间倒序
        sorted_pages = sorted(pages, key=lambda p: p.timestamp, reverse=True)

        # 构建上下文
        context_parts = []

        # 添加查询信息
        context_parts.append(f"## 查询: {query}\n")
        context_parts.append(f"## 找到 {len(pages)} 个相关结果\n")

        # 添加页面内容
        for i, page in enumerate(sorted_pages[:10]):  # 限制最多 10 个
            part = f"""
### 来源 {i + 1} (ID: {page.page_id})
- 时间: {page.timestamp.strftime('%Y-%m-%d %H:%M')}
- 标签: {', '.join(page.context_tags[:5])}
{'-' * 40}
{page.content[:1500]}
{'...(内容已截断)' if len(page.content) > 1500 else ''}
"""
            context_parts.append(part)

        return "\n".join(context_parts)

    def quick_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Page]:
        """
        快速搜索（不进行深度研究）

        Args:
            query: 查询文本
            top_k: 返回数量

        Returns:
            页面列表
        """
        strategy = {
            "use_vector": True,
            "use_bm25": True,
            "use_page_id": False,
            "vector_weight": 0.5,
            "bm25_weight": 0.5,
            "top_k": top_k
        }

        return self._execute_search(query, strategy)

    def get_research_history(self) -> List[Dict[str, Any]]:
        """获取研究历史"""
        return self._research_history.copy()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_iterations = sum(
            len(r.get("iterations", []))
            for r in self._research_history
        )

        return {
            "total_researches": len(self._research_history),
            "total_iterations": total_iterations,
            "avg_iterations_per_research": (
                total_iterations / len(self._research_history)
                if self._research_history else 0
            ),
            "retrievers": list(self.retrievers.keys())
        }
