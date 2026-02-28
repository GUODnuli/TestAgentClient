# -*- coding: utf-8 -*-
"""
测试执行工具集

提供 API 响应验证和性能指标采集功能。
HTTP 请求执行由 MCP `http_client_tools` 工具组（http_request）承担。
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

# 导入项目模块
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.test_models import (
    Response,
    Assertion,
    AssertionType,
    AssertionOperator,
)
from common.engines.requests_engine import RequestsEngine


def _parse_assertion(assertion_dict: Dict[str, Any]) -> Optional[Assertion]:
    """解析断言字典为 Assertion 对象"""
    try:
        operator_mapping = {
            "equals": "eq", "equal": "eq", "eq": "eq",
            "not_equals": "ne", "not_equal": "ne", "ne": "ne",
            "greater_than": "gt", "greater": "gt", "gt": "gt",
            "less_than": "lt", "less": "lt", "lt": "lt",
            "gte": "gte", "lte": "lte",
            "in": "in", "contains": "in", "not_in": "not_in",
        }
        type_mapping = {
            "status_code": AssertionType.STATUS_CODE,
            "statuscode": AssertionType.STATUS_CODE,
            "status": AssertionType.STATUS_CODE,
            "json_path": AssertionType.JSON_PATH,
            "jsonpath": AssertionType.JSON_PATH,
            "regex": AssertionType.REGEX,
            "contains": AssertionType.CONTAINS,
            "equals": AssertionType.EQUALS,
            "equal": AssertionType.EQUALS,
            "not_equals": AssertionType.NOT_EQUALS,
            "greater_than": AssertionType.GREATER_THAN,
            "less_than": AssertionType.LESS_THAN,
        }
        assertion_type_str = assertion_dict.get("type", "status_code").lower()
        assertion_type = type_mapping.get(assertion_type_str, AssertionType.STATUS_CODE)
        operator_str = assertion_dict.get("operator", "eq").lower()
        operator = AssertionOperator(operator_mapping.get(operator_str, "eq"))
        return Assertion(
            type=assertion_type,
            expected=assertion_dict.get("expected"),
            actual_path=assertion_dict.get("actual_path"),
            operator=operator,
            description=assertion_dict.get("description"),
        )
    except Exception:
        return None


def validate_response(response_json: str, assertions_json: str) -> ToolResponse:
    """
    Validate API response against assertion rules.

    Performs validation of response data against provided assertions
    without sending a new request. Pass the response returned by
    `http_request` (from http_client_tools) as response_json.

    Args:
        response_json: JSON string of response object with fields:
            - status_code: HTTP status code
            - headers: Response headers dict
            - body: Response body (dict or string)
            - elapsed_ms: Response time in milliseconds (or elapsed in seconds)
        assertions_json: JSON string of assertion rules list

    Returns:
        ToolResponse containing validation results:
        {
            "status": "success",
            "all_passed": true,
            "passed_count": 3,
            "failed_count": 0,
            "results": [...]
        }
    """
    engine = None
    try:
        response_dict = json.loads(response_json) if isinstance(response_json, str) else response_json
        assertions_list = json.loads(assertions_json) if isinstance(assertions_json, str) else assertions_json

        # Support both elapsed (seconds) and elapsed_ms (milliseconds) from http_request
        elapsed = response_dict.get("elapsed", 0)
        if not elapsed:
            elapsed_ms = response_dict.get("elapsed_ms", 0)
            elapsed = elapsed_ms / 1000.0 if elapsed_ms else 0

        response = Response(
            status_code=response_dict.get("status_code", 0),
            headers=response_dict.get("headers", {}),
            body=response_dict.get("body", {}),
            elapsed=elapsed,
        )

        assertions = []
        for assertion_dict in assertions_list:
            assertion = _parse_assertion(assertion_dict)
            if assertion:
                assertions.append(assertion)

        if not assertions:
            return ToolResponse(
                content=[TextBlock(
                    type="text",
                    text=json.dumps({
                        "status": "warning",
                        "message": "No valid assertions provided",
                        "all_passed": True,
                        "results": [],
                    }, ensure_ascii=False),
                )]
            )

        engine = RequestsEngine()
        engine.initialize({"log_level": "WARNING"})
        results = engine.validate_assertions(response, assertions)

        validation_results = []
        passed_count = 0
        for ar in results:
            passed = ar.passed
            if passed:
                passed_count += 1
            validation_results.append({
                "type": ar.assertion.type.value if hasattr(ar.assertion.type, "value") else str(ar.assertion.type),
                "expected": ar.assertion.expected,
                "actual": ar.actual_value,
                "passed": passed,
                "error_message": ar.error_message,
            })

        all_passed = passed_count == len(results)

        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "all_passed": all_passed,
                    "passed_count": passed_count,
                    "failed_count": len(results) - passed_count,
                    "total_assertions": len(results),
                    "results": validation_results,
                }, ensure_ascii=False, default=str),
            )]
        )

    except json.JSONDecodeError as e:
        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "error_code": "INVALID_JSON",
                    "message": f"Invalid JSON input: {str(e)}",
                }, ensure_ascii=False),
            )]
        )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "error_code": "VALIDATION_ERROR",
                    "message": f"Response validation failed: {str(e)}",
                }, ensure_ascii=False),
            )]
        )

    finally:
        if engine:
            engine.cleanup()


def capture_metrics(results_json: str) -> ToolResponse:
    """
    Capture and summarize performance metrics from test results.

    Analyzes test results to provide performance statistics including
    response times, success rates, and error distribution.

    Args:
        results_json: JSON string of test results list. Each result should contain:
            - testcase_id: Test case identifier
            - interface_name: API name
            - test_status: "PASSED" | "FAILED" | "ERROR"
            - duration: Execution time in seconds
            - error_message: Error description (if any)

    Returns:
        ToolResponse containing metrics summary:
        {
            "status": "success",
            "summary": {
                "total_tests": 10,
                "passed": 8,
                "failed": 1,
                "error": 1,
                "pass_rate": 80.0,
                "avg_duration": 0.234,
                "min_duration": 0.102,
                "max_duration": 0.567
            },
            "slowest_tests": [...],
            "error_distribution": {...}
        }
    """
    try:
        results = json.loads(results_json) if isinstance(results_json, str) else results_json

        if not results:
            return ToolResponse(
                content=[TextBlock(
                    type="text",
                    text=json.dumps({
                        "status": "warning",
                        "message": "No test results provided",
                        "summary": {},
                    }, ensure_ascii=False),
                )]
            )

        total = len(results)
        passed = sum(1 for r in results if r.get("test_status") == "PASSED" or r.get("status") == "PASSED")
        failed = sum(1 for r in results if r.get("test_status") == "FAILED" or r.get("status") == "FAILED")
        error = sum(1 for r in results if r.get("test_status") == "ERROR" or r.get("status") == "ERROR")

        durations = [r.get("duration", 0) for r in results if r.get("duration")]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        sorted_by_duration = sorted(results, key=lambda x: x.get("duration", 0), reverse=True)
        slowest_tests = [
            {
                "testcase_id": r.get("testcase_id", ""),
                "interface_name": r.get("interface_name", ""),
                "duration": round(r.get("duration", 0), 3),
            }
            for r in sorted_by_duration[:5]
        ]

        error_distribution: Dict[str, int] = {}
        for r in results:
            if r.get("error_message"):
                error_type = _classify_error(r["error_message"])
                error_distribution[error_type] = error_distribution.get(error_type, 0) + 1

        pass_rate = round((passed / total) * 100, 2) if total > 0 else 0

        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "summary": {
                        "total_tests": total,
                        "passed": passed,
                        "failed": failed,
                        "error": error,
                        "skipped": total - passed - failed - error,
                        "pass_rate": pass_rate,
                        "avg_duration": round(avg_duration, 3),
                        "min_duration": round(min_duration, 3),
                        "max_duration": round(max_duration, 3),
                        "total_duration": round(sum(durations), 3),
                    },
                    "slowest_tests": slowest_tests,
                    "error_distribution": error_distribution,
                }, ensure_ascii=False),
            )]
        )

    except json.JSONDecodeError as e:
        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "error_code": "INVALID_JSON",
                    "message": f"Invalid results JSON: {str(e)}",
                }, ensure_ascii=False),
            )]
        )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "error_code": "METRICS_ERROR",
                    "message": f"Failed to capture metrics: {str(e)}",
                }, ensure_ascii=False),
            )]
        )


def _classify_error(error_message: str) -> str:
    """对错误信息进行分类"""
    msg = error_message.lower()
    if "timeout" in msg:
        return "timeout"
    elif "connection" in msg or "refused" in msg:
        return "connection_error"
    elif "401" in error_message or "unauthorized" in msg:
        return "authentication"
    elif "403" in error_message or "forbidden" in msg:
        return "authorization"
    elif "404" in error_message or "not found" in msg:
        return "not_found"
    elif "500" in error_message or "internal server" in msg:
        return "server_error"
    elif "断言" in error_message or "assertion" in msg:
        return "assertion_failure"
    else:
        return "other"
