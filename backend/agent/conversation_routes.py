"""
对话历史路由

提供对话管理 API 端点。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel
import uuid

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserResponse
from backend.common.database import get_database
from backend.common.logger import get_logger


router = APIRouter(prefix="/conversations", tags=["对话历史"])

logger = get_logger()


# 请求/响应模型
class CreateConversationRequest(BaseModel):
    title: str


class UpdateConversationRequest(BaseModel):
    title: str


class CreateMessageRequest(BaseModel):
    role: str  # user / assistant
    content: str


class ConversationResponse(BaseModel):
    conversation_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: Optional[int] = None


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: CreateConversationRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    创建新对话
    
    - **title**: 对话标题
    """
    try:
        db = get_database()
        conversation_id = str(uuid.uuid4())
        
        db.create_conversation(
            conversation_id=conversation_id,
            user_id=current_user.user_id,
            title=request.title
        )
        
        conversation = db.get_conversation(conversation_id)
        
        return ConversationResponse(
            conversation_id=conversation['conversation_id'],
            user_id=conversation['user_id'],
            title=conversation['title'],
            created_at=conversation['created_at'],
            updated_at=conversation['updated_at'],
            message_count=0
        )
    
    except Exception as e:
        logger.error(f"[Conversations] 创建对话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建对话失败"
        )


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = 100,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    获取用户的对话列表
    
    - **limit**: 返回数量限制（默认100）
    - **offset**: 偏移量（默认0）
    """
    try:
        db = get_database()
        conversations = db.list_user_conversations(
            user_id=current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        # 添加消息数量
        result = []
        for conv in conversations:
            message_count = db.count_conversation_messages(conv['conversation_id'])
            result.append(ConversationResponse(
                conversation_id=conv['conversation_id'],
                user_id=conv['user_id'],
                title=conv['title'],
                created_at=conv['created_at'],
                updated_at=conv['updated_at'],
                message_count=message_count
            ))
        
        return result
    
    except Exception as e:
        logger.error(f"[Conversations] 获取对话列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取对话列表失败"
        )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    获取对话详情
    """
    try:
        db = get_database()
        conversation = db.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="对话不存在"
            )
        
        # 检查权限
        if conversation['user_id'] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此对话"
            )
        
        message_count = db.count_conversation_messages(conversation_id)
        
        return ConversationResponse(
            conversation_id=conversation['conversation_id'],
            user_id=conversation['user_id'],
            title=conversation['title'],
            created_at=conversation['created_at'],
            updated_at=conversation['updated_at'],
            message_count=message_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Conversations] 获取对话详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取对话详情失败"
        )


@router.put("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    更新对话标题
    """
    try:
        db = get_database()
        conversation = db.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="对话不存在"
            )
        
        # 检查权限
        if conversation['user_id'] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此对话"
            )
        
        db.update_conversation_title(conversation_id, request.title)
        
        return {"message": "对话标题已更新"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Conversations] 更新对话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新对话失败"
        )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    删除对话
    """
    try:
        db = get_database()
        conversation = db.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="对话不存在"
            )
        
        # 检查权限
        if conversation['user_id'] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此对话"
            )
        
        db.delete_conversation(conversation_id)
        
        return {"message": "对话已删除"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Conversations] 删除对话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除对话失败"
        )


# ==================== 消息相关接口 ====================

@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: str,
    request: CreateMessageRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    创建新消息
    
    - **role**: user 或 assistant
    - **content**: 消息内容
    """
    try:
        db = get_database()
        conversation = db.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="对话不存在"
            )
        
        # 检查权限
        if conversation['user_id'] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权在此对话中发送消息"
            )
        
        message_id = str(uuid.uuid4())
        
        db.create_message(
            message_id=message_id,
            conversation_id=conversation_id,
            role=request.role,
            content=request.content
        )
        
        # 获取创建的消息
        messages = db.list_conversation_messages(conversation_id, limit=1, offset=0)
        # 反向查找最新消息
        all_messages = db.list_conversation_messages(conversation_id, limit=1000)
        message = [m for m in all_messages if m['message_id'] == message_id][0]
        
        return MessageResponse(
            message_id=message['message_id'],
            conversation_id=message['conversation_id'],
            role=message['role'],
            content=message['content'],
            created_at=message['created_at']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Conversations] 创建消息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建消息失败"
        )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    获取对话的消息列表
    
    - **limit**: 返回数量限制（默认100）
    - **offset**: 偏移量（默认0）
    """
    try:
        db = get_database()
        conversation = db.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="对话不存在"
            )
        
        # 检查权限
        if conversation['user_id'] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此对话的消息"
            )
        
        messages = db.list_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset
        )
        
        return [
            MessageResponse(
                message_id=msg['message_id'],
                conversation_id=msg['conversation_id'],
                role=msg['role'],
                content=msg['content'],
                created_at=msg['created_at']
            )
            for msg in messages
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Conversations] 获取消息列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取消息列表失败"
        )
