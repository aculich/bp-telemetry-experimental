"""
Integration tests for Layer 1 capture components.
"""

import pytest
import redis
import json
import uuid
from datetime import datetime

from blueplane.capture.queue_writer import MessageQueueWriter
from blueplane.config import config


@pytest.fixture
def redis_client():
    """Create a Redis client for testing."""
    try:
        client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
        client.ping()
        yield client
        # Cleanup test streams
        try:
            client.delete(config.mq_stream_name)
        except:
            pass
    except redis.ConnectionError:
        pytest.skip("Redis not available")


def test_message_queue_writer_integration(redis_client):
    """Test MessageQueueWriter with real Redis."""
    writer = MessageQueueWriter(redis_client=redis_client)
    
    # Test connection
    assert writer.test_connection() is True
    
    # Enqueue event
    event = {
        "hook_type": "SessionStart",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "cwd": "/test",
            "transcript_path": "/path/to/transcript.jsonl",
        },
    }
    
    result = writer.enqueue(
        event=event,
        platform="claude_code",
        session_id="test-session-integration",
        hook_type="SessionStart",
    )
    
    assert result is True
    
    # Verify event was written to stream
    messages = redis_client.xread({config.mq_stream_name: "0"}, count=1)
    assert len(messages) > 0
    
    stream_name, entries = messages[0]
    assert stream_name == config.mq_stream_name
    assert len(entries) > 0
    
    # Check entry content
    entry_id, entry_data = entries[0]
    assert entry_data["platform"] == "claude_code"
    assert entry_data["external_session_id"] == "test-session-integration"
    assert entry_data["hook_type"] == "SessionStart"
    
    # Verify data is JSON
    data = json.loads(entry_data["data"])
    assert data["cwd"] == "/test"


def test_multiple_events_integration(redis_client):
    """Test enqueueing multiple events."""
    writer = MessageQueueWriter(redis_client=redis_client)
    
    events = [
        {
            "hook_type": "SessionStart",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {"cwd": "/test1"},
        },
        {
            "hook_type": "UserPromptSubmit",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {"prompt_length": 100},
        },
    ]
    
    for event in events:
        result = writer.enqueue(
            event=event,
            platform="claude_code",
            session_id="test-session-multi",
            hook_type=event["hook_type"],
        )
        assert result is True
    
    # Verify both events in stream
    messages = redis_client.xread({config.mq_stream_name: "0"}, count=10)
    assert len(messages) > 0
    
    stream_name, entries = messages[0]
    assert len(entries) >= 2
    
    # Check hook types
    hook_types = [json.loads(entry[1]["data"]).get("hook_type") or entry[1]["hook_type"] for entry in entries]
    assert "SessionStart" in hook_types or any("SessionStart" in str(e) for e in entries)

