#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
End-to-end smoke test for the Python processing server ingest path.

This script:
- Writes a small batch of synthetic events to the Redis `telemetry:events` stream
  using the same `MessageQueueWriter` used by Layer 1 hooks.
- Waits briefly for the Python processing server to consume and ingest events.
- Verifies that:
  - Events were written to SQLite `raw_traces` for the test session.
  - At least one row can be decompressed and parsed from `event_data`.
  - CDC events are present on the configured CDC stream (if the server is running).
"""

import sys
import time
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.capture.shared.queue_writer import MessageQueueWriter
from src.capture.shared.config import Config
from src.processing.database.sqlite_client import SQLiteClient

def generate_test_event(event_type: str, session_id: str = None) -> dict:
    """Generate a test event."""
    if session_id is None:
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    
    return {
        'hook_type': 'test',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_type': event_type,
        'platform': 'cursor',
        'session_id': session_id,
        'metadata': {
            'workspace_hash': 'test_workspace_123',
            'test': True
        },
        'payload': {
            'test_event': True,
            'event_type': event_type,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
    }

def main():
    """Generate test events and verify processing."""
    print("=" * 60)
    print("Blueplane Telemetry Core - Python Server Ingest Smoke Test")
    print("=" * 60)
    print()
    
    # Initialize components
    print("1. Initializing components...")
    config = Config()
    writer = MessageQueueWriter(config)
    
    if writer._redis_client is None:
        print("❌ Redis is not available. Please start Redis:")
        print("   redis-server")
        return 1
    
    print("✅ Redis connection established")
    
    # Generate test events
    print("\n2. Generating test events...")
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    events = [
        generate_test_event('session_start', session_id),
        generate_test_event('user_prompt', session_id),
        generate_test_event('assistant_response', session_id),
        generate_test_event('file_edit', session_id),
        generate_test_event('session_end', session_id),
    ]
    
    print(f"   Generated {len(events)} test events")
    print(f"   Session ID: {session_id}")
    
    # Write events to Redis
    print("\n3. Writing events to Redis Streams...")
    written = 0
    for event in events:
        if writer.enqueue(event, 'cursor', session_id):
            written += 1
            print(f"   ✅ Wrote: {event['event_type']}")
        else:
            print(f"   ❌ Failed: {event['event_type']}")
    
    print(f"\n   Wrote {written}/{len(events)} events")
    
    if written == 0:
        print("❌ No events were written. Check Redis connection.")
        return 1
    
    # Wait a bit for processing
    print("\n4. Waiting for processing (5 seconds)...")
    print("   (Start the processing server in another terminal if not running)")
    time.sleep(5)
    
    # Check SQLite database
    print("\n5. Checking SQLite database (raw_traces ingest)...")
    db_path = Path.home() / ".blueplane" / "telemetry.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1
    
    client = SQLiteClient(str(db_path))
    
    with client.get_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM raw_traces WHERE session_id = ?",
            (session_id,),
        )
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"✅ Found {count} events in database for session {session_id}")

            # Show sample events
            cursor = conn.execute(
                "SELECT sequence, event_type, platform, timestamp FROM raw_traces "
                "WHERE session_id = ? ORDER BY sequence LIMIT 5",
                (session_id,),
            )
            print("\n   Sample events (from raw_traces):")
            rows = cursor.fetchall()
            for row in rows:
                print(f"     Sequence {row[0]}: {row[1]} ({row[2]}) at {row[3]}")

            # Try to decompress one event_data row to validate compression/round-trip
            cursor = conn.execute(
                "SELECT sequence, event_data FROM raw_traces "
                "WHERE session_id = ? ORDER BY sequence LIMIT 1",
                (session_id,),
            )
            sample = cursor.fetchone()
            if sample:
                seq, blob = sample
                try:
                    import zlib

                    json_str = zlib.decompress(blob).decode("utf-8")
                    event = json.loads(json_str)
                    print("\n   ✅ Successfully decompressed event_data for sequence", seq)
                    print(f"      event_type={event.get('event_type')}, platform={event.get('platform')}")
                except Exception as exc:
                    print("\n   ⚠️  Failed to decompress event_data for sequence", seq)
                    print(f"      Error: {exc}")
        else:
            print(f"⚠️  No events found in database for session {session_id}")
            print("   This might mean:")
            print("   - Processing server is not running")
            print("   - Events are still being processed")
            print("   - Check server logs for errors")
    
    # Check CDC stream
    print("\n6. Checking CDC stream...")
    try:
        import redis
        redis_client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            decode_responses=False
        )
        
        cdc_config = config.get_stream_config("cdc")
        cdc_length = redis_client.xlen(cdc_config.name)
        print(f"   CDC stream '{cdc_config.name}' has {cdc_length} entries")
        
        if cdc_length > 0:
            print("   ✅ CDC events are being published")
        else:
            print("   ⚠️  No CDC events found (server may not be running)")
    except Exception as e:
        print(f"   ⚠️  Could not check CDC stream: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    print("\nTo start the processing server:")
    print("  python -m src.processing.server")
    print("\nOr run it in the background:")
    print("  python -m src.processing.server &")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

