#!/usr/bin/env python3
"""
Run the Blueplane Telemetry Core server.
Starts both fast path consumer and slow path workers.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blueplane.fast_path.consumer import FastPathConsumer
from blueplane.slow_path.worker_pool import WorkerPoolManager
from blueplane.config import config


async def main():
    """Run both fast path consumer and slow path workers."""
    print("Starting Blueplane Telemetry Core server...")
    print(f"  Data directory: {config.data_dir}")
    print(f"  Database: {config.db_path}")
    print(f"  Redis: {config.redis_host}:{config.redis_port}")
    print(f"  Stream: {config.mq_stream_name}")
    print(f"  CDC Stream: {config.cdc_stream_name}")
    print()
    
    # Start fast path consumer
    consumer = FastPathConsumer()
    fast_path_task = asyncio.create_task(consumer.run())
    
    # Start slow path workers
    worker_pool = WorkerPoolManager()
    await worker_pool.start()
    
    print("\n✅ Server started successfully!")
    print("   Fast path: Processing events from message queue")
    print("   Slow path: Enriching events and calculating metrics")
    print("\nPress Ctrl+C to stop...\n")
    
    try:
        # Wait for both tasks
        await asyncio.gather(fast_path_task, worker_pool.wait_for_completion())
    except KeyboardInterrupt:
        print("\nShutting down...")
        consumer.stop()
        worker_pool.stop()
        await worker_pool.wait_for_completion()
        consumer.close()
        worker_pool.close()
        print("✅ Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

