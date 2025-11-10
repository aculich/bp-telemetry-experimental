"""
Configuration management for Blueplane Telemetry Core.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class Config:
    """Main configuration class."""
    
    # Data directory
    data_dir: Path = Path.home() / ".blueplane"
    db_path: Path = data_dir / "telemetry.db"
    
    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Fast path configuration
    fast_path_batch_size: int = 100
    fast_path_batch_timeout_ms: int = 100
    compression_level: int = 6  # zlib level 6 achieves 7-10x compression
    
    # Slow path configuration
    metrics_workers: int = 2
    conversation_workers: int = 2
    ai_insights_workers: int = 1
    
    # Redis Streams configuration
    mq_stream_name: str = "telemetry:events"
    mq_consumer_group: str = "processors"
    cdc_stream_name: str = "cdc:events"
    cdc_consumer_group: str = "workers"
    dlq_stream_name: str = "telemetry:dlq"
    
    # Server configuration
    server_host: str = "localhost"
    server_port: int = 7531
    api_prefix: str = "/api/v1"
    
    # Retention
    raw_trace_retention_days: int = 90
    
    def __post_init__(self):
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            data_dir=Path(os.getenv("BLUEPLANE_DATA_DIR", str(Path.home() / ".blueplane"))),
            redis_host=os.getenv("BLUEPLANE_REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("BLUEPLANE_REDIS_PORT", "6379")),
            redis_db=int(os.getenv("BLUEPLANE_REDIS_DB", "0")),
            fast_path_batch_size=int(os.getenv("BLUEPLANE_BATCH_SIZE", "100")),
            server_host=os.getenv("BLUEPLANE_HOST", "localhost"),
            server_port=int(os.getenv("BLUEPLANE_PORT", "7531")),
        )


# Global config instance
config = Config.from_env()

