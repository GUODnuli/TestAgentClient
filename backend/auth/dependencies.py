"""
认证依赖注入

提供 FastAPI 依赖注入函数，用于认证中间件和获取当前用户。
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.auth.models import UserInDB, UserResponse
from backend.auth.jwt_handler import JWTHandler
from backend.auth.service import AuthService, get_auth_service
from backend.common.logger import get_logger


# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)

logger = get_logger()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    """
    获取当前认证用户（必须登录）
    
    Args:
        credentials: HTTP Bearer 认证凭证
        auth_service: 认证服务实例
        
    Returns:
        当前用户信息
        
    Raises:
        HTTPException: 认证失败
    """
    if credentials is None:
        logger.warning("[Auth] 缺少认证凭证")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    
    # 验证Token（使用auth_service中的jwt_handler）
    payload = auth_service.jwt.verify_token(token)
    
    if payload is None:
        logger.warning("[Auth] Token无效或已过期")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("sub")
    jti = payload.get("jti")
    
    if not user_id or not jti:
        logger.warning("[Auth] Token缺少必要字段")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token格式错误",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 验证会话（检查是否被踢出）
    if not auth_service.session_manager.validate_session(user_id, jti):
        logger.warning(f"[Auth] 会话已失效 | user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 获取用户信息
    user = auth_service.get_user(user_id)
    
    if user is None:
        logger.warning(f"[Auth] 用户不存在 | user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 检查用户状态
    if user.status != "active":
        logger.warning(f"[Auth] 用户已禁用 | user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[UserResponse]:
    """
    获取当前认证用户（可选，允许未登录）
    
    Args:
        credentials: HTTP Bearer 认证凭证
        auth_service: 认证服务实例
        
    Returns:
        当前用户信息，未登录则返回 None
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, auth_service)
    except HTTPException:
        return None


async def get_admin_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    获取当前管理员用户（必须是管理员）
    
    Args:
        current_user: 当前认证用户
        
    Returns:
        管理员用户信息
        
    Raises:
        HTTPException: 不是管理员
    """
    if current_user.role != "admin":
        logger.warning(f"[Auth] 非管理员访问 | user_id: {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return current_user


def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    从请求头获取 Token
    
    Args:
        credentials: HTTP Bearer 认证凭证
        
    Returns:
        Token 字符串，未提供则返回 None
    """
    if credentials is None:
        return None
    return credentials.credentials
