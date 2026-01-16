"""
Dify API 客户端

提供与 Dify 工作流 API 的交互接口。
"""

import json
import requests
import time
from typing import Any, Dict, Generator, Optional

from ..common.logger import get_logger


class DifyAPIError(Exception):
    """Dify API 异常"""
    pass


class DifyClient:
    """Dify API 客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Dify 客户端
        
        Args:
            config: Dify 配置（来自 dify.toml）
        """
        self.api_endpoint = config.get("api_endpoint")
        self.api_key = config.get("api_key")
        self.timeout = config.get("timeout", 120)
        self.max_context_tokens = config.get("max_context_tokens", 20000)
        
        # 重试配置
        retry_config = config.get("retry", {})
        self.retry_enabled = retry_config.get("enabled", True)
        self.max_attempts = retry_config.get("max_attempts", 3)
        self.backoff_factor = retry_config.get("backoff_factor", 2)
        
        self.logger = get_logger()
        
        if not self.api_endpoint or not self.api_key:
            raise DifyAPIError("Dify API 配置不完整，请检查 api_endpoint 和 api_key")
        
        self.logger.info(f"Dify 客户端初始化 | endpoint: {self.api_endpoint}")
    
    def call_workflow_streaming(
        self,
        inputs: Dict[str, Any],
        user: str = "mcp-agent"
    ) -> Generator[str, None, None]:
        """
        调用 Dify 工作流（流式模式）
        
        Args:
            inputs: 工作流输入参数
            user: 用户标识
            
        Yields:
            流式返回的文本块
            
        Raises:
            DifyAPIError: API 调用失败
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": inputs,
            "response_mode": "streaming",
            "user": user
        }
        
        self.logger.info("[Dify Streaming] 开始流式调用")
        
        try:
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = f"Dify API 返回错误 | 状态码: {response.status_code}"
                self.logger.error(error_msg)
                raise DifyAPIError(error_msg)
            
            # 解析 SSE 流
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    # SSE 格式: data: {...}
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # 去掉 "data: " 前缀
                        
                        try:
                            data = json.loads(data_str)
                            event_type = data.get("event")
                            
                            # 处理不同事件类型
                            if event_type == "text_chunk":
                                # 文本块事件
                                text = data.get("data", {}).get("text", "")
                                if text:
                                    yield text
                            
                            elif event_type == "message":
                                # 完整消息事件（某些工作流使用）
                                answer = data.get("answer", "")
                                if answer:
                                    yield answer
                            
                            elif event_type == "workflow_finished":
                                # 工作流完成
                                outputs = data.get("data", {}).get("outputs", {})
                                # 尝试提取输出文本
                                for field in ["text", "output", "result", "reply"]:
                                    if field in outputs:
                                        text = outputs[field]
                                        if text and isinstance(text, str):
                                            yield text
                                        break
                                self.logger.info("[Dify Streaming] 工作流完成")
                            
                            elif event_type == "error":
                                error_msg = data.get("message", "未知错误")
                                self.logger.error(f"[Dify Streaming] 错误: {error_msg}")
                                raise DifyAPIError(error_msg)
                            
                            elif event_type in ["node_started", "node_finished", "workflow_started"]:
                                # 节点事件，忽略
                                pass
                            
                            else:
                                self.logger.debug(f"[Dify Streaming] 未知事件: {event_type}")
                        
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"[Dify Streaming] JSON 解析失败: {data_str[:100]}")
            
            self.logger.info("[Dify Streaming] 流式调用结束")
        
        except requests.Timeout:
            self.logger.error("[Dify Streaming] 请求超时")
            raise DifyAPIError("请求超时")
        
        except requests.RequestException as e:
            self.logger.error(f"[Dify Streaming] 请求异常: {e}")
            raise DifyAPIError(f"请求异常: {str(e)}")
    
    def call_workflow(
        self,
        inputs: Dict[str, Any],
        user: str = "mcp-agent"
    ) -> Dict[str, Any]:
        """
        调用 Dify 工作流
        
        Args:
            inputs: 工作流输入参数
            user: 用户标识
            
        Returns:
            工作流输出结果
            
        Raises:
            DifyAPIError: API 调用失败
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user
        }
        
        attempt = 0
        last_error = None
        
        while attempt < self.max_attempts:
            try:
                self.logger.info(
                    f"调用 Dify API | 尝试: {attempt + 1}/{self.max_attempts}"
                )
                
                response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    result = response.json()
                    
                    # 支持多种响应格式
                    # 格式1: {"data": {"outputs": {...}}} - 标准工作流
                    # 格式2: {"text": "..."} - 文本生成工作流
                    if "data" in result and "outputs" in result["data"]:
                        outputs = result["data"]["outputs"]
                        self.logger.info("Dify API 调用成功")
                        return {"data": {"outputs": outputs}}
                    elif "text" in result:
                        # 文本生成工作流，包装为标准格式
                        self.logger.info("Dify API 调用成功（文本格式）")
                        return {"data": {"outputs": {"text": result["text"]}}}
                    else:
                        self.logger.warning(f"Dify API 响应格式异常: {result}")
                        return {"data": {"outputs": result}}
                
                elif response.status_code == 429:  # Rate limit
                    wait_time = self.backoff_factor ** attempt
                    self.logger.warning(
                        f"Dify API 速率限制 | 等待 {wait_time} 秒后重试"
                    )
                    time.sleep(wait_time)
                    attempt += 1
                    continue
                
                else:
                    error_msg = f"Dify API 返回错误 | 状态码: {response.status_code} | 响应: {response.text}"
                    self.logger.error(error_msg)
                    raise DifyAPIError(error_msg)
            
            except requests.Timeout:
                last_error = "请求超时"
                self.logger.warning(f"Dify API 请求超时 | 尝试: {attempt + 1}")
                attempt += 1
                if attempt < self.max_attempts:
                    time.sleep(self.backoff_factor ** attempt)
            
            except requests.RequestException as e:
                last_error = str(e)
                self.logger.error(f"Dify API 请求异常: {e}")
                attempt += 1
                if attempt < self.max_attempts and self.retry_enabled:
                    time.sleep(self.backoff_factor ** attempt)
                else:
                    break
        
        # 所有重试都失败
        raise DifyAPIError(f"Dify API 调用失败（已重试 {attempt} 次）: {last_error}")
    
    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        
        使用简单的估算方法：英文约 4 字符/token，中文约 1.5 字符/token
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数量
        """
        # 简单估算：统计中英文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = len(text) - chinese_chars
        
        # 中文约 1.5 字符/token，英文约 4 字符/token
        estimated_tokens = int(chinese_chars / 1.5 + english_chars / 4)
        
        return estimated_tokens
    
    def check_context_size(self, text: str) -> bool:
        """
        检查文本是否超过上下文限制
        
        Args:
            text: 文本内容
            
        Returns:
            是否在限制内
        """
        tokens = self.estimate_tokens(text)
        return tokens <= self.max_context_tokens
