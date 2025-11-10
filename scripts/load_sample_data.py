#!/usr/bin/env python3
"""
Helper script to load sample data and wait for processing to complete.
This ensures the dashboard has data to display.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blueplane.capture import MessageQueueWriter
from blueplane.storage.sqlite_conversations import ConversationStorage
from blueplane.storage.redis_cdc import CDCWorkQueue
import asyncio

# Import test_sample functions
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_sample import (
    test_sample_case_1_refactoring,
    test_sample_case_2_bug_fix,
    test_sample_case_3_multi_file,
)


async def wait_for_processing(max_wait=30):
    """Wait for conversations to be created."""
    storage = ConversationStorage()
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        conversations = storage.get_all_conversations()
        if len(conversations) >= 3:
            print(f"✅ Found {len(conversations)} conversations!")
            return True
        
        print(f"⏳ Waiting for processing... ({len(conversations)}/3 conversations)")
        await asyncio.sleep(2)
    
    print(f"⚠️  Timeout: Only {len(conversations)} conversations found after {max_wait}s")
    return False


def main():
    """Load sample data and wait for processing."""
    print("="*60)
    print("Loading Sample Data for Dashboard")
    print("="*60)
    
    # Check Redis connection
    writer = MessageQueueWriter()
    if not writer.test_connection():
        print("❌ Redis connection failed. Please start Redis:")
        print("   brew services start redis")
        return 1
    
    print("✅ Redis connection successful\n")
    
    # Generate sample data
    print("Generating sample test cases...")
    sessions = []
    sessions.append(test_sample_case_1_refactoring())
    time.sleep(1)
    sessions.append(test_sample_case_2_bug_fix())
    time.sleep(1)
    sessions.append(test_sample_case_3_multi_file())
    
    print(f"\n✅ Generated {len(sessions)} test sessions")
    print(f"   Sessions: {', '.join(sessions)}\n")
    
    # Wait for processing
    print("Waiting for slow path to process events...")
    print("(This may take 10-30 seconds)\n")
    
    result = asyncio.run(wait_for_processing(max_wait=60))
    
    if result:
        print("\n" + "="*60)
        print("✅ Sample Data Loaded Successfully!")
        print("="*60)
        print("\nDashboard should now show:")
        print("  - 3 sessions")
        print("  - Acceptance rate metrics")
        print("  - Tool usage data")
        print("\nOpen: http://localhost:3001")
        return 0
    else:
        print("\n⚠️  Processing incomplete. Check:")
        print("  1. Processing server is running: python scripts/run_server.py")
        print("  2. Redis streams: redis-cli XINFO STREAM cdc:events")
        return 1


if __name__ == "__main__":
    sys.exit(main())

