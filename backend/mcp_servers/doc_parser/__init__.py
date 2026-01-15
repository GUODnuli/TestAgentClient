"""
文档解析 MCP Server

提供 API 文档解析功能，支持 OpenAPI、Postman Collection、HAR 等格式。
"""

from .doc_parser import DocumentParser

__all__ = ["DocumentParser"]
