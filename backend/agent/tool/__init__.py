# -*- coding: utf-8 -*-
"""
Agent 工具集

导出所有可用的 Agent 工具函数，供 ReActAgent 注册使用。

工具分类：
- utils: 基础文件操作工具（list_uploaded_files, safe_view_text_file）
- doc_parser: 文档解析工具（read_document, extract_api_spec, validate_api_spec）
- case_generator: 用例生成工具（generate_positive_cases, generate_negative_cases, generate_security_cases）
- test_executor: 测试执行工具（execute_api_test, validate_response, capture_metrics）
- report_tools: 报告生成工具（generate_test_report, diagnose_failures, suggest_improvements）
"""

# ===== 基础工具 =====
from .utils import (
    list_uploaded_files,
    safe_view_text_file,
    safe_write_text_file
)

# ===== 文档解析工具 =====
from .doc_parser import (
    read_document,
    extract_api_spec,
    validate_api_spec
)

# ===== 用例生成工具 =====
from .case_generator import (
    generate_positive_cases,
    generate_negative_cases,
    generate_security_cases
)

# ===== 测试执行工具 =====
from .test_executor import (
    execute_api_test,
    validate_response,
    capture_metrics
)

# ===== 报告生成工具 =====
from .report_tools import (
    generate_test_report,
    diagnose_failures,
    suggest_improvements
)

# 导出所有工具
__all__ = [
    # 基础工具
    "list_uploaded_files",
    "safe_view_text_file",
    "safe_write_text_file",
    # 文档解析
    "read_document",
    "extract_api_spec",
    "validate_api_spec",
    # 用例生成
    "generate_positive_cases",
    "generate_negative_cases",
    "generate_security_cases",
    # 测试执行
    "execute_api_test",
    "validate_response",
    "capture_metrics",
    # 报告生成
    "generate_test_report",
    "diagnose_failures",
    "suggest_improvements",
]


# 工具分组定义（供 Toolkit.create_tool_group 使用）
TOOL_GROUPS = {
    "doc_parsing": {
        "description": "文档解析工具组：用于读取和解析接口文档，提取 API 规范",
        "tools": ["read_document", "extract_api_spec", "validate_api_spec"]
    },
    "case_generation": {
        "description": "用例生成工具组：基于 API 规范自动生成各类测试用例",
        "tools": ["generate_positive_cases", "generate_negative_cases", "generate_security_cases"]
    },
    "test_execution": {
        "description": "测试执行工具组：执行 API 测试并验证响应",
        "tools": ["execute_api_test", "validate_response", "capture_metrics"]
    },
    "reporting": {
        "description": "报告生成工具组：生成测试报告、诊断失败、提供改进建议",
        "tools": ["generate_test_report", "diagnose_failures", "suggest_improvements"]
    },
    "file_operations": {
        "description": "文件操作工具组：列出和读取上传的文件",
        "tools": ["list_uploaded_files", "safe_view_text_file"]
    }
}
