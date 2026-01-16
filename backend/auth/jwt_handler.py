"""
JWT 处理器

负责JWT令牌的生成、验证和解析。
"""

import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from backend.common.logger import get_logger


class JWTHandler:
    """JWT处理器"""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_hours: int = 24
    ):
        """
        初始化JWT处理器
        
        Args:
            secret_key: JWT密钥
            algorithm: 加密算法
            access_token_expire_hours: 访问令牌过期时间（小时）
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = timedelta(hours=access_token_expire_hours)
        self.logger = get_logger()
        
        self.logger.info(
            f"[JWTHandler] 初始化完成 | algorithm: {algorithm} | "
            f"expire_hours: {access_token_expire_hours}"
        )
    
    def create_access_token(
        self,
        user_id: str,
        username: str,
        role: str = "user",
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str, datetime]:
        """
        创建访问令牌
        
        Args:
            user_id: 用户ID
            username: 用户名
            role: 用户角色
            extra_claims: 额外的声明
            
        Returns:
            (token, jti, expire_at) 元组
        """
        jti = str(uuid.uuid4())  # JWT ID，用于会话互斥
        now = datetime.utcnow()
        expire_at = now + self.access_token_expire
        
        payload = {
            "sub": user_id,           # Subject (用户ID)
            "username": username,
            "role": role,
            "jti": jti,               # JWT ID
            "iat": now,               # Issued At
            "exp": expire_at          # Expiration
        }
        
        if extra_claims:
            payload.update(extra_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        self.logger.info(
            f"[JWTHandler] 创建令牌 | user_id: {user_id} | jti: {jti[:8]}..."
        )
        
        return token, jti, expire_at
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证令牌
        
        Args:
            token: JWT令牌
            
        Returns:
            解析后的payload，验证失败返回None
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        
        except jwt.ExpiredSignatureError:
            self.logger.warning("[JWTHandler] 令牌已过期")
            return None
        
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"[JWTHandler] 令牌无效: {str(e)}")
            return None
    
    def decode_token_without_verify(self, token: str) -> Optional[Dict[str, Any]]:
        """
        解码令牌（不验证签名和过期时间）
        用于获取过期令牌的信息
        
        Args:
            token: JWT令牌
            
        Returns:
            解析后的payload
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False, "verify_signature": False}
            )
            return payload
        except jwt.InvalidTokenError:
            return None
    
    def get_token_expire_seconds(self) -> int:
        """获取令牌过期时间（秒）"""
        return int(self.access_token_expire.total_seconds())
