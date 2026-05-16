from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional, Any
from datetime import datetime
import json
import asyncio
import structlog
from enum import Enum

logger = structlog.get_logger()

class MessageType(str, Enum):
    AGENT_STATUS_CHANGE = "agent_status_change"
    TASK_CREATED = "task_created"
    TASK_STATUS_CHANGE = "task_status_change"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CLUSTER_STATS_UPDATE = "cluster_stats_update"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

class ConnectionState(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATED = "authenticated"

class WebSocketConnection:
    """Represents a single WebSocket connection."""
    
    def __init__(self, websocket: WebSocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.state = ConnectionState.CONNECTED
        self.subscriptions: Set[str] = set()
        self.user_id: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
    
    async def send_json(self, data: dict):
        """Send JSON message to client."""
        try:
            await self.websocket.send_json(data)
            return True
        except Exception as e:
            logger.error("websocket_send_error", client_id=self.client_id, error=str(e))
            return False
    
    async def send_message(self, message_type: MessageType, data: Any = None, message: str = ""):
        """Send a structured message to client."""
        return await self.send_json({
            "type": message_type.value,
            "data": data,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def update_heartbeat(self):
        """Update last heartbeat timestamp."""
        self.last_heartbeat = datetime.utcnow()
    
    def subscribe(self, channel: str):
        """Subscribe to a channel."""
        self.subscriptions.add(channel)
        logger.debug("client_subscribed", client_id=self.client_id, channel=channel)
    
    def unsubscribe(self, channel: str):
        """Unsubscribe from a channel."""
        self.subscriptions.discard(channel)
        logger.debug("client_unsubscribed", client_id=self.client_id, channel=channel)

class WebSocketManager:
    """Manages all WebSocket connections and message broadcasting."""
    
    def __init__(self):
        self._connections: Dict[str, WebSocketConnection] = {}
        self._client_counter = 0
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def connect(self, websocket: WebSocket) -> WebSocketConnection:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        async with self._lock:
            self._client_counter += 1
            client_id = f"client_{self._client_counter}"
            connection = WebSocketConnection(websocket, client_id)
            self._connections[client_id] = connection
        
        logger.info("websocket_connected", client_id=client_id)
        
        await self._send_welcome(connection)
        
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_checker())
        
        return connection
    
    async def disconnect(self, client_id: str):
        """Disconnect and cleanup a WebSocket connection."""
        async with self._lock:
            if client_id in self._connections:
                del self._connections[client_id]
                logger.info("websocket_disconnected", client_id=client_id)
    
    async def _send_welcome(self, connection: WebSocketConnection):
        """Send welcome message to new connection."""
        await connection.send_message(
            MessageType.NOTIFICATION,
            data={"client_id": connection.client_id},
            message="Connected to Agent Cluster WebSocket"
        )
    
    async def _heartbeat_checker(self):
        """Periodically check and cleanup stale connections."""
        while True:
            try:
                await asyncio.sleep(30)
                await self._cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("heartbeat_checker_error", error=str(e))
    
    async def _cleanup_stale_connections(self):
        """Remove connections that haven't sent heartbeat."""
        now = datetime.utcnow()
        stale_threshold = 120
        
        async with self._lock:
            stale_clients = [
                client_id for client_id, conn in self._connections.items()
                if (now - conn.last_heartbeat).total_seconds() > stale_threshold
            ]
            
            for client_id in stale_clients:
                await self._force_disconnect(client_id)
    
    async def _force_disconnect(self, client_id: str):
        """Force disconnect a client."""
        if client_id in self._connections:
            connection = self._connections[client_id]
            try:
                await connection.websocket.close()
            except Exception:
                pass
            del self._connections[client_id]
            logger.warning("client_force_disconnected", client_id=client_id)
    
    async def broadcast(
        self,
        message_type: MessageType,
        data: Any = None,
        message: str = "",
        channel: Optional[str] = None
    ):
        """Broadcast message to all connected clients or specific channel."""
        payload = {
            "type": message_type.value,
            "data": data,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async with self._lock:
            disconnected = []
            
            for client_id, connection in self._connections.items():
                if channel and channel not in connection.subscriptions:
                    continue
                
                success = await connection.send_json(payload)
                if not success:
                    disconnected.append(client_id)
            
            for client_id in disconnected:
                del self._connections[client_id]
    
    async def send_to_client(
        self,
        client_id: str,
        message_type: MessageType,
        data: Any = None,
        message: str = ""
    ):
        """Send message to a specific client."""
        async with self._lock:
            connection = self._connections.get(client_id)
        
        if connection:
            await connection.send_message(message_type, data, message)
    
    async def handle_message(self, client_id: str, data: dict):
        """Handle incoming message from client."""
        async with self._lock:
            connection = self._connections.get(client_id)
        
        if not connection:
            return
        
        message_type = data.get("type")
        
        if message_type == "subscribe":
            channel = data.get("channel")
            if channel:
                connection.subscribe(channel)
                await connection.send_message(
                    MessageType.NOTIFICATION,
                    message=f"Subscribed to {channel}"
                )
        
        elif message_type == "unsubscribe":
            channel = data.get("channel")
            if channel:
                connection.unsubscribe(channel)
                await connection.send_message(
                    MessageType.NOTIFICATION,
                    message=f"Unsubscribed from {channel}"
                )
        
        elif message_type == "heartbeat":
            connection.update_heartbeat()
            await connection.send_message(MessageType.HEARTBEAT)
        
        elif message_type == "authenticate":
            token = data.get("token")
            if token:
                connection.user_id = token
                connection.state = ConnectionState.AUTHENTICATED
                await connection.send_message(
                    MessageType.NOTIFICATION,
                    message="Authenticated successfully"
                )
    
    def get_stats(self) -> dict:
        """Get WebSocket connection statistics."""
        return {
            "total_connections": len(self._connections),
            "subscriptions": sum(len(c.subscriptions) for c in self._connections.values())
        }

ws_manager = WebSocketManager()
