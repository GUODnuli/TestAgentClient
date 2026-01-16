"""
用户相关数据模型

定义用户注册、登录、响应等Pydantic模型。
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re


class UserCreate(BaseModel):
    """用户注册请求模型"""
    username: str = Field(..., min_length=4, max_length=32, description="用户名")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    display_name: Optional[str] = Field(None, max_length=64, description="显示名称")
    
    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v):
            raise ValueError('用户名必须以字母开头，只能包含字母、数字和下划线')
        return v
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        # 可选：增加密码强度验证
        # if not re.search(r'[A-Z]', v):
        #     raise ValueError('密码必须包含大写字母')
        # if not re.search(r'[a-z]', v):
        #     raise ValueError('密码必须包含小写字母')
        # if not re.search(r'\d', v):
        #     raise ValueError('密码必须包含数字')
        return v


class UserLogin(BaseModel):
    """用户登录请求模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应模型（不含敏感信息）"""
    user_id: str
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "user"
    status: str = "active"
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class TokenResponse(BaseModel):
    """登录令牌响应模型"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒
    user: UserResponse


class UserInDB(BaseModel):
    """数据库中的用户模型"""
    user_id: str
    username: str
    email: Optional[str] = None
    password_hash: str
    display_name: Optional[str] = None
    role: str = "user"
    status: str = "active"
    created_at: str
    updated_at: str
    last_login_at: Optional[str] = None
    
    def to_response(self) -> UserResponse:
        """转换为响应模型"""
        return UserResponse(
            user_id=self.user_id,
            username=self.username,
            email=self.email,
            display_name=self.display_name,
            role=self.role,
            status=self.status,
            created_at=self.created_at,
            last_login_at=self.last_login_at
        )


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


class UpdateProfileRequest(BaseModel):
    """更新用户资料请求模型"""
    display_name: Optional[str] = Field(None, max_length=64, description="显示名称")
    email: Optional[EmailStr] = Field(None, description="邮箱")
