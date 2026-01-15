"""
HttpRunner 测试引擎

基于 HttpRunner 框架的高级测试引擎。
支持复杂的测试场景、数据驱动和更强大的断言能力。
"""

import time
import json
import tempfile
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from httprunner import HttpRunner
    from httprunner.models import TestCase as HRTestCase
    HTTPRUNNER_AVAILABLE = True
except ImportError:
    HTTPRUNNER_AVAILABLE = False

from backend.common.test_models import (
    TestEngine,
    TestCase,
    TestResult,
    Response,
    Assertion,
    AssertionResult,
    AssertionType,
    AssertionOperator,
    TestCaseStatus
)
from backend.common.logger import Logger


class HttpRunnerEngine(TestEngine):
    """
    基于 HttpRunner 框架的测试引擎
    
    特性：
    - 支持复杂的测试场景和数据驱动
    - 支持变量提取和引用
    - 支持前置/后置操作
    - 支持测试用例依赖
    - 更强大的断言和验证能力
    - 详细的测试报告
    
    注意：需要安装 HttpRunner 包
    """
    
    def __init__(self):
        self.logger: Optional[Logger] = None
        self.runner: Optional[HttpRunner] = None
        self.config: Dict[str, Any] = {}
        self.initialized = False
        self.temp_dir: Optional[Path] = None
        self.variables: Dict[str, Any] = {}  # 共享变量池
    
    def initialize(self, config: Dict[str, Any]):
        """
        初始化引擎配置
        
        Args:
            config: 引擎配置，支持的键：
                - log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
                - failfast: 遇到失败时立即停止（默认 False）
                - save_tests: 保存生成的测试文件（默认 False）
                - report_dir: 报告保存目录（可选）
        """
        if not HTTPRUNNER_AVAILABLE:
            raise RuntimeError(
                "HttpRunner 未安装，请执行: pip install httprunner"
            )
        
        self.config = config
        
        # 初始化日志系统
        log_level = config.get("log_level", "INFO")
        self.logger = Logger(log_level=log_level, enable_file=False)
        
        # 创建临时目录用于存放测试文件
        self.temp_dir = Path(tempfile.mkdtemp(prefix="httprunner_"))
        
        # 初始化 HttpRunner
        self.runner = HttpRunner(
            failfast=config.get("failfast", False),
            save_tests=config.get("save_tests", False),
            report_dir=config.get("report_dir")
        )
        
        self.initialized = True
        
        self.logger.info(
            f"HttpRunnerEngine 初始化成功 | "
            f"日志级别: {log_level} (提醒：DEBUG < INFO < WARNING < ERROR) | "
            f"failfast: {config.get('failfast', False)} | "
            f"临时目录: {self.temp_dir}",
            engine="HttpRunnerEngine"
        )
    
    def execute_testcase(self, testcase: TestCase) -> TestResult:
        """
        执行单个测试用例
        
        Args:
            testcase: 测试用例对象
            
        Returns:
            测试结果对象
        """
        if not self.initialized:
            raise RuntimeError("引擎未初始化，请先调用 initialize()")
        
        start_time = time.time()
        test_result = TestResult(
            testcase_id=testcase.id,
            interface_name=testcase.interface_name,
            status=TestCaseStatus.RUNNING,
            duration=0.0,
            request_log={}
        )
        
        try:
            self.logger.info(
                f"开始执行测试用例 | "
                f"用例ID: {testcase.id} | "
                f"接口: {testcase.interface_name} | "
                f"方法: {testcase.request.method} | "
                f"URL: {testcase.request.url}",
                testcase_id=testcase.id,
                interface=testcase.interface_name
            )
            
            # 转换为 HttpRunner 格式
            hr_testcase = self._convert_to_httprunner_format(testcase)
            
            # 保存测试文件
            testcase_file = self.temp_dir / f"{testcase.id}.json"
            with open(testcase_file, "w", encoding="utf-8") as f:
                json.dump(hr_testcase, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(
                f"HttpRunner 测试文件已生成 | 路径: {testcase_file}",
                testcase_id=testcase.id
            )
            
            # 执行测试
            summary = self.runner.run(str(testcase_file))
            
            # 解析执行结果
            test_result = self._parse_httprunner_result(
                testcase,
                summary,
                test_result
            )
            
            # 清理临时文件（如果配置不保存）
            if not self.config.get("save_tests", False):
                testcase_file.unlink(missing_ok=True)
        
        except Exception as e:
            test_result.status = TestCaseStatus.ERROR
            test_result.error_message = f"执行异常: {str(e)}"
            self.logger.error(
                f"测试用例执行异常 | 用例ID: {testcase.id} | 错误: {str(e)}",
                testcase_id=testcase.id,
                error=str(e),
                exc_info=True
            )
        
        finally:
            test_result.duration = time.time() - start_time
        
        return test_result
    
    def _convert_to_httprunner_format(self, testcase: TestCase) -> Dict[str, Any]:
        """
        将测试用例转换为 HttpRunner 格式
        
        Args:
            testcase: 测试用例对象
            
        Returns:
            HttpRunner 格式的测试用例
        """
        # 构建请求部分
        request = {
            "method": testcase.request.method.upper(),
            "url": testcase.request.url,
        }
        
        if testcase.request.headers:
            request["headers"] = testcase.request.headers
        
        if testcase.request.query_params:
            request["params"] = testcase.request.query_params
        
        if testcase.request.body:
            if isinstance(testcase.request.body, dict):
                request["json"] = testcase.request.body
            else:
                request["data"] = testcase.request.body
        
        # 构建验证部分
        validate = []
        for assertion in testcase.assertions:
            validator = self._convert_assertion_to_validator(assertion)
            if validator:
                validate.append(validator)
        
        # 构建测试步骤
        test_step = {
            "name": testcase.interface_name,
            "request": request,
            "validate": validate
        }
        
        # 构建完整的测试用例
        hr_testcase = {
            "config": {
                "name": testcase.interface_name,
                "variables": self.variables.copy()
            },
            "teststeps": [test_step]
        }
        
        return hr_testcase
    
    def _convert_assertion_to_validator(
        self,
        assertion: Assertion
    ) -> Optional[Dict[str, Any]]:
        """
        将断言转换为 HttpRunner validator
        
        Args:
            assertion: 断言对象
            
        Returns:
            HttpRunner validator 格式
        """
        if assertion.type == AssertionType.STATUS_CODE:
            return {
                "eq": ["status_code", assertion.expected]
            }
        
        elif assertion.type == AssertionType.JSON_PATH:
            if not assertion.actual_path:
                return None
            
            # HttpRunner 使用 jmespath 语法
            check_field = f"body.{assertion.actual_path}"
            
            if assertion.operator == AssertionOperator.EQ:
                return {"eq": [check_field, assertion.expected]}
            elif assertion.operator == AssertionOperator.NE:
                return {"ne": [check_field, assertion.expected]}
            elif assertion.operator == AssertionOperator.GT:
                return {"gt": [check_field, assertion.expected]}
            elif assertion.operator == AssertionOperator.LT:
                return {"lt": [check_field, assertion.expected]}
            elif assertion.operator == AssertionOperator.GTE:
                return {"gte": [check_field, assertion.expected]}
            elif assertion.operator == AssertionOperator.LTE:
                return {"lte": [check_field, assertion.expected]}
            elif assertion.operator == AssertionOperator.IN:
                return {"contains": [check_field, assertion.expected]}
        
        elif assertion.type == AssertionType.CONTAINS:
            return {"contains": ["body", assertion.expected]}
        
        elif assertion.type == AssertionType.EQUALS:
            check_field = assertion.actual_path or "body"
            return {"eq": [check_field, assertion.expected]}
        
        elif assertion.type == AssertionType.REGEX:
            return {"regex_match": ["body", assertion.expected]}
        
        return None
    
    def _parse_httprunner_result(
        self,
        testcase: TestCase,
        summary: Dict[str, Any],
        test_result: TestResult
    ) -> TestResult:
        """
        解析 HttpRunner 执行结果
        
        Args:
            testcase: 原始测试用例
            summary: HttpRunner 执行摘要
            test_result: 测试结果对象（将被更新）
            
        Returns:
            更新后的测试结果
        """
        # 提取执行详情
        if summary.get("success", False):
            test_result.status = TestCaseStatus.PASSED
            self.logger.info(
                f"测试用例执行成功 | 用例ID: {testcase.id}",
                testcase_id=testcase.id,
                status="PASSED"
            )
        else:
            test_result.status = TestCaseStatus.FAILED
            test_result.error_message = "测试失败"
            self.logger.warning(
                f"测试用例执行失败 | 用例ID: {testcase.id}",
                testcase_id=testcase.id,
                status="FAILED"
            )
        
        # 提取请求/响应日志
        details = summary.get("details", [])
        if details:
            record = details[0].get("records", [{}])[0]
            
            # 请求日志
            req_data = record.get("meta_data", {}).get("request", {})
            test_result.request_log = {
                "method": req_data.get("method", testcase.request.method),
                "url": req_data.get("url", testcase.request.url),
                "headers": req_data.get("headers", {}),
                "body": req_data.get("body")
            }
            
            # 响应日志
            resp_data = record.get("meta_data", {}).get("response", {})
            test_result.response_log = {
                "status_code": resp_data.get("status_code"),
                "headers": resp_data.get("headers", {}),
                "body": resp_data.get("body"),
                "elapsed": resp_data.get("elapsed_ms", 0) / 1000.0
            }
            
            # 断言结果
            validators = record.get("validators", [])
            test_result.assertion_results = self._parse_validators(
                testcase.assertions,
                validators
            )
        
        return test_result
    
    def _parse_validators(
        self,
        assertions: List[Assertion],
        validators: List[Dict[str, Any]]
    ) -> List[AssertionResult]:
        """
        解析 HttpRunner 的 validator 结果
        
        Args:
            assertions: 原始断言列表
            validators: HttpRunner validator 结果
            
        Returns:
            断言结果列表
        """
        results = []
        
        # 尝试匹配断言和验证结果
        for i, assertion in enumerate(assertions):
            if i < len(validators):
                validator = validators[i]
                result = AssertionResult(
                    assertion=assertion,
                    passed=validator.get("check_result") == "pass",
                    actual_value=validator.get("check_value"),
                    error_message=validator.get("message") if validator.get("check_result") != "pass" else None
                )
            else:
                # 如果没有对应的验证结果，标记为错误
                result = AssertionResult(
                    assertion=assertion,
                    passed=False,
                    error_message="未找到对应的验证结果"
                )
            
            results.append(result)
        
        return results
    
    def validate_assertions(
        self,
        response: Response,
        assertions: List[Assertion]
    ) -> List[AssertionResult]:
        """
        执行断言验证
        
        注意：HttpRunner 引擎在 execute_testcase 中已经完成断言验证，
        此方法主要用于兼容接口，实际不会被单独调用。
        
        Args:
            response: HTTP 响应对象
            assertions: 断言规则列表
            
        Returns:
            断言结果列表
        """
        self.logger.warning(
            "HttpRunnerEngine 的断言验证已在 execute_testcase 中完成，"
            "不应单独调用 validate_assertions",
            engine="HttpRunnerEngine"
        )
        
        # 返回空结果列表
        return []
    
    def cleanup(self):
        """清理资源"""
        # 清理临时目录
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                self.logger.debug(
                    f"临时目录已清理 | 路径: {self.temp_dir}",
                    engine="HttpRunnerEngine"
                )
            except Exception as e:
                self.logger.warning(
                    f"清理临时目录失败 | 路径: {self.temp_dir} | 错误: {str(e)}",
                    engine="HttpRunnerEngine"
                )
        
        if self.logger:
            self.logger.info("HttpRunnerEngine 资源已清理", engine="HttpRunnerEngine")
        
        self.initialized = False
        self.runner = None
        self.variables.clear()
