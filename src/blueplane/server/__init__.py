"""
Layer 2 server components (REST API and WebSocket).
"""

from .api import app, create_app
from .websocket import manager, metrics_stream, events_stream

__all__ = [
    "app",
    "create_app",
    "manager",
    "metrics_stream",
    "events_stream",
]

