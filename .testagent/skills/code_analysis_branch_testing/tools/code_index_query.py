# -*- coding: utf-8 -*-
"""
代码索引查询工具集

通过 HTTP 调用 Code Index Service（FastAPI + tree-sitter）进行查询，
支持符号搜索、调用链分析、注解查找、源码读取。

当 Code Index Service 不可用时，自动降级返回错误提示。
"""

import json
import os
from typing import Any, Dict, List, Optional

import httpx
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

INDEX_SERVICE_URL = os.environ.get("CODE_INDEX_SERVICE_URL", "http://code-index-service:8080")
_TIMEOUT = 10.0


def _make_response(data: Dict[str, Any]) -> ToolResponse:
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(data, ensure_ascii=False))]
    )


def _error_response(error_code: str, message: str) -> ToolResponse:
    return _make_response({
        "status": "error",
        "error_code": error_code,
        "message": message,
    })


def search_symbol(
    pattern: str,
    symbol_type: str = "",
    language: str = "java",
    limit: int = 20
) -> ToolResponse:
    """
    搜索代码符号（类、方法、字段等）

    基于预构建的符号索引进行模糊或精确匹配搜索。
    支持通配符：* 匹配任意字符，? 匹配单个字符

    Args:
        pattern: 搜索模式，如 "LoanController", "*apply*", "Loan*Service"
        symbol_type: 符号类型过滤，可选 "CLASS", "METHOD", "FIELD", "INTERFACE", "ENUM"
                      空字符串表示不过滤
        language: 编程语言，默认 "java"
        limit: 返回结果数量上限，默认 20

    Returns:
        ToolResponse containing search results:
        {
            "status": "success",
            "query": {"pattern": "...", "type": "..."},
            "results": [
                {
                    "fqn": "com.bank.loan.controller.LoanController",
                    "name": "LoanController",
                    "type": "CLASS",
                    "file": "src/main/java/com/bank/loan/controller/LoanController.java",
                    "line": 15,
                    "signature": "public class LoanController",
                    "score": 0.95
                }
            ],
            "total": 1
        }

    Example:
        search_symbol("*apply*", symbol_type="METHOD")
        search_symbol("LoanController", symbol_type="CLASS")
    """
    try:
        resp = httpx.get(
            f"{INDEX_SERVICE_URL}/api/v1/query/symbols",
            params={"pattern": pattern, "symbol_type": symbol_type, "language": language, "limit": limit},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return _make_response(resp.json())
    except Exception as e:
        return _error_response("SEARCH_FAILED", f"Symbol search failed: {e}")


def get_call_chain(
    fqn: str,
    direction: str = "downstream",
    depth: int = 5,
    include_external: bool = False
) -> ToolResponse:
    """
    获取方法调用链

    基于预构建的调用图（call graph）查询指定方法的上游或下游调用关系。

    Args:
        fqn: 方法的完全限定名，如 "com.bank.loan.controller.LoanController.apply"
        direction: 查询方向，"downstream"（被谁调用）或 "upstream"（调用谁）
        depth: 查询深度，默认 5 层
        include_external: 是否包含外部服务调用（如 SOA 服务），默认 False

    Returns:
        ToolResponse containing call chain:
        {
            "status": "success",
            "entry_point": "...",
            "direction": "downstream",
            "chain": [...],
            "external_calls": [...]
        }

    Example:
        get_call_chain("com.bank.loan.controller.LoanController.apply", direction="downstream", depth=5)
    """
    try:
        resp = httpx.get(
            f"{INDEX_SERVICE_URL}/api/v1/query/call-chain",
            params={"fqn": fqn, "direction": direction, "depth": depth, "include_external": include_external},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return _make_response(resp.json())
    except Exception as e:
        return _error_response("CALL_CHAIN_FAILED", f"Call chain query failed: {e}")


def find_by_annotation(
    annotation: str,
    value: str = "",
    scope: str = "METHOD",
    codebase_path: str = ""
) -> ToolResponse:
    """
    通过注解查找代码元素

    基于预构建的注解索引，查找带有指定注解的类、方法或字段。
    常用于定位 Spring 事务入口（如 @TransCode, @RequestMapping）。

    Args:
        annotation: 注解名称，如 "TransCode", "RequestMapping", "Service"
                   可带或不带 @ 前缀
        value: 注解属性值过滤，如 "LN_LOAN_APPLY"
        scope: 查找范围，"CLASS", "METHOD", "FIELD"，默认 "METHOD"
        codebase_path: 代码库路径（可选）

    Returns:
        ToolResponse containing annotation matches:
        {
            "status": "success",
            "annotation": "@TransCode",
            "value_filter": "LN_LOAN_APPLY",
            "matches": [...],
            "total": 1
        }

    Example:
        find_by_annotation("TransCode", value="LN_LOAN_APPLY", scope="METHOD")
    """
    try:
        # Normalize annotation name
        ann = annotation.lstrip("@")
        resp = httpx.get(
            f"{INDEX_SERVICE_URL}/api/v1/query/annotations",
            params={"annotation": ann, "value": value, "scope": scope},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return _make_response(resp.json())
    except Exception as e:
        return _error_response("ANNOTATION_SEARCH_FAILED", f"Annotation search failed: {e}")


def read_method_source(
    fqn: str,
    include_body: bool = True,
    max_tokens: int = 2000
) -> ToolResponse:
    """
    读取方法源代码

    从代码库中读取指定方法的完整源代码，用于分支逻辑分析。

    Args:
        fqn: 方法的完全限定名
        include_body: 是否包含方法体，默认 True
        max_tokens: 最大返回 token 数，默认 2000

    Returns:
        ToolResponse containing method source:
        {
            "status": "success",
            "fqn": "...",
            "file": "...",
            "line_range": [45, 89],
            "signature": "...",
            "annotations": ["@Transactional"],
            "source": "...",
            "byte_size": 1240,
            "truncated": false
        }

    Example:
        read_method_source("com.bank.loan.service.LoanService.submitApplication", include_body=True)
    """
    try:
        resp = httpx.get(
            f"{INDEX_SERVICE_URL}/api/v1/query/source",
            params={"fqn": fqn, "include_body": include_body, "max_tokens": max_tokens},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return _make_response(resp.json())
    except Exception as e:
        return _error_response("SOURCE_READ_FAILED", f"Failed to read method source: {e}")
