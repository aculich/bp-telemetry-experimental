"""
WebSocket endpoints for real-time telemetry updates.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any
import asyncio
import json

from ..storage.redis_metrics import RedisMetricsStorage
from ..storage.sqlite_conversations import ConversationStorage


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and store WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        message_json = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()
metrics_storage = RedisMetricsStorage()
conversation_storage = ConversationStorage()


async def metrics_stream(websocket: WebSocket):
    """
    Stream real-time metrics updates.
    
    Sends metrics updates every second.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Get latest metrics
            realtime = metrics_storage.get_latest_metrics(category="realtime")
            session = metrics_storage.get_latest_metrics(category="session")
            tools = metrics_storage.get_latest_metrics(category="tools")
            
            message = {
                "type": "metrics",
                "timestamp": asyncio.get_event_loop().time(),
                "data": {
                    "realtime": realtime,
                    "session": session,
                    "tools": tools,
                },
            }
            
            await websocket.send_json(message)
            await asyncio.sleep(1)  # Update every second
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Error in metrics stream: {e}")
        manager.disconnect(websocket)


async def events_stream(websocket: WebSocket):
    """
    Stream real-time event updates.
    
    Placeholder for future event streaming.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Placeholder - would stream events as they're processed
            message = {
                "type": "event",
                "timestamp": asyncio.get_event_loop().time(),
                "data": {},
            }
            
            await websocket.send_json(message)
            await asyncio.sleep(5)  # Update every 5 seconds (placeholder)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Error in events stream: {e}")
        manager.disconnect(websocket)

