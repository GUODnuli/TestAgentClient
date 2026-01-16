"""
认证路由

提供用户注册、登录、登出、获取用户信息等 API 端点。
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Optional

from backend.auth.models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    ChangePasswordRequest, UpdateProfileRequest
)
from backend.auth.service import AuthService, get_auth_service
from backend.auth.dependencies import (
    get_current_user, get_admin_user, get_token_from_header
)
from backend.common.logger import get_logger


router = APIRouter(prefix="/auth", tags=["认证"])

logger = get_logger()


def get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_device_info(request: Request) -> str:
    """获取设备信息"""
    return request.headers.get("User-Agent", "unknown")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    用户注册
    
    - **username**: 用户名（4-32位，字母开头，只能包含字母数字下划线）
    - **password**: 密码（8-128位）
    - **email**: 邮箱（可选）
    - **display_name**: 显示名称（可选）
    """
    try:
        logger.info(
            f"[Auth] 收到注册请求 | username: {user_data.username} | "
            f"email: {user_data.email} | display_name: {user_data.display_name}"
        )
        user = auth_service.register(user_data)
        logger.info(f"[Auth] 注册成功 | user_id: {user.user_id} | username: {user.username}")
        return user
    except ValueError as e:
        logger.warning(f"[Auth] 注册验证失败 | error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[Auth] 注册失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    用户登录
    
    - **username**: 用户名
    - **password**: 密码
    
    成功返回 access_token，需要在后续请求中携带 Authorization: Bearer <token>
    """
    try:
        logger.info(
            f"[Auth] 收到登录请求 | username: {credentials.username} | "
            f"device: {get_device_info(request)[:50]} | ip: {get_client_ip(request)}"
        )
        token_response = auth_service.login(
            username=credentials.username,
            password=credentials.password,
            device_info=get_device_info(request),
            ip_address=get_client_ip(request)
        )
        logger.info(f"[Auth] 登录成功 | username: {credentials.username}")
        return token_response
    except ValueError as e:
        logger.warning(f"[Auth] 登录验证失败 | username: {credentials.username} | error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"[Auth] 登录失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@router.post("/logout")
async def logout(
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    用户登出
    
    需要携带有效的 Authorization 头
    """
    auth_service.logout(current_user.user_id)
    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    获取当前用户信息
    
    需要携带有效的 Authorization 头
    """
    return current_user


@router.put("/password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    修改密码
    
    修改成功后会注销当前会话，需要重新登录
    """
    try:
        auth_service.change_password(
            user_id=current_user.user_id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
        )
        return {"message": "密码修改成功，请重新登录"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[Auth] 修改密码失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="修改密码失败"
        )


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    更新用户资料
    
    - **display_name**: 显示名称（可选）
    - **email**: 邮箱（可选）
    """
    try:
        auth_service.db.update_user_profile(
            user_id=current_user.user_id,
            display_name=profile_data.display_name,
            email=profile_data.email
        )
        # 返回更新后的用户信息
        user = auth_service.get_user(current_user.user_id)
        return user
    except Exception as e:
        logger.error(f"[Auth] 更新资料失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/session")
async def get_session_info(
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    获取当前会话信息
    """
    session_info = auth_service.session_manager.get_session_info(current_user.user_id)
    if session_info:
        return {
            "user_id": current_user.user_id,
            "device_info": session_info.get("device_info"),
            "ip_address": session_info.get("ip_address"),
            "created_at": session_info.get("created_at")
        }
    return {"user_id": current_user.user_id, "message": "会话管理未启用"}


# ==================== 管理员接口 ====================

@router.get("/users", response_model=list)
async def list_users(
    status: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    admin_user: UserResponse = Depends(get_admin_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    获取用户列表（管理员）
    """
    from backend.common.database import UserStatus, UserRole
    
    status_enum = UserStatus(status) if status else None
    role_enum = UserRole(role) if role else None
    
    users = auth_service.db.list_users(
        status=status_enum,
        role=role_enum,
        limit=limit,
        offset=offset
    )
    return users


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    new_status: str,
    admin_user: UserResponse = Depends(get_admin_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    更新用户状态（管理员）
    
    - **new_status**: active / inactive / banned
    """
    from backend.common.database import UserStatus
    
    try:
        status_enum = UserStatus(new_status)
        auth_service.db.update_user_status(user_id, status_enum)
        
        # 如果禁用用户，同时注销其会话
        if new_status in ("inactive", "banned"):
            auth_service.session_manager.invalidate_session(user_id)
        
        return {"message": f"用户状态已更新为 {new_status}"}
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的状态值"
        )
