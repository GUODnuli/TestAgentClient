"""
测试引擎抽象接口和数据模型

定义测试用例、测试结果等核心数据模型，以及测试引擎的抽象接口。
避免上下游强耦合，支持未来扩展自定义协议。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class AssertionType(str, Enum):
    """断言类型"""
    STATUS_CODE = "status_code"
    JSON_PATH = "json_path"
    REGEX = "regex"
    CONTAINS = "contains"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


class AssertionOperator(str, Enum):
    """比较运算符"""
    EQ = "eq"  # 等于
    NE = "ne"  # 不等于
    GT = "gt"  # 大于
    LT = "lt"  # 小于
    GTE = "gte"  # 大于等于
    LTE = "lte"  # 小于等于
    IN = "in"  # 包含
    NOT_IN = "not_in"  # 不包含


class TestCaseStatus(str, Enum):
    """测试用例状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class Assertion(BaseModel):
    """断言规则"""
    type: AssertionType
    expected: Any = Field(description="期望值")
    actual_path: Optional[str] = Field(None, description="实际值提取路径（JSON Path 或 XPath）")
    operator: AssertionOperator = Field(AssertionOperator.EQ, description="比较运算符")
    description: Optional[str] = Field(None, description="断言描述")


class Request(BaseModel):
    """HTTP 请求"""
    method: str = Field(description="HTTP 方法（GET/POST/PUT/DELETE/PATCH）")
    url: str = Field(description="请求URL")
    headers: Optional[Dict[str, str]] = Field(None, description="请求头")
    query_params: Optional[Dict[str, Any]] = Field(None, description="查询参数")
    body: Optional[Union[Dict[str, Any], str]] = Field(None, description="请求体")
    timeout: Optional[int] = Field(30, description="超时时间（秒）")


class Response(BaseModel):
    """HTTP 响应"""
    status_code: int = Field(description="HTTP 状态码")
    headers: Dict[str, str] = Field(description="响应头")
    body: Union[Dict[str, Any], str, bytes] = Field(description="响应体")
    elapsed: float = Field(description="耗时（秒）")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="响应时间")


class AssertionResult(BaseModel):
    """断言结果"""
    assertion: Assertion
    passed: bool = Field(description="是否通过")
    actual_value: Any = Field(None, description="实际值")
    error_message: Optional[str] = Field(None, description="错误信息")


class TestCase(BaseModel):
    """测试用例"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="用例唯一标识")
    interface_name: str = Field(description="接口名称")
    interface_path: str = Field(description="接口路径")
    request: Request = Field(description="请求对象")
    assertions: List[Assertion] = Field(default_factory=list, description="断言规则列表")
    priority: str = Field("medium", description="优先级（high/medium/low）")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    description: Optional[str] = Field(None, description="用例描述")
    dependencies: List[str] = Field(default_factory=list, description="依赖的前置用例ID")
    config: Dict[str, Any] = Field(default_factory=dict, description="引擎特定配置")


class TestResult(BaseModel):
    """测试结果"""
    testcase_id: str = Field(description="用例标识")
    interface_name: str = Field(description="接口名称")
    status: TestCaseStatus = Field(description="执行状态")
    duration: float = Field(description="执行耗时（秒）")
    request_log: Dict[str, Any] = Field(description="请求详情")
    response_log: Optional[Dict[str, Any]] = Field(None, description="响应详情")
    assertion_results: List[AssertionResult] = Field(default_factory=list, description="断言结果明细")
    error_message: Optional[str] = Field(None, description="错误信息")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="执行时间")


class TestEngine(ABC):
    """测试引擎抽象基类
    
    所有测试引擎必须实现此接口，以避免上下游强耦合。
    """
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]):
        """
        初始化引擎配置
        
        Args:
            config: 引擎配置
        """
        pass
    
    @abstractmethod
    def execute_testcase(self, testcase: TestCase) -> TestResult:
        """
        执行单个测试用例
        
        Args:
            testcase: 测试用例
            
        Returns:
            测试结果
        """
        pass
    
    @abstractmethod
    def validate_assertions(
        self,
        response: Response,
        assertions: List[Assertion]
    ) -> List[AssertionResult]:
        """
        执行断言验证
        
        Args:
            response: HTTP 响应
            assertions: 断言规则列表
            
        Returns:
            断言结果列表
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """清理资源"""
        pass


class ProtocolAdapter(ABC):
    """协议适配器抽象基类
    
    用于支持自定义协议扩展。
    """
    
    @abstractmethod
    def encode_request(self, abstract_request: Dict[str, Any]) -> bytes:
        """
        将抽象请求编码为协议报文
        
        Args:
            abstract_request: 抽象请求描述
            
        Returns:
            协议报文
        """
        pass
    
    @abstractmethod
    def send_request(self, protocol_request: bytes, target: str) -> bytes:
        """
        发送请求并接收响应
        
        Args:
            protocol_request: 协议报文
            target: 目标地址
            
        Returns:
            协议响应
        """
        pass
    
    @abstractmethod
    def decode_response(self, protocol_response: bytes) -> Dict[str, Any]:
        """
        将协议响应解码为抽象数据
        
        Args:
            protocol_response: 协议响应
            
        Returns:
            抽象响应数据
        """
        pass


class TestSuite(BaseModel):
    """测试套件"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="套件ID")
    name: str = Field(description="套件名称")
    testcases: List[TestCase] = Field(description="测试用例列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="套件配置")
    tags: List[str] = Field(default_factory=list, description="标签")


class TestReport(BaseModel):
    """测试报告"""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="报告ID")
    task_id: str = Field(description="关联任务ID")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="生成时间")
    
    # 测试摘要
    total_count: int = Field(0, description="总用例数")
    passed_count: int = Field(0, description="通过数")
    failed_count: int = Field(0, description="失败数")
    error_count: int = Field(0, description="错误数")
    skipped_count: int = Field(0, description="跳过数")
    pass_rate: float = Field(0.0, description="通过率（百分比）")
    total_duration: float = Field(0.0, description="总耗时（秒）")
    
    # 详细结果
    testcase_results: List[TestResult] = Field(default_factory=list, description="测试用例结果列表")
    
    # 性能统计
    slowest_testcases: List[Dict[str, Any]] = Field(default_factory=list, description="最慢用例 Top 10")
    
    # 错误模式
    error_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="错误模式分析")


# 工具函数

def create_simple_testcase(
    interface_name: str,
    method: str,
    url: str,
    expected_status: int = 200,
    **kwargs
) -> TestCase:
    """
    快速创建简单测试用例
    
    Args:
        interface_name: 接口名称
        method: HTTP 方法
        url: 请求URL
        expected_status: 期望状态码
        **kwargs: 其他参数
        
    Returns:
        测试用例对象
    """
    request = Request(
        method=method.upper(),
        url=url,
        headers=kwargs.get("headers"),
        query_params=kwargs.get("query_params"),
        body=kwargs.get("body")
    )
    
    assertions = [
        Assertion(
            type=AssertionType.STATUS_CODE,
            expected=expected_status,
            operator=AssertionOperator.EQ
        )
    ]
    
    return TestCase(
        interface_name=interface_name,
        interface_path=url,
        request=request,
        assertions=assertions,
        **{k: v for k, v in kwargs.items() if k in ["priority", "tags", "description"]}
    )


def calculate_pass_rate(passed: int, total: int) -> float:
    """
    计算通过率
    
    Args:
        passed: 通过数
        total: 总数
        
    Returns:
        通过率（百分比）
    """
    if total == 0:
        return 0.0
    return round((passed / total) * 100, 2)
