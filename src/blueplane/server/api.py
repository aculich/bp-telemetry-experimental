"""
Layer 2 REST API server.
Provides access to processed data (conversations and metrics).
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from fastapi import WebSocket

from ..config import config
from ..storage.sqlite_conversations import ConversationStorage
from ..storage.redis_metrics import RedisMetricsStorage
from .websocket import metrics_stream, events_stream


# Pydantic models for API responses
class ConversationSummary(BaseModel):
    id: str
    session_id: str
    external_session_id: str
    platform: str
    started_at: str
    ended_at: Optional[str]
    interaction_count: int
    acceptance_rate: Optional[float]
    total_tokens: int
    total_changes: int


class MetricValue(BaseModel):
    name: str
    value: float
    timestamp: Optional[float] = None


class MetricsResponse(BaseModel):
    realtime: Dict[str, float]
    session: Dict[str, float]
    tools: Dict[str, float]


# Initialize FastAPI app
app = FastAPI(
    title="Blueplane Telemetry Core API",
    description="REST API for accessing telemetry data",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage
conversation_storage = ConversationStorage()
metrics_storage = RedisMetricsStorage()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Blueplane Telemetry Core API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/api/v1/metrics", response_model=MetricsResponse)
async def get_metrics(
    category: Optional[str] = Query(None, description="Metric category (realtime, session, tools)"),
    time_range: Optional[str] = Query("1h", description="Time range (e.g., 1h, 24h, 7d)"),
) -> MetricsResponse:
    """
    Get current metrics.
    
    Returns metrics from Redis for dashboard display.
    """
    try:
        if category:
            metrics = metrics_storage.get_latest_metrics(category=category)
        else:
            # Get all categories
            realtime = metrics_storage.get_latest_metrics(category="realtime")
            session = metrics_storage.get_latest_metrics(category="session")
            tools = metrics_storage.get_latest_metrics(category="tools")
            
            # If no metrics in Redis, calculate from conversations
            if not session and not tools:
                global_metrics = conversation_storage.get_global_acceptance_metrics()
                if global_metrics:
                    avg_acceptance = global_metrics.get("avg_acceptance_rate", 0) or 0
                    total_convs = global_metrics.get("total_conversations", 0) or 0
                    total_changes = global_metrics.get("total_changes", 0) or 0
                    
                    # Calculate time saved (rough estimate: 5 min per accepted change)
                    time_saved_hours = (total_changes * 5) / 60.0
                    
                    session = {
                        "acceptance_rate": float(avg_acceptance) if avg_acceptance else 0,
                        "total_conversations": int(total_convs) if total_convs else 0,
                        "total_changes": int(total_changes) if total_changes else 0,
                        "time_saved_hours": time_saved_hours,
                    }
                    
                    # Calculate tool usage from conversations
                    # Get all conversations and count tool usage
                    all_convs = conversation_storage.get_all_conversations(limit=1000)
                    tool_counts = {}
                    for conv in all_convs:
                        # Get turns for this conversation
                        conv_id = conv.get("id")
                        if conv_id:
                            cursor = conversation_storage.conn.execute("""
                                SELECT metadata FROM conversation_turns
                                WHERE conversation_id = ? AND turn_type = 'tool_use'
                            """, (conv_id,))
                            for row in cursor:
                                import json
                                metadata = json.loads(row["metadata"] or "{}")
                                tool_name = metadata.get("tool", "Unknown")
                                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                    
                    if tool_counts:
                        tools = tool_counts
            
            return MetricsResponse(
                realtime=realtime,
                session=session,
                tools=tools,
            )
        
        # If single category requested
        if category == "realtime":
            return MetricsResponse(realtime=metrics, session={}, tools={})
        elif category == "session":
            return MetricsResponse(realtime={}, session=metrics, tools={})
        elif category == "tools":
            return MetricsResponse(realtime={}, session={}, tools=metrics)
        else:
            return MetricsResponse(realtime={}, session={}, tools={})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")


@app.get("/api/v1/metrics/{category}/{name}")
async def get_metric_range(
    category: str,
    name: str,
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    aggregation: Optional[str] = Query(None, description="Aggregation (1m, 5m, 1h)"),
) -> List[MetricValue]:
    """
    Get metric values for a time range.
    """
    try:
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        if not start_dt:
            # Default to last hour
            end_dt = end_dt or datetime.utcnow()
            start_dt = end_dt - timedelta(hours=1)
        
        values = metrics_storage.get_metric_range(
            category=category,
            name=name,
            start_time=start_dt,
            end_time=end_dt,
            aggregation=aggregation,
        )
        
        return [
            MetricValue(name=name, value=value, timestamp=timestamp)
            for timestamp, value in values
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metric range: {str(e)}")


@app.get("/api/v1/sessions", response_model=List[ConversationSummary])
async def list_sessions(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    limit: int = Query(100, description="Maximum number of sessions to return"),
    offset: int = Query(0, description="Offset for pagination"),
) -> List[ConversationSummary]:
    """
    List all sessions.
    
    Returns conversation summaries for Layer 3 access.
    """
    try:
        conversations = conversation_storage.get_all_conversations(
            limit=limit,
            offset=offset,
            platform=platform,
        )
        
        result = []
        for conv in conversations:
            # Convert string values to proper types
            ended_at = conv.get("ended_at")
            if ended_at == "None" or ended_at is None:
                ended_at = None
            else:
                ended_at = str(ended_at)
            
            acceptance_rate = conv.get("acceptance_rate")
            if acceptance_rate == "None" or acceptance_rate is None:
                acceptance_rate = None
            else:
                acceptance_rate = float(acceptance_rate)
            
            interaction_count = conv.get("interaction_count", 0)
            if isinstance(interaction_count, str):
                interaction_count = int(interaction_count) if interaction_count != "None" else 0
            
            total_tokens = conv.get("total_tokens", 0)
            if isinstance(total_tokens, str):
                total_tokens = int(total_tokens) if total_tokens != "None" else 0
            
            total_changes = conv.get("total_changes", 0)
            if isinstance(total_changes, str):
                total_changes = int(total_changes) if total_changes != "None" else 0
            
            result.append(ConversationSummary(
                id=str(conv.get("id", "")),
                session_id=str(conv.get("session_id", "")),
                external_session_id=str(conv.get("external_session_id", "")),
                platform=str(conv.get("platform", "unknown")),
                started_at=str(conv.get("started_at", "")),
                ended_at=ended_at,
                interaction_count=interaction_count,
                acceptance_rate=acceptance_rate,
                total_tokens=total_tokens,
                total_changes=total_changes,
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """
    Get session details.
    
    Returns all conversations for a session.
    """
    try:
        conversations = conversation_storage.get_conversations_by_session(session_id)
        return {
            "session_id": session_id,
            "conversations": conversations,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching session: {str(e)}")


@app.get("/api/v1/sessions/{session_id}/analysis")
async def analyze_session(session_id: str) -> Dict[str, Any]:
    """
    Get deep analysis for a session.
    
    Returns aggregated metrics and insights.
    """
    try:
        conversations = conversation_storage.get_conversations_by_session(session_id)
        
        # Calculate aggregated metrics
        total_conversations = len(conversations)
        total_interactions = sum(c.get("interaction_count", 0) for c in conversations)
        avg_acceptance_rate = sum(
            c.get("acceptance_rate", 0) or 0 for c in conversations
        ) / total_conversations if total_conversations > 0 else 0
        
        return {
            "session_id": session_id,
            "total_conversations": total_conversations,
            "total_interactions": total_interactions,
            "avg_acceptance_rate": avg_acceptance_rate,
            "conversations": conversations,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing session: {str(e)}")


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Get complete conversation flow.
    
    Returns conversation with turns and code changes.
    """
    try:
        conversation = conversation_storage.get_conversation_flow(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conversation: {str(e)}")


@app.get("/api/v1/insights")
async def get_insights() -> Dict[str, Any]:
    """
    Get AI-powered insights.
    
    Returns workflow optimization suggestions.
    """
    try:
        # Get global acceptance metrics
        metrics = conversation_storage.get_global_acceptance_metrics()
        
        # Get acceptance statistics
        stats = conversation_storage.get_acceptance_statistics(time_range="7d")
        
        return {
            "global_metrics": metrics,
            "trends": stats,
            "insights": [
                "Your acceptance rate is improving over time",
                "Consider optimizing tool usage patterns",
            ],  # Placeholder
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching insights: {str(e)}")


@app.get("/api/v1/export")
async def export_data(
    format: str = Query("json", description="Export format (json, csv)"),
    time_range: str = Query("7d", description="Time range"),
) -> Dict[str, Any]:
    """
    Export telemetry data.
    
    Returns data in requested format.
    """
    try:
        # Get acceptance statistics
        stats = conversation_storage.get_acceptance_statistics(time_range=time_range)
        
        if format == "csv":
            # Convert to CSV format
            csv_lines = ["date,conversation_count,avg_acceptance_rate,total_changes"]
            for stat in stats:
                csv_lines.append(
                    f"{stat['date']},{stat['conversation_count']},"
                    f"{stat.get('avg_acceptance_rate', 0)},{stat.get('total_changes', 0)}"
                )
            return {"format": "csv", "data": "\n".join(csv_lines)}
        else:
            return {"format": "json", "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting data: {str(e)}")


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics streaming."""
    await metrics_stream(websocket)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming."""
    await events_stream(websocket)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        # Check database connection
        conversation_storage.conn.execute("SELECT 1")
        
        # Check Redis connection
        metrics_storage.redis.ping()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    return app

