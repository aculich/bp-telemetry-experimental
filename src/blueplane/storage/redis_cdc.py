"""
Redis Streams for CDC event distribution.
Connects fast path to slow path workers.
"""

import asyncio
import json
import redis
from typing import AsyncGenerator, Dict, Optional
from datetime import datetime

from ..config import config


class CDCWorkQueue:
    """
    Redis Streams for CDC event distribution.
    Connects fast path to slow path workers.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize Redis connection and consumer group."""
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                decode_responses=True,
            )
        
        self.stream_key = config.cdc_stream_name
        self.consumer_group = config.cdc_consumer_group
        self.max_stream_length = 100000

    async def initialize(self) -> None:
        """
        Setup Redis connection and consumer group.
        
        - Connect to Redis
        - Create consumer group with XGROUP CREATE
        - Set stream position to '0' (start from beginning)
        """
        try:
            # Try to create consumer group (may fail if it already exists)
            self.redis.xgroup_create(
                name=self.stream_key,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
        except redis.exceptions.ResponseError as e:
            # Group already exists, that's fine
            if "BUSYGROUP" not in str(e):
                raise

    def publish(self, event: Dict) -> None:
        """
        Publish CDC event from fast path (fire-and-forget).
        
        - Serialize event to JSON
        - Execute XADD with MAXLEN approximate trim
        - Silently fail on error (don't block fast path)
        """
        try:
            event_json = json.dumps(event, default=str)
            self.redis.xadd(
                name=self.stream_key,
                fields={"event": event_json},
                maxlen=self.max_stream_length,
                approximate=True,
            )
        except Exception:
            # Silently fail - CDC failures don't affect fast path
            pass

    async def consume(
        self, consumer_name: str, count: int = 1, block: int = 1000
    ) -> AsyncGenerator[tuple[str, Dict], None]:
        """
        Consume events for slow path workers.
        
        - Execute XREADGROUP with block timeout
        - Yield (message_id, event) pairs
        - Blocks until events available
        """
        while True:
            try:
                # XREADGROUP: read from stream for this consumer
                messages = self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=consumer_name,
                    streams={self.stream_key: ">"},  # Read new messages
                    count=count,
                    block=block,
                )
                
                if not messages:
                    continue
                
                # Parse messages
                stream_name, message_list = messages[0]
                for message_id, fields in message_list:
                    event_json = fields.get("event", "{}")
                    event = json.loads(event_json)
                    yield (message_id, event)
                    
            except Exception as e:
                # Log error but continue
                print(f"Error consuming CDC events: {e}")
                await asyncio.sleep(1)  # Wait before retrying

    async def acknowledge(self, message_id: str) -> None:
        """Mark message as processed with XACK."""
        try:
            self.redis.xack(self.stream_key, self.consumer_group, message_id)
        except Exception:
            pass  # Silently fail

    async def get_queue_stats(self) -> Dict:
        """
        Monitor queue depth and lag.
        
        - Execute XINFO STREAM for stream stats
        - Execute XPENDING for pending message count
        - Calculate lag from oldest message timestamp
        - Return stats dict
        """
        try:
            # Get stream info
            info = self.redis.xinfo_stream(self.stream_key)
            length = info.get("length", 0)
            
            # Get pending messages
            pending = self.redis.xpending_range(
                name=self.stream_key,
                groupname=self.consumer_group,
                min="-",
                max="+",
                count=1,
            )
            
            pending_count = len(pending)
            oldest_pending = pending[0]["time_since_delivered"] if pending else 0
            
            return {
                "queue_length": length,
                "pending_count": pending_count,
                "oldest_pending_ms": oldest_pending,
            }
        except Exception:
            return {
                "queue_length": 0,
                "pending_count": 0,
                "oldest_pending_ms": 0,
            }

    def close(self) -> None:
        """Close Redis connection."""
        self.redis.close()

