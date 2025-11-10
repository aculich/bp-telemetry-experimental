#!/usr/bin/env python3
"""
Run the Blueplane Telemetry Core server.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blueplane.fast_path.consumer import FastPathConsumer
from blueplane.config import config


async def main():
    """Run the fast path consumer."""
    print(f"Starting Blueplane Telemetry Core server...")
    print(f"  Data directory: {config.data_dir}")
    print(f"  Database: {config.db_path}")
    print(f"  Redis: {config.redis_host}:{config.redis_port}")
    print(f"  Stream: {config.mq_stream_name}")
    print()
    
    consumer = FastPathConsumer()
    
    try:
        await consumer.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        consumer.stop()
        consumer.close()


if __name__ == "__main__":
    asyncio.run(main())

