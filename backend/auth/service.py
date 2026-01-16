"""
认证服务

提供用户注册、登录、会话管理等功能。
"""

import uuid
import json
import redis
from datetime import datetime
from typing import Optional, Dict, Any
from passlib.context import CryptContext

from backend.auth.models import UserCreate, UserInDB, UserResponse, TokenResponse
from backend.auth.jwt_handler import JWTHandler
from backend.common.logger import get_logger


# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SessionManager:
    """会话管理器 - 使用Redis实现会话互斥"""
    
    def __init__(self, redis_config: Dict[str, Any]):
        """
        初始化会话管理器
        
        Args:
            redis_config: Redis配置
        """
        self.logger = get_logger()
        self.session_prefix = "session:"
        self.session_ttl = redis_config.get("session_ttl", 86400)
        
        # 连接Redis
        try:
            self.redis = redis.Redis(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                db=redis_config.get("db", 0),
                password=redis_config.get("password") or None,
                socket_timeout=redis_config.get("socket_timeout", 5),
                decode_responses=True
            )
            # 测试连接
            self.redis.ping()
            self.enabled = True
            self.logger.info("[SessionManager] Redis连接成功")
        except redis.ConnectionError as e:
            self.enabled = False
            self.logger.warning(
                f"[SessionManager] Redis连接失败，会话互斥功能禁用: {str(e)}"
            )
    
    def create_session(
        self,
        user_id: str,
        token_jti: str,
        device_info: str = "",
        ip_address: str = ""
    ) -> bool:
        """
        创建新会话，同时踢出旧会话
        
        Args:
            user_id: 用户ID
            token_jti: JWT ID
            device_info: 设备信息
            ip_address: IP地址
            
        Returns:
            是否成功
        """
        if not self.enabled:
            return True
        
        session_key = f"{self.session_prefix}{user_id}"
        
        try:
            # 获取旧会话（用于日志）
            old_session = self.redis.get(session_key)
            if old_session:
                old_data = json.loads(old_session)
                self.logger.info(
                    f"[SessionManager] 踢出旧会话 | user_id: {user_id} | "
                    f"old_jti: {old_data.get('token_jti', '')[:8]}..."
                )
            
            # 设置新会话
            session_data = {
                "token_jti": token_jti,
                "device_info": device_info,
                "ip_address": ip_address,
                "created_at": datetime.utcnow().isoformat()
            }
            self.redis.setex(session_key, self.session_ttl, json.dumps(session_data))
            
            self.logger.info(
                f"[SessionManager] 创建会话 | user_id: {user_id} | "
                f"jti: {token_jti[:8]}..."
            )
            return True
        
        except redis.RedisError as e:
            self.logger.error(f"[SessionManager] 创建会话失败: {str(e)}")
            return False
    
    def validate_session(self, user_id: str, token_jti: str) -> bool:
        """
        验证会话是否有效（检测是否被踢出）
        
        Args:
            user_id: 用户ID
            token_jti: JWT ID
            
        Returns:
            会话是否有效
        """
        if not self.enabled:
            return True
        
        session_key = f"{self.session_prefix}{user_id}"
        
        try:
            session_data = self.redis.get(session_key)
            
            if not session_data:
                self.logger.warning(
                    f"[SessionManager] 会话不存在 | user_id: {user_id}"
                )
                return False
            
            session = json.loads(session_data)
            is_valid = session.get("token_jti") == token_jti
            
            if not is_valid:
                self.logger.warning(
                    f"[SessionManager] 会话已失效（被踢出）| user_id: {user_id}"
                )
            
            return is_valid
        
        except redis.RedisError as e:
            self.logger.error(f"[SessionManager] 验证会话失败: {str(e)}")
            # Redis异常时允许访问
            return True
    
    def invalidate_session(self, user_id: str) -> bool:
        """
        注销会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        if not self.enabled:
            return True
        
        session_key = f"{self.session_prefix}{user_id}"
        
        try:
            self.redis.delete(session_key)
            self.logger.info(f"[SessionManager] 注销会话 | user_id: {user_id}")
            return True
        
        except redis.RedisError as e:
            self.logger.error(f"[SessionManager] 注销会话失败: {str(e)}")
            return False
    
    def get_session_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        if not self.enabled:
            return None
        
        session_key = f"{self.session_prefix}{user_id}"
        
        try:
            session_data = self.redis.get(session_key)
            if session_data:
                return json.loads(session_data)
            return None
        except redis.RedisError:
            return None


class AuthService:
    """认证服务"""
    
    def __init__(
        self,
        database,
        jwt_handler: JWTHandler,
        session_manager: SessionManager
    ):
        """
        初始化认证服务
        
        Args:
            database: 数据库实例
            jwt_handler: JWT处理器
            session_manager: 会话管理器
        """
        self.db = database
        self.jwt = jwt_handler
        self.session_manager = session_manager
        self.logger = get_logger()
        
        self.logger.info("[AuthService] 初始化完成")
    
    def hash_password(self, password: str) -> str:
        """哈希密码"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def register(self, user_data: UserCreate) -> UserResponse:
        """
        用户注册
        
        Args:
            user_data: 注册信息
            
        Returns:
            用户响应
            
        Raises:
            ValueError: 用户名或邮箱已存在
        """
        # 检查用户名是否存在
        existing_user = self.db.get_user_by_username(user_data.username)
        if existing_user:
            raise ValueError("用户名已存在")
        
        # 检查邮箱是否存在
        if user_data.email:
            existing_email = self.db.get_user_by_email(user_data.email)
            if existing_email:
                raise ValueError("邮箱已被使用")
        
        # 创建用户
        user_id = str(uuid.uuid4())
        password_hash = self.hash_password(user_data.password)
        
        self.db.create_user(
            user_id=user_id,
            username=user_data.username,
            password_hash=password_hash,
            email=user_data.email,
            display_name=user_data.display_name or user_data.username
        )
        
        self.logger.info(
            f"[AuthService] 用户注册成功 | user_id: {user_id} | "
            f"username: {user_data.username}"
        )
        
        return UserResponse(
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            display_name=user_data.display_name or user_data.username,
            role="user",
            status="active"
        )
    
    def login(
        self,
        username: str,
        password: str,
        device_info: str = "",
        ip_address: str = ""
    ) -> TokenResponse:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            device_info: 设备信息
            ip_address: IP地址
            
        Returns:
            令牌响应
            
        Raises:
            ValueError: 用户名或密码错误
        """
        # 获取用户
        user_data = self.db.get_user_by_username(username)
        if not user_data:
            self.logger.warning(f"[AuthService] 登录失败：用户不存在 | username: {username}")
            raise ValueError("用户名或密码错误")
        
        # 检查状态
        if user_data.get("status") != "active":
            self.logger.warning(
                f"[AuthService] 登录失败：用户已禁用 | username: {username}"
            )
            raise ValueError("账户已被禁用")
        
        # 验证密码
        if not self.verify_password(password, user_data.get("password_hash", "")):
            self.logger.warning(f"[AuthService] 登录失败：密码错误 | username: {username}")
            raise ValueError("用户名或密码错误")
        
        user_id = user_data.get("user_id")
        user_role = user_data.get("role", "user")
        
        # 生成令牌
        token, jti, expire_at = self.jwt.create_access_token(
            user_id=user_id,
            username=username,
            role=user_role
        )
        
        # 创建会话（踢出旧会话）
        self.session_manager.create_session(
            user_id=user_id,
            token_jti=jti,
            device_info=device_info,
            ip_address=ip_address
        )
        
        # 更新最后登录时间
        self.db.update_user_last_login(user_id)
        
        # 记录用户数据用于调试
        self.logger.debug(
            f"[AuthService] 准备创建TokenResponse | user_id: {user_id} | "
            f"username: {username} | email: {user_data.get('email')} | "
            f"display_name: {user_data.get('display_name')} | "
            f"role: {user_role} | status: {user_data.get('status')}"
        )
        
        self.logger.info(
            f"[AuthService] 用户登录成功 | user_id: {user_id} | "
            f"username: {username} | ip: {ip_address}"
        )
        
        # 确保所有字符串字段不为None（Pydantic要求）
        email = user_data.get("email")
        display_name = user_data.get("display_name") or username
        status_value = user_data.get("status", "active")
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=self.jwt.get_token_expire_seconds(),
            user=UserResponse(
                user_id=user_id,
                username=username,
                email=email if email else None,
                display_name=display_name,
                role=user_role,
                status=status_value
            )
        )
    
    def logout(self, user_id: str) -> bool:
        """
        用户登出
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        result = self.session_manager.invalidate_session(user_id)
        self.logger.info(f"[AuthService] 用户登出 | user_id: {user_id}")
        return result
    
    def get_user(self, user_id: str) -> Optional[UserResponse]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户响应或None
        """
        user_data = self.db.get_user_by_id(user_id)
        if user_data:
            return UserResponse(
                user_id=user_data.get("user_id"),
                username=user_data.get("username"),
                email=user_data.get("email"),
                display_name=user_data.get("display_name"),
                role=user_data.get("role", "user"),
                status=user_data.get("status", "active")
            )
        return None
    
    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 旧密码错误
        """
        user_data = self.db.get_user_by_id(user_id)
        if not user_data:
            raise ValueError("用户不存在")
        
        if not self.verify_password(old_password, user_data.get("password_hash", "")):
            raise ValueError("旧密码错误")
        
        new_hash = self.hash_password(new_password)
        self.db.update_user_password(user_id, new_hash)
        
        # 注销会话，强制重新登录
        self.session_manager.invalidate_session(user_id)
        
        self.logger.info(f"[AuthService] 密码修改成功 | user_id: {user_id}")
        return True


# ==================== 全局实例 ====================

_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """
    获取全局认证服务实例（单例模式）
    
    Returns:
        认证服务实例
    """
    global _auth_service
    
    if _auth_service is None:
        import toml
        from pathlib import Path
        from backend.common.database import get_database
        
        # 加载配置
        config_path = Path("config/auth.toml")
        if config_path.exists():
            config = toml.load(config_path)
        else:
            config = {}
        
        jwt_config = config.get("jwt", {})
        redis_config = config.get("redis", {})
        
        # 创建组件
        database = get_database()
        jwt_handler = JWTHandler(**jwt_config) if jwt_config else JWTHandler(secret_key="default-secret-key-change-in-production")
        session_manager = SessionManager(redis_config)
        
        _auth_service = AuthService(
            database=database,
            jwt_handler=jwt_handler,
            session_manager=session_manager
        )
    
    return _auth_service
