"""
Redis TimeSeries for real-time metrics.
"""

import redis
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from ..config import config


class RedisMetricsStorage:
    """Redis TimeSeries for real-time metrics."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize Redis connection."""
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                decode_responses=False,  # Keep binary for TimeSeries
            )
        
        self._initialize_time_series()

    def _initialize_time_series(self) -> None:
        """
        Initialize time series with retention policies.
        
        - Create TS.CREATE for each metric with retention and labels
        - Create aggregation rules (1m, 5m, 1h)
        - Set duplicate policy to LAST
        """
        # Note: Redis TimeSeries module may not be available
        # For now, we'll use regular Redis structures as fallback
        # In production, use RedisTimeSeries if available
        
        metrics_config = {
            "realtime": {
                "active_sessions": {"retention": 3600000, "type": "gauge"},  # 1 hour
                "events_per_second": {"retention": 3600000, "type": "counter"},
                "current_latency": {"retention": 3600000, "type": "gauge"},
            },
            "session": {
                "acceptance_rate": {"retention": 604800000, "type": "gauge"},  # 7 days
                "productivity_score": {"retention": 604800000, "type": "gauge"},
                "error_rate": {"retention": 604800000, "type": "gauge"},
                "tokens_per_minute": {"retention": 604800000, "type": "counter"},
            },
            "tools": {
                "tool_latency_p50": {"retention": 86400000, "type": "gauge"},  # 1 day
                "tool_latency_p95": {"retention": 86400000, "type": "gauge"},
                "tool_latency_p99": {"retention": 86400000, "type": "gauge"},
                "tool_success_rate": {"retention": 86400000, "type": "gauge"},
            },
        }
        
        # Try to initialize TimeSeries, fallback to regular Redis if not available
        try:
            for category, metrics in metrics_config.items():
                for name, config_data in metrics.items():
                    key = f"metric:{category}:{name}"
                    try:
                        # Try to create TimeSeries
                        self.redis.execute_command(
                            "TS.CREATE",
                            key,
                            "RETENTION", config_data["retention"],
                            "DUPLICATE_POLICY", "LAST",
                        )
                    except redis.exceptions.ResponseError:
                        # TimeSeries module not available, use regular Redis
                        # We'll use sorted sets for time-series data
                        pass
        except Exception:
            # Fallback: use regular Redis structures
            pass

    def record_metric(
        self, category: str, name: str, value: float, timestamp: Optional[float] = None
    ) -> None:
        """
        Record single metric value.
        
        - Build key: metric:{category}:{name}
        - Execute TS.ADD with timestamp and value
        """
        key = f"metric:{category}:{name}"
        ts = timestamp or datetime.utcnow().timestamp() * 1000  # milliseconds
        
        try:
            # Try TimeSeries first
            self.redis.execute_command("TS.ADD", key, int(ts), value)
        except (redis.exceptions.ResponseError, AttributeError):
            # Fallback: use sorted set
            self.redis.zadd(key, {str(value): ts})
            # Trim to keep only recent data (last 1000 points)
            self.redis.zremrangebyrank(key, 0, -1001)

    def get_metric_range(
        self,
        category: str,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: Optional[str] = None,
    ) -> List[Tuple[float, float]]:
        """
        Get metric values for time range.
        
        - Use aggregated key if aggregation specified
        - Execute TS.RANGE with time bounds
        - Return list of (timestamp, value) tuples
        """
        key = f"metric:{category}:{name}"
        
        if aggregation:
            key = f"{key}:{aggregation}"
        
        start_ts = int(start_time.timestamp() * 1000) if start_time else "-"
        end_ts = int(end_time.timestamp() * 1000) if end_time else "+"
        
        try:
            # Try TimeSeries
            result = self.redis.execute_command("TS.RANGE", key, start_ts, end_ts)
            return [(item[0], item[1]) for item in result]
        except (redis.exceptions.ResponseError, AttributeError):
            # Fallback: use sorted set
            start_score = int(start_time.timestamp() * 1000) if start_time else 0
            end_score = int(end_time.timestamp() * 1000) if end_time else float("inf")
            
            items = self.redis.zrangebyscore(key, start_score, end_score, withscores=True)
            return [(score, float(value)) for value, score in items]

    def get_latest_metrics(self, category: Optional[str] = None) -> Dict[str, float]:
        """
        Get latest values for dashboard display.
        
        - Pattern match metric keys
        - Execute TS.GET for each key
        - Return dict of metric_name -> latest_value
        """
        pattern = f"metric:{category}:*" if category else "metric:*"
        
        metrics = {}
        try:
            keys = self.redis.keys(pattern)
            for key in keys:
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                try:
                    # Try TimeSeries GET
                    result = self.redis.execute_command("TS.GET", key)
                    if result:
                        metrics[key_str] = result[1]  # (timestamp, value)
                except (redis.exceptions.ResponseError, AttributeError):
                    # Fallback: get latest from sorted set
                    items = self.redis.zrange(key, -1, -1, withscores=True)
                    if items:
                        metrics[key_str] = float(items[0][0])
        except Exception:
            pass
        
        return metrics

    def increment_counter(self, category: str, name: str, amount: int = 1) -> None:
        """Increment a counter metric."""
        key = f"metric:{category}:{name}"
        self.redis.incrby(key, amount)
        # Set expiry for counters (1 hour default)
        self.redis.expire(key, 3600)

    def set_gauge(self, category: str, name: str, value: float) -> None:
        """Set a gauge metric."""
        key = f"metric:{category}:{name}"
        self.redis.set(key, value)
        # Set expiry for gauges (1 hour default)
        self.redis.expire(key, 3600)

    def get_gauge(self, category: str, name: str) -> Optional[float]:
        """Get a gauge metric value."""
        key = f"metric:{category}:{name}"
        value = self.redis.get(key)
        return float(value) if value else None

    def close(self) -> None:
        """Close Redis connection."""
        self.redis.close()

