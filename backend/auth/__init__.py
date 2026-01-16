"""
认证模块

提供用户认证、会话管理、JWT处理等功能。
"""

from backend.auth.models import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserInDB,
    ChangePasswordRequest,
    UpdateProfileRequest
)
from backend.auth.jwt_handler import JWTHandler
from backend.auth.service import AuthService, SessionManager, get_auth_service
from backend.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
    get_admin_user,
    get_token_from_header
)
from backend.auth.routes import router as auth_router

__all__ = [
    "UserCreate",
    "UserLogin", 
    "UserResponse",
    "TokenResponse",
    "UserInDB",
    "ChangePasswordRequest",
    "UpdateProfileRequest",
    "JWTHandler",
    "AuthService",
    "SessionManager",
    "get_auth_service",
    "get_current_user",
    "get_current_user_optional",
    "get_admin_user",
    "get_token_from_header",
    "auth_router"
]
