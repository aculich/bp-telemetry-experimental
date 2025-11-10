#!/usr/bin/env python3
"""
Test script to verify Blueplane Telemetry Core setup.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import redis
from blueplane.config import config
from blueplane.storage.sqlite_traces import SQLiteTraceStorage
from blueplane.storage.sqlite_conversations import ConversationStorage


def test_redis():
    """Test Redis connection."""
    print("Testing Redis connection...")
    try:
        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
        r.ping()
        print("  ✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        print(f"     Make sure Redis is running on {config.redis_host}:{config.redis_port}")
        return False


def test_sqlite():
    """Test SQLite database."""
    print("Testing SQLite database...")
    try:
        storage = SQLiteTraceStorage()
        conv_storage = ConversationStorage()
        print(f"  ✅ SQLite database initialized at {config.db_path}")
        storage.close()
        conv_storage.close()
        return True
    except Exception as e:
        print(f"  ❌ SQLite initialization failed: {e}")
        return False


def test_redis_streams():
    """Test Redis Streams setup."""
    print("Testing Redis Streams...")
    try:
        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
        
        # Try to create consumer group (may fail if exists, that's OK)
        try:
            r.xgroup_create(
                name=config.mq_stream_name,
                groupname=config.mq_consumer_group,
                id="0",
                mkstream=True,
            )
            print(f"  ✅ Created consumer group '{config.mq_consumer_group}'")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"  ✅ Consumer group '{config.mq_consumer_group}' already exists")
            else:
                raise
        
        # Try to create CDC stream consumer group
        try:
            r.xgroup_create(
                name=config.cdc_stream_name,
                groupname=config.cdc_consumer_group,
                id="0",
                mkstream=True,
            )
            print(f"  ✅ Created CDC consumer group '{config.cdc_consumer_group}'")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"  ✅ CDC consumer group '{config.cdc_consumer_group}' already exists")
            else:
                raise
        
        return True
    except Exception as e:
        print(f"  ❌ Redis Streams setup failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Blueplane Telemetry Core - Setup Test\n")
    
    results = []
    results.append(("Redis", test_redis()))
    results.append(("SQLite", test_sqlite()))
    results.append(("Redis Streams", test_redis_streams()))
    
    print("\n" + "=" * 50)
    print("Summary:")
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n✅ All tests passed! System is ready.")
        return 0
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

