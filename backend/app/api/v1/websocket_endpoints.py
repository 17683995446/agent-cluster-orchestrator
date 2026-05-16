from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import json
from app.websocket.websocket_connection_manager import ws_manager, WebSocketConnection, MessageType
from app.security.jwt_authentication import jwt_manager
import structlog

logger = structlog.get_logger()

router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time communication.
    
    Connect with: ws://host/ws?token=<jwt_token>
    
    Client can send messages:
    - {"type": "subscribe", "channel": "agents"}
    - {"type": "unsubscribe", "channel": "agents"}
    - {"type": "heartbeat"}
    - {"type": "authenticate", "token": "<jwt>"}
    """
    connection = await ws_manager.connect(websocket)
    
    if token:
        payload = jwt_manager.verify_access_token(token)
        if payload:
            connection.user_id = payload.get("sub")
            connection.state = "authenticated"
            logger.info("websocket_authenticated", client_id=connection.client_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await ws_manager.handle_message(connection.client_id, message)
            except json.JSONDecodeError:
                await connection.send_message(
                    MessageType.ERROR,
                    message="Invalid JSON format"
                )
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(connection.client_id)
        logger.info("websocket_client_disconnected", client_id=connection.client_id)
    except Exception as e:
        logger.error("websocket_error", client_id=connection.client_id, error=str(e))
        await ws_manager.disconnect(connection.client_id)

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    channels: Optional[str] = Query("default")
):
    """
    WebSocket endpoint for streaming task execution results.
    
    Connect with: ws://host/ws/stream?channels=task_progress,notifications
    """
    connection = await ws_manager.connect(websocket)
    
    if channels:
        for channel in channels.split(","):
            connection.subscribe(channel.strip())
    
    try:
        await connection.send_message(
            MessageType.NOTIFICATION,
            data={"channels": channels.split(",") if channels else []},
            message=f"Subscribed to channels: {channels}"
        )
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await ws_manager.handle_message(connection.client_id, message)
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(connection.client_id)
    except Exception as e:
        logger.error("websocket_stream_error", error=str(e))
        await ws_manager.disconnect(connection.client_id)

@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return ws_manager.get_stats()
