"""
Publishes change data capture events to Redis Streams.
Fire-and-forget pattern for maximum throughput.
"""

import json
import redis
from typing import Dict, Optional

from ..config import config


class CDCPublisher:
    """
    Publishes change data capture events to Redis Streams.
    Fire-and-forget pattern for maximum throughput.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize CDC publisher."""
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
        self.max_stream_length = 100000

    def publish(self, event: Dict) -> None:
        """
        Publish CDC event to Redis Stream (fire-and-forget).
        
        - Connect to Redis (lazy initialization)
        - XADD with MAXLEN=100000, approximate=True
        - Serialize event to JSON
        - Log warning on error but don't block
        - CDC failures don't affect fast path
        """
        try:
            event_json = json.dumps(event, default=str)
            self.redis.xadd(
                name=self.stream_key,
                fields={"event": event_json},
                maxlen=self.max_stream_length,
                approximate=True,
            )
        except Exception as e:
            # Silently fail - CDC failures don't affect fast path
            # In production, we might want to log this
            pass

    def close(self) -> None:
        """Close Redis connection."""
        self.redis.close()

