"""
记忆管理器

提供短期记忆（Working Memory）和长期记忆（Persistent Memory）管理。
用于克服 Dify 20k token 的上下文限制，实现跨任务知识复用。
"""

from typing import Any, Dict, List, Optional
from collections import OrderedDict
from datetime import datetime

from .logger import get_logger
from .vectordb import VectorDB, get_vector_db


class MemoryError(Exception):
    """记忆管理异常"""
    pass


class WorkingMemory:
    """短期记忆（Working Memory）
    
    缓存当前任务的即时上下文，生命周期与任务绑定。
    使用 LRU 策略管理容量。
    """
    
    def __init__(self, capacity: int = 50):
        """
        初始化短期记忆
        
        Args:
            capacity: 最大容量（条数）
        """
        self.capacity = capacity
        self.storage = OrderedDict()
        self.logger = get_logger()
        
        self.logger.debug(f"短期记忆初始化 | 容量: {capacity}")
    
    def add(self, key: str, value: Any):
        """
        添加记忆项
        
        Args:
            key: 记忆键
            value: 记忆值
        """
        # 如果键已存在，先删除（会更新到最新）
        if key in self.storage:
            del self.storage[key]
        
        # 添加新项
        self.storage[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        
        # 检查容量，LRU 淘汰
        if len(self.storage) > self.capacity:
            # 删除最旧的项（OrderedDict 保证顺序）
            oldest_key = next(iter(self.storage))
            del self.storage[oldest_key]
            self.logger.debug(f"短期记忆淘汰 | key: {oldest_key}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取记忆项
        
        Args:
            key: 记忆键
            
        Returns:
            记忆值，不存在则返回 None
        """
        if key in self.storage:
            # 移到末尾（标记为最近使用）
            self.storage.move_to_end(key)
            return self.storage[key]["value"]
        return None
    
    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的 N 条记忆
        
        Args:
            n: 数量
            
        Returns:
            记忆列表
        """
        items = list(self.storage.items())[-n:]
        return [
            {"key": k, "value": v["value"], "timestamp": v["timestamp"]}
            for k, v in items
        ]
    
    def clear(self):
        """清空短期记忆"""
        self.storage.clear()
        self.logger.debug("短期记忆已清空")
    
    def size(self) -> int:
        """获取当前记忆数量"""
        return len(self.storage)


class PersistentMemory:
    """长期记忆（Persistent Memory）
    
    持久化存储关键知识，支持跨任务检索与复用。
    基于向量数据库实现。
    """
    
    def __init__(self, vectordb: VectorDB):
        """
        初始化长期记忆
        
        Args:
            vectordb: 向量数据库实例
        """
        self.vectordb = vectordb
        self.logger = get_logger()
        
        self.logger.debug("长期记忆初始化")
    
    def store_interface(
        self,
        interface_name: str,
        interface_data: Dict[str, Any],
        task_id: str
    ) -> str:
        """
        存储接口知识
        
        Args:
            interface_name: 接口名称
            interface_data: 接口数据
            task_id: 任务 ID
            
        Returns:
            文档 ID
        """
        doc_id = self.vectordb.add_interface_knowledge(
            interface_name,
            interface_data,
            task_id
        )
        
        self.logger.debug(f"接口知识已存储 | interface: {interface_name}")
        return doc_id
    
    def store_testcase(
        self,
        testcase_id: str,
        testcase_data: Dict[str, Any],
        task_id: str
    ) -> str:
        """
        存储测试用例知识
        
        Args:
            testcase_id: 用例 ID
            testcase_data: 用例数据
            task_id: 任务 ID
            
        Returns:
            文档 ID
        """
        doc_id = self.vectordb.add_testcase_knowledge(
            testcase_id,
            testcase_data,
            task_id
        )
        
        self.logger.debug(f"测试用例知识已存储 | testcase: {testcase_id}")
        return doc_id
    
    def recall_similar_interfaces(
        self,
        query: str,
        top_k: int = 5,
        task_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        回忆相似接口
        
        Args:
            query: 查询文本
            top_k: 返回数量
            task_id: 按任务过滤（可选）
            
        Returns:
            相似接口列表
        """
        results = self.vectordb.search_similar_interfaces(
            query,
            top_k=top_k,
            task_id=task_id
        )
        
        # 转换为标准格式
        similar_interfaces = [
            {
                "document": doc,
                "similarity": sim,
                "metadata": meta
            }
            for doc, sim, meta in results
        ]
        
        self.logger.debug(f"相似接口回忆 | 查询: {query[:50]}... | 结果数: {len(similar_interfaces)}")
        return similar_interfaces
    
    def recall_similar_testcases(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        回忆相似测试用例
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            相似用例列表
        """
        results = self.vectordb.search_similar_testcases(
            query,
            top_k=top_k
        )
        
        similar_testcases = [
            {
                "document": doc,
                "similarity": sim,
                "metadata": meta
            }
            for doc, sim, meta in results
        ]
        
        self.logger.debug(f"相似用例回忆 | 查询: {query[:50]}... | 结果数: {len(similar_testcases)}")
        return similar_testcases


class MemoryManager:
    """记忆管理器
    
    协调短期记忆和长期记忆，提供统一的记忆访问接口。
    """
    
    def __init__(
        self,
        working_memory_capacity: int = 50,
        vectordb_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化记忆管理器
        
        Args:
            working_memory_capacity: 短期记忆容量
            vectordb_config: 向量数据库配置
        """
        self.logger = get_logger()
        
        # 初始化短期记忆
        self.working_memory = WorkingMemory(capacity=working_memory_capacity)
        
        # 初始化长期记忆
        if vectordb_config:
            vectordb = get_vector_db(vectordb_config)
        else:
            vectordb = get_vector_db()
        self.persistent_memory = PersistentMemory(vectordb)
        
        self.logger.info("记忆管理器初始化完成")
    
    def remember_current(self, key: str, value: Any):
        """
        记住当前上下文（短期记忆）
        
        Args:
            key: 记忆键
            value: 记忆值
        """
        self.working_memory.add(key, value)
    
    def recall_current(self, key: str) -> Optional[Any]:
        """
        回忆当前上下文（短期记忆）
        
        Args:
            key: 记忆键
            
        Returns:
            记忆值
        """
        return self.working_memory.get(key)
    
    def get_recent_context(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的上下文（短期记忆）
        
        Args:
            n: 数量
            
        Returns:
            最近的记忆列表
        """
        return self.working_memory.get_recent(n)
    
    def memorize_interface(
        self,
        interface_name: str,
        interface_data: Dict[str, Any],
        task_id: str
    ) -> str:
        """
        记住接口知识（长期记忆）
        
        Args:
            interface_name: 接口名称
            interface_data: 接口数据
            task_id: 任务 ID
            
        Returns:
            文档 ID
        """
        # 同时存储到短期记忆（当前任务可能会用到）
        self.remember_current(f"interface_{interface_name}", interface_data)
        
        # 存储到长期记忆
        return self.persistent_memory.store_interface(
            interface_name,
            interface_data,
            task_id
        )
    
    def memorize_testcase(
        self,
        testcase_id: str,
        testcase_data: Dict[str, Any],
        task_id: str
    ) -> str:
        """
        记住测试用例知识（长期记忆）
        
        Args:
            testcase_id: 用例 ID
            testcase_data: 用例数据
            task_id: 任务 ID
            
        Returns:
            文档 ID
        """
        # 同时存储到短期记忆
        self.remember_current(f"testcase_{testcase_id}", testcase_data)
        
        # 存储到长期记忆
        return self.persistent_memory.store_testcase(
            testcase_id,
            testcase_data,
            task_id
        )
    
    def recall_similar_interfaces(
        self,
        query: str,
        top_k: int = 5,
        task_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        回忆相似接口（长期记忆）
        
        用于上下文增强，突破 LLM 上下文限制。
        
        Args:
            query: 查询文本
            top_k: 返回数量
            task_id: 按任务过滤（可选）
            
        Returns:
            相似接口列表
        """
        return self.persistent_memory.recall_similar_interfaces(
            query,
            top_k=top_k,
            task_id=task_id
        )
    
    def recall_similar_testcases(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        回忆相似测试用例（长期记忆）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            相似用例列表
        """
        return self.persistent_memory.recall_similar_testcases(
            query,
            top_k=top_k
        )
    
    def build_enhanced_context(
        self,
        current_interface: str,
        max_context_items: int = 5
    ) -> str:
        """
        构建增强上下文
        
        从长期记忆中检索相关知识，拼接为增强上下文。
        用于注入 Dify API 请求，最大化利用 20k token 的有效容量。
        
        Args:
            current_interface: 当前处理的接口描述
            max_context_items: 最大上下文项数
            
        Returns:
            增强上下文文本
        """
        # 从长期记忆检索相关接口
        similar_interfaces = self.recall_similar_interfaces(
            current_interface,
            top_k=max_context_items
        )
        
        # 构建上下文文本
        context_parts = ["# 相关接口参考"]
        
        for item in similar_interfaces:
            context_parts.append(f"\n## 相似接口 (相似度: {item['similarity']:.2f})")
            context_parts.append(item['document'])
        
        enhanced_context = "\n".join(context_parts)
        
        self.logger.debug(
            f"增强上下文构建完成 | 相关项数: {len(similar_interfaces)} | "
            f"上下文长度: {len(enhanced_context)} 字符"
        )
        
        return enhanced_context
    
    def clear_working_memory(self):
        """清空短期记忆（任务结束时调用）"""
        self.working_memory.clear()
        self.logger.info("短期记忆已清空")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取记忆统计信息
        
        Returns:
            统计数据
        """
        vectordb_stats = self.persistent_memory.vectordb.get_statistics()
        
        return {
            "working_memory_size": self.working_memory.size(),
            "working_memory_capacity": self.working_memory.capacity,
            "persistent_memory": vectordb_stats
        }


# 全局记忆管理器实例
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(
    working_memory_capacity: int = 50,
    vectordb_config: Optional[Dict[str, Any]] = None
) -> MemoryManager:
    """
    获取全局记忆管理器实例（单例模式）
    
    Args:
        working_memory_capacity: 短期记忆容量
        vectordb_config: 向量数据库配置
        
    Returns:
        记忆管理器实例
    """
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = MemoryManager(
            working_memory_capacity=working_memory_capacity,
            vectordb_config=vectordb_config
        )
    
    return _memory_manager
