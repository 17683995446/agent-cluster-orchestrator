"""
Phase 1: 增强WebSocket端点
提供完整的实时协作功能，包括用户状态同步、任务更新、通知推送
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Set
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.websockets import WebSocketState
from pydantic import BaseModel, Field

from app.core.structured_logging_config import get_structured_logger
from app.models.agent_data_model import Agent
from app.models.task_data_model import Task
from app.repositories.agent_persistence_repository import AgentRepository
from app.repositories.task_persistence_repository import TaskRepository
from app.schemas.agent_api_schemas import AgentStatus
from app.schemas.task_api_schemas import TaskStatus

logger = get_structured_logger(__name__)

# WebSocket路由
websocket_router = APIRouter()


# ============== 数据模型定义 ==============

class WebSocketMessageType(str):
    """WebSocket消息类型枚举"""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    USER_PRESENCE_UPDATE = "user_presence_update"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    TASK_WATCH = "task_watch"
    TASK_UNWATCH = "task_unwatch"


class UserPresence(BaseModel):
    """用户在线状态"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    status: str = Field(default="online", description="状态: online/away/busy/offline")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskUpdate(BaseModel):
    """任务更新事件"""
    task_id: str = Field(..., description="任务ID")
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    progress: Optional[float] = Field(None, description="进度百分比")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    agent_id: Optional[str] = Field(None, description="分配的代理ID")
    message: Optional[str] = Field(None, description="更新消息")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Notification(BaseModel):
    """通知事件"""
    notification_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(..., description="通知类型: info/warning/success/error")
    title: str = Field(..., description="通知标题")
    message: str = Field(..., description="通知内容")
    data: Optional[Dict[str, Any]] = Field(None, description="附加数据")
    actionable: bool = Field(default=False, description="是否可操作")
    action_label: Optional[str] = Field(None, description="操作标签")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentUpdate(BaseModel):
    """代理状态更新事件"""
    agent_id: str = Field(..., description="代理ID")
    name: Optional[str] = Field(None, description="代理名称")
    status: Optional[AgentStatus] = Field(None, description="代理状态")
    current_task_id: Optional[str] = Field(None, description="当前任务ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============== 连接管理类 ==============

class WebSocketConnectionManager:
    """
    增强的WebSocket连接管理器
    支持房间管理、用户状态同步、事件广播
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_presence: Dict[str, UserPresence] = {}
        self.task_watchers: Dict[str, Set[str]] = {}
        self.room_members: Dict[str, Set[str]] = {}
        self.heartbeat_interval = 30.0
    
    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """建立WebSocket连接"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # 广播用户加入
        presence = UserPresence(user_id=user_id, username=f"User_{user_id}")
        self.user_presence[user_id] = presence
        await self.broadcast_presence_update(presence)
        
        logger.info(
            "websocket_connection_established",
            user_id=user_id,
            active_connections=len(self.active_connections)
        )
    
    async def disconnect(self, user_id: str) -> None:
        """断开WebSocket连接"""
        if user_id in self.active_connections:
            self.active_connections.pop(user_id)
            
            # 广播用户离开
            if user_id in self.user_presence:
                presence = self.user_presence.pop(user_id)
                presence.status = "offline"
                await self.broadcast_presence_update(presence)
            
            # 清理任务观察者
            for task_id in list(self.task_watchers.keys()):
                if user_id in self.task_watchers[task_id]:
                    self.task_watchers[task_id].remove(user_id)
            
            # 清理房间成员
            for room_id in list(self.room_members.keys()):
                if user_id in self.room_members[room_id]:
                    self.room_members[room_id].remove(user_id)
            
            logger.info(
                "websocket_connection_closed",
                user_id=user_id,
                active_connections=len(self.active_connections)
            )
    
    async def send_personal_message(self, user_id: str, message: Dict[str, Any]) -> None:
        """向特定用户发送消息"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                logger.debug("personal_message_sent", user_id=user_id)
            except Exception as e:
                logger.error(
                    "failed_to_send_personal_message",
                    user_id=user_id,
                    error=str(e)
                )
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """向所有连接广播消息"""
        disconnected_users = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(
                    "failed_to_broadcast_to_user",
                    user_id=user_id,
                    error=str(e)
                )
                disconnected_users.append(user_id)
        
        # 清理断开的连接
        for user_id in disconnected_users:
            await self.disconnect(user_id)
    
    async def broadcast_presence_update(self, presence: UserPresence) -> None:
        """广播用户在线状态更新"""
        message = {
            "type": WebSocketMessageType.USER_PRESENCE_UPDATE,
            "data": presence.model_dump()
        }
        await self.broadcast(message)
    
    async def broadcast_task_update(self, task_update: TaskUpdate) -> None:
        """广播任务更新"""
        message = {
            "type": WebSocketMessageType.TASK_UPDATED,
            "data": task_update.model_dump()
        }
        await self.broadcast(message)
        
        # 同时发送给任务的观察者
        if task_update.task_id in self.task_watchers:
            for user_id in self.task_watchers[task_update.task_id]:
                await self.send_personal_message(user_id, message)
    
    async def broadcast_agent_update(self, agent_update: AgentUpdate) -> None:
        """广播代理状态更新"""
        message = {
            "type": WebSocketMessageType.AGENT_STATUS_CHANGED,
            "data": agent_update.model_dump()
        }
        await self.broadcast(message)
    
    async def send_notification(self, user_id: str, notification: Notification) -> None:
        """向特定用户发送通知"""
        message = {
            "type": WebSocketMessageType.NOTIFICATION,
            "data": notification.model_dump()
        }
        await self.send_personal_message(user_id, message)
    
    async def broadcast_notification(self, notification: Notification) -> None:
        """向所有用户广播通知"""
        message = {
            "type": WebSocketMessageType.NOTIFICATION,
            "data": notification.model_dump()
        }
        await self.broadcast(message)
    
    async def add_task_watcher(self, task_id: str, user_id: str) -> None:
        """添加任务观察者"""
        if task_id not in self.task_watchers:
            self.task_watchers[task_id] = set()
        self.task_watchers[task_id].add(user_id)
        
        logger.debug("task_watcher_added", task_id=task_id, user_id=user_id)
    
    async def remove_task_watcher(self, task_id: str, user_id: str) -> None:
        """移除任务观察者"""
        if task_id in self.task_watchers:
            self.task_watchers[task_id].discard(user_id)
            logger.debug("task_watcher_removed", task_id=task_id, user_id=user_id)
    
    async def get_online_users(self) -> list[UserPresence]:
        """获取当前在线用户列表"""
        return list(self.user_presence.values())
    
    async def update_user_presence(self, user_id: str, presence: UserPresence) -> None:
        """更新用户在线状态"""
        self.user_presence[user_id] = presence
        await self.broadcast_presence_update(presence)


# 全局连接管理器实例
manager = WebSocketConnectionManager()


# ============== WebSocket端点 ==============

@websocket_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str
) -> None:
    """
    增强的WebSocket端点
    
    支持的功能:
    - 用户在线状态管理
    - 任务实时更新
    - 代理状态同步
    - 通知推送
    - 任务观察
    """
    await manager.connect(websocket, user_id)
    
    try:
        # 发送当前在线用户列表
        await manager.send_personal_message(
            user_id,
            {
                "type": "initial_state",
                "data": {
                    "users": [u.model_dump() for u in await manager.get_online_users()]
                }
            }
        )
        
        # 消息处理循环
        while True:
            try:
                data = await websocket.receive_json()
                message_type = data.get("type")
                message_data = data.get("data", {})
                
                logger.debug(
                    "websocket_message_received",
                    user_id=user_id,
                    message_type=message_type
                )
                
                if message_type == WebSocketMessageType.HEARTBEAT:
                    # 心跳响应
                    await manager.send_personal_message(
                        user_id,
                        {
                            "type": WebSocketMessageType.HEARTBEAT,
                            "data": {"timestamp": datetime.utcnow().isoformat()}
                        }
                    )
                
                elif message_type == WebSocketMessageType.USER_PRESENCE_UPDATE:
                    # 用户状态更新
                    presence = UserPresence(**message_data)
                    await manager.update_user_presence(user_id, presence)
                
                elif message_type == WebSocketMessageType.TASK_WATCH:
                    # 开始观察任务
                    task_id = message_data.get("task_id")
                    if task_id:
                        await manager.add_task_watcher(task_id, user_id)
                
                elif message_type == WebSocketMessageType.TASK_UNWATCH:
                    # 停止观察任务
                    task_id = message_data.get("task_id")
                    if task_id:
                        await manager.remove_task_watcher(task_id, user_id)
            
            except WebSocketDisconnect:
                logger.info("websocket_client_disconnected", user_id=user_id)
                break
            except Exception as e:
                logger.error(
                    "websocket_message_processing_error",
                    user_id=user_id,
                    error=str(e)
                )
    
    finally:
        await manager.disconnect(user_id)


# ============== 辅助函数 ==============

async def notify_task_created(task: Task) -> None:
    """通知任务创建"""
    notification = Notification(
        type="info",
        title="新任务创建",
        message=f"任务 '{task.description[:50]}...' 已创建",
        data={"task_id": str(task.id)}
    )
    await manager.broadcast_notification(notification)
    
    task_update = TaskUpdate(
        task_id=str(task.id),
        status=TaskStatus.PENDING,
        message="任务已创建"
    )
    await manager.broadcast_task_update(task_update)


async def notify_task_updated(task: Task, progress: Optional[float] = None, 
                             message: Optional[str] = None) -> None:
    """通知任务更新"""
    task_update = TaskUpdate(
        task_id=str(task.id),
        status=task.status,
        progress=progress,
        agent_id=str(task.assigned_agent_id) if task.assigned_agent_id else None,
        message=message
    )
    await manager.broadcast_task_update(task_update)


async def notify_task_completed(task: Task, result: Any) -> None:
    """通知任务完成"""
    notification = Notification(
        type="success",
        title="任务完成",
        message=f"任务 '{task.description[:50]}...' 已成功完成",
        data={"task_id": str(task.id)},
        actionable=True,
        action_label="查看结果"
    )
    await manager.broadcast_notification(notification)
    
    task_update = TaskUpdate(
        task_id=str(task.id),
        status=TaskStatus.COMPLETED,
        result=result if isinstance(result, dict) else {"content": str(result)},
        progress=100.0,
        message="任务已完成"
    )
    await manager.broadcast_task_update(task_update)


async def notify_task_failed(task: Task, error: str) -> None:
    """通知任务失败"""
    notification = Notification(
        type="error",
        title="任务执行失败",
        message=f"任务 '{task.description[:50]}...' 执行失败: {error[:100]}",
        data={"task_id": str(task.id)}
    )
    await manager.broadcast_notification(notification)
    
    task_update = TaskUpdate(
        task_id=str(task.id),
        status=TaskStatus.FAILED,
        error=error,
        message="任务执行失败"
    )
    await manager.broadcast_task_update(task_update)


async def notify_agent_status_changed(agent: Agent) -> None:
    """通知代理状态变化"""
    agent_update = AgentUpdate(
        agent_id=str(agent.id),
        name=agent.name,
        status=agent.status,
        current_task_id=str(agent.current_task_id) if agent.current_task_id else None
    )
    await manager.broadcast_agent_update(agent_update)


async def send_user_notification(user_id: str, notification: Notification) -> None:
    """向特定用户发送通知"""
    await manager.send_notification(user_id, notification)
