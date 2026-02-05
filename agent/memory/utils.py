"""
Memory System Utilities

记忆系统的工具函数，包括：
- 文本分段和处理
- 时间戳和 ID 生成
- 哈希和序列化
- 嵌入向量处理
"""

import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Generator
import logging

logger = logging.getLogger(__name__)


# ==================== 文本处理 ====================

def segment_text(
    text: str,
    max_length: int = 2000,
    overlap: int = 200,
    separator: str = "\n\n"
) -> List[str]:
    """
    将长文本分割为多个段落

    Args:
        text: 输入文本
        max_length: 每段最大长度
        overlap: 段落间重叠长度
        separator: 优先分割位置

    Returns:
        文本段落列表
    """
    if len(text) <= max_length:
        return [text]

    segments = []
    current_pos = 0

    while current_pos < len(text):
        # 计算当前段落的结束位置
        end_pos = current_pos + max_length

        if end_pos >= len(text):
            segments.append(text[current_pos:])
            break

        # 尝试在分隔符处断开
        search_start = max(current_pos + max_length - overlap, current_pos)
        search_text = text[search_start:end_pos]

        # 优先在段落分隔符处断开
        split_pos = search_text.rfind(separator)
        if split_pos == -1:
            # 其次在句号处断开
            split_pos = search_text.rfind("。")
        if split_pos == -1:
            split_pos = search_text.rfind(". ")
        if split_pos == -1:
            # 最后在空格处断开
            split_pos = search_text.rfind(" ")
        if split_pos == -1:
            split_pos = len(search_text)

        actual_end = search_start + split_pos + len(separator)
        segments.append(text[current_pos:actual_end].strip())
        current_pos = actual_end - overlap

    return [s for s in segments if s.strip()]


def clean_text(text: str) -> str:
    """
    清理文本，移除多余空白和特殊字符

    Args:
        text: 输入文本

    Returns:
        清理后的文本
    """
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text)
    # 移除控制字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    从文本中提取关键词（简单实现）

    Args:
        text: 输入文本
        max_keywords: 最大关键词数量

    Returns:
        关键词列表
    """
    # 移除标点和特殊字符
    words = re.findall(r'\b\w+\b', text.lower())

    # 简单的停用词列表
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
        'who', 'whom', 'whose', 'when', 'where', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
        'just', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while',
        'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into',
        'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from',
        'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
        '的', '是', '在', '有', '和', '了', '不', '这', '那', '我', '你', '他',
        '她', '它', '我们', '你们', '他们', '什么', '哪', '谁', '怎么', '为什么',
    }

    # 过滤停用词和短词
    filtered = [w for w in words if w not in stopwords and len(w) > 2]

    # 统计词频
    word_freq = {}
    for word in filtered:
        word_freq[word] = word_freq.get(word, 0) + 1

    # 按词频排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, _ in sorted_words[:max_keywords]]


def compute_text_hash(text: str) -> str:
    """
    计算文本的 SHA256 哈希

    Args:
        text: 输入文本

    Returns:
        哈希字符串（前 16 位）
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


# ==================== ID 和时间 ====================

def generate_id(prefix: str = "") -> str:
    """
    生成唯一 ID

    Args:
        prefix: ID 前缀

    Returns:
        唯一 ID 字符串
    """
    uid = str(uuid.uuid4()).replace("-", "")[:12]
    return f"{prefix}_{uid}" if prefix else uid


def generate_page_id() -> str:
    """生成 Page ID"""
    return generate_id("pg")


def generate_entry_id() -> str:
    """生成 Entry ID"""
    return generate_id("me")


def get_timestamp() -> datetime:
    """获取当前时间戳"""
    return datetime.now()


def format_timestamp(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间戳"""
    return dt.strftime(format_str)


def parse_timestamp(ts_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """解析时间戳字符串"""
    try:
        return datetime.strptime(ts_str, format_str)
    except ValueError:
        # 尝试 ISO 格式
        return datetime.fromisoformat(ts_str)


# ==================== 序列化 ====================

def serialize_to_jsonl(items: List[Dict[str, Any]], file_path: Path) -> None:
    """
    将数据序列化为 JSONL 文件

    Args:
        items: 字典列表
        file_path: 输出文件路径
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        for item in items:
            json_str = json.dumps(item, ensure_ascii=False, default=str)
            f.write(json_str + '\n')


def deserialize_from_jsonl(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """
    从 JSONL 文件反序列化数据

    Args:
        file_path: 输入文件路径

    Yields:
        字典对象
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSONL line: {e}")


def append_to_jsonl(item: Dict[str, Any], file_path: Path) -> None:
    """
    追加数据到 JSONL 文件

    Args:
        item: 字典对象
        file_path: 文件路径
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'a', encoding='utf-8') as f:
        json_str = json.dumps(item, ensure_ascii=False, default=str)
        f.write(json_str + '\n')


def save_json(data: Dict[str, Any], file_path: Path) -> None:
    """保存 JSON 文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """加载 JSON 文件"""
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ==================== 嵌入向量 ====================

class EmbeddingManager:
    """嵌入向量管理器"""

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.dimension = 384

    def _load_model(self):
        """延迟加载嵌入模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded embedding model: {self.model_name}")
            except ImportError:
                logger.warning("sentence-transformers not installed, embedding disabled")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")

    def encode(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        编码文本为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表，或 None（如果模型不可用）
        """
        self._load_model()
        if self._model is None:
            return None

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            return None

    def encode_single(self, text: str) -> Optional[List[float]]:
        """编码单个文本"""
        result = self.encode([text])
        return result[0] if result else None

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算余弦相似度

    Args:
        vec1: 向量1
        vec2: 向量2

    Returns:
        相似度值 (0-1)
    """
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have the same dimension")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


# ==================== 过滤器 ====================

def apply_filters(items: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
    """
    应用过滤条件

    支持的操作符：
    - 直接值匹配
    - $in: 值在列表中
    - $contains: 列表包含值
    - $gt, $gte, $lt, $lte: 数值比较
    - $ne: 不等于

    Args:
        items: 数据列表
        filters: 过滤条件

    Returns:
        过滤后的数据列表
    """
    if not filters:
        return items

    result = []
    for item in items:
        if _match_filters(item, filters):
            result.append(item)
    return result


def _match_filters(item: Dict, filters: Dict[str, Any]) -> bool:
    """检查单个项目是否匹配过滤条件"""
    for key, condition in filters.items():
        value = item.get(key)

        if isinstance(condition, dict):
            # 复杂条件
            for op, op_value in condition.items():
                if op == "$in":
                    if value not in op_value:
                        return False
                elif op == "$contains":
                    if not isinstance(value, list):
                        return False
                    if not all(v in value for v in op_value):
                        return False
                elif op == "$gt":
                    if value is None or value <= op_value:
                        return False
                elif op == "$gte":
                    if value is None or value < op_value:
                        return False
                elif op == "$lt":
                    if value is None or value >= op_value:
                        return False
                elif op == "$lte":
                    if value is None or value > op_value:
                        return False
                elif op == "$ne":
                    if value == op_value:
                        return False
        else:
            # 简单值匹配
            if value != condition:
                return False

    return True


# ==================== 统计辅助 ====================

def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量（粗略估计）

    Args:
        text: 输入文本

    Returns:
        估算的 token 数量
    """
    # 粗略估计：英文约 4 字符/token，中文约 1.5 字符/token
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars

    return int(chinese_chars / 1.5 + other_chars / 4)


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
