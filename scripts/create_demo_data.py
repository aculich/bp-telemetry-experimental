#!/usr/bin/env python3
"""
Create demo conversation data directly in SQLite for dashboard demonstration.
This bypasses the slow path processing for quick demo setup.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blueplane.storage.sqlite_conversations import ConversationStorage


def create_demo_conversations():
    """Create sample conversations for dashboard demo."""
    storage = ConversationStorage()
    
    # Demo session 1: High acceptance rate
    session_id_1 = "demo-refactor-abc123"
    conv_id_1 = storage.get_or_create_conversation(
        session_id=session_id_1,
        external_session_id=session_id_1,
        platform="claude_code",
        workspace_hash="demo-workspace-1",
    )
    
    # Add turns
    storage.add_turn(
        conversation_id=conv_id_1,
        turn_type="user_prompt",
        content="Refactor this class to use dependency injection",
        content_hash="hash1",
    )
    
    storage.add_turn(
        conversation_id=conv_id_1,
        turn_type="tool_use",
        tool_name="ReadFile",
        tokens_used=500,
        latency_ms=120,
        accepted=True,
    )
    
    storage.add_turn(
        conversation_id=conv_id_1,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=1200,
        latency_ms=250,
        accepted=True,
        lines_added=15,
        lines_removed=3,
    )
    
    storage.add_turn(
        conversation_id=conv_id_1,
        turn_type="user_prompt",
        content="Add unit tests for the refactored class",
        content_hash="hash2",
    )
    
    storage.add_turn(
        conversation_id=conv_id_1,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=800,
        latency_ms=180,
        accepted=True,
        lines_added=25,
        lines_removed=0,
    )
    
    # Update conversation end time
    storage.update_conversation(
        conversation_id=conv_id_1,
        ended_at=datetime.utcnow().isoformat() + "Z",
    )
    
    # Demo session 2: Mixed acceptance
    session_id_2 = "demo-bugfix-def456"
    conv_id_2 = storage.get_or_create_conversation(
        session_id=session_id_2,
        external_session_id=session_id_2,
        platform="claude_code",
        workspace_hash="demo-workspace-1",
    )
    
    storage.add_turn(
        conversation_id=conv_id_2,
        turn_type="user_prompt",
        content="Fix the bug where the function returns None",
        content_hash="hash3",
    )
    
    storage.add_turn(
        conversation_id=conv_id_2,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=600,
        latency_ms=150,
        accepted=False,  # Rejected
    )
    
    storage.add_turn(
        conversation_id=conv_id_2,
        turn_type="user_prompt",
        content="Actually, I need it to return an empty list, not None",
        content_hash="hash4",
    )
    
    storage.add_turn(
        conversation_id=conv_id_2,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=400,
        latency_ms=100,
        accepted=True,
        lines_added=2,
        lines_removed=1,
    )
    
    storage.update_conversation(
        conversation_id=conv_id_2,
        ended_at=datetime.utcnow().isoformat() + "Z",
    )
    
    # Demo session 3: Multi-file feature
    session_id_3 = "demo-multifile-ghi789"
    conv_id_3 = storage.get_or_create_conversation(
        session_id=session_id_3,
        external_session_id=session_id_3,
        platform="claude_code",
        workspace_hash="demo-workspace-2",
    )
    
    storage.add_turn(
        conversation_id=conv_id_3,
        turn_type="user_prompt",
        content="Add a new authentication feature",
        content_hash="hash5",
    )
    
    storage.add_turn(
        conversation_id=conv_id_3,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=1500,
        latency_ms=300,
        accepted=True,
        lines_added=50,
        lines_removed=5,
    )
    
    storage.add_turn(
        conversation_id=conv_id_3,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=800,
        latency_ms=200,
        accepted=True,
        lines_added=30,
        lines_removed=2,
    )
    
    storage.add_turn(
        conversation_id=conv_id_3,
        turn_type="tool_use",
        tool_name="ReadFile",
        tokens_used=300,
        latency_ms=80,
        accepted=True,
    )
    
    storage.add_turn(
        conversation_id=conv_id_3,
        turn_type="user_prompt",
        content="Add documentation for the new feature",
        content_hash="hash6",
    )
    
    storage.add_turn(
        conversation_id=conv_id_3,
        turn_type="tool_use",
        tool_name="Edit",
        tokens_used=600,
        latency_ms=150,
        accepted=True,
        lines_added=20,
        lines_removed=0,
    )
    
    storage.update_conversation(
        conversation_id=conv_id_3,
        ended_at=datetime.utcnow().isoformat() + "Z",
    )
    
    print("✅ Created 3 demo conversations:")
    print(f"   1. {session_id_1} (high acceptance)")
    print(f"   2. {session_id_2} (mixed acceptance)")
    print(f"   3. {session_id_3} (multi-file feature)")
    
    # Verify
    conversations = storage.get_all_conversations()
    print(f"\n✅ Total conversations: {len(conversations)}")
    
    return conversations


if __name__ == "__main__":
    create_demo_conversations()

