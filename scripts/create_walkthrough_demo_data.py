#!/usr/bin/env python3
"""
Create realistic demo data matching the walkthrough examples.
This simulates what the dashboard would show with real usage data.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blueplane.storage.sqlite_conversations import ConversationStorage


def create_walkthrough_demo_data():
    """Create demo conversations matching walkthrough examples."""
    storage = ConversationStorage()
    
    # Clear existing demo data
    print("Clearing existing demo data...")
    storage.conn.execute("DELETE FROM conversations WHERE session_id LIKE 'demo-%'")
    storage.conn.execute("DELETE FROM conversation_turns WHERE conversation_id IN (SELECT id FROM conversations WHERE session_id LIKE 'demo-%')")
    storage.conn.execute("DELETE FROM code_changes WHERE conversation_id IN (SELECT id FROM conversations WHERE session_id LIKE 'demo-%')")
    storage.conn.commit()
    
    # Calculate dates for realistic timeline
    now = datetime.utcnow()
    base_date = now - timedelta(days=30)  # Start 30 days ago
    
    conversations_created = []
    
    # Create ~142 sessions over the past month (matching walkthrough: "142 sessions this month")
    # This gives us ~5 sessions per day
    sessions_per_day = 5
    total_sessions = 142
    
    # Track metrics for realistic acceptance rate
    total_accepted = 0
    total_rejected = 0
    
    session_num = 0
    current_date = base_date
    
    while session_num < total_sessions:
        # Create sessions for this day
        for i in range(sessions_per_day):
            if session_num >= total_sessions:
                break
            
            session_id = f"demo-session-{session_num:04d}"
            
            # Vary session types for realism
            session_type = random.choice(["refactor", "bugfix", "feature", "test", "docs"])
            
            # Create conversation
            conv_id = storage.get_or_create_conversation(
                session_id=session_id,
                external_session_id=session_id,
                platform="claude_code",
                workspace_hash=f"workspace-{random.randint(1, 5)}",
            )
            
            # Set started_at to current_date
            started_at = current_date + timedelta(hours=random.randint(9, 17), minutes=random.randint(0, 59))
            storage.conn.execute("""
                UPDATE conversations SET started_at = ? WHERE id = ?
            """, (started_at.isoformat() + "Z", conv_id))
            
            # Add interactions based on session type
            interactions = 0
            session_accepted = 0
            session_rejected = 0
            
            # User prompt
            storage.add_turn(
                conversation_id=conv_id,
                turn_type="user_prompt",
                content_hash=f"hash-{session_num}-{interactions}",
            )
            interactions += 1
            
            # Tool uses (varies by session type)
            if session_type == "refactor":
                num_tools = random.randint(3, 6)
            elif session_type == "bugfix":
                num_tools = random.randint(2, 4)
            elif session_type == "feature":
                num_tools = random.randint(4, 8)
            else:
                num_tools = random.randint(2, 5)
            
            for tool_idx in range(num_tools):
                # Vary tool types
                tool_name = random.choice(["Edit", "ReadFile", "Search", "Edit", "Edit"])  # Edit more common
                
                # Acceptance rate: ~85% overall (matching walkthrough)
                # But vary by session for realism
                accepted = random.random() < 0.85
                
                if accepted:
                    session_accepted += 1
                    total_accepted += 1
                else:
                    session_rejected += 1
                    total_rejected += 1
                
                # Add tool use turn
                storage.add_turn(
                    conversation_id=conv_id,
                    turn_type="tool_use",
                    metadata={"tool": tool_name},
                    tokens_used=random.randint(300, 1500),
                    latency_ms=random.randint(80, 300),
                )
                interactions += 1
                
                # Track code changes for Edit tools
                if tool_name == "Edit" and accepted:
                    lines_added = random.randint(5, 50)
                    lines_removed = random.randint(0, 10)
                    
                    storage.track_code_change(
                        conversation_id=conv_id,
                        turn_id=None,
                        file_extension=random.choice([".py", ".ts", ".tsx", ".js", ".md"]),
                        operation="edit",
                        lines_added=lines_added,
                        lines_removed=lines_removed,
                        accepted=True,
                    )
            
            # Calculate acceptance rate for this session
            session_total = session_accepted + session_rejected
            session_acceptance_rate = session_accepted / session_total if session_total > 0 else None
            
            # Update conversation metrics
            storage.conn.execute("""
                UPDATE conversations
                SET interaction_count = ?,
                    acceptance_rate = ?,
                    total_tokens = ?,
                    total_changes = ?,
                    ended_at = ?
                WHERE id = ?
            """, (
                interactions,
                session_acceptance_rate,
                random.randint(1000, 5000),
                session_accepted,  # total_changes
                (started_at + timedelta(minutes=random.randint(5, 45))).isoformat() + "Z",
                conv_id,
            ))
            
            conversations_created.append({
                "id": conv_id,
                "session_id": session_id,
                "acceptance_rate": session_acceptance_rate,
                "interactions": interactions,
            })
            
            session_num += 1
        
        # Move to next day
        current_date += timedelta(days=1)
    
    storage.conn.commit()
    
    # Calculate overall metrics
    overall_acceptance = total_accepted / (total_accepted + total_rejected) if (total_accepted + total_rejected) > 0 else 0
    
    print(f"\n✅ Created {len(conversations_created)} demo conversations")
    print(f"   Overall acceptance rate: {overall_acceptance:.1%}")
    print(f"   Total accepted: {total_accepted}")
    print(f"   Total rejected: {total_rejected}")
    print(f"   Sessions: {len(conversations_created)}")
    
    # Verify
    conversations = storage.get_all_conversations(limit=200)
    print(f"\n✅ Total conversations in database: {len(conversations)}")
    
    # Show sample
    print("\nSample conversations:")
    for conv in conversations[:5]:
        print(f"  - {conv['session_id']}: {conv.get('interaction_count', 0)} interactions, "
              f"acceptance={conv.get('acceptance_rate', 0):.1%}")
    
    return conversations_created


if __name__ == "__main__":
    create_walkthrough_demo_data()

