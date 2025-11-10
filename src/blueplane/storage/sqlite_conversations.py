"""
SQLite storage for structured conversation data in telemetry.db.
Uses same database connection as raw traces.
Updated by slow path conversation workers.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..config import config


class ConversationStorage:
    """
    SQLite storage for structured conversation data in telemetry.db.
    Uses same database connection as raw traces.
    Updated by slow path conversation workers.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize conversation storage (uses same DB as raw traces)."""
        self.db_path = db_path or config.db_path
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        self._initialize_tables()

    def _initialize_tables(self) -> None:
        """Create conversation tables if they don't exist."""
        # Conversations table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                external_session_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                workspace_hash TEXT,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                
                -- JSON fields
                context TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                tool_sequence TEXT DEFAULT '[]',
                acceptance_decisions TEXT DEFAULT '[]',
                
                -- Metrics
                interaction_count INTEGER DEFAULT 0,
                acceptance_rate REAL,
                total_tokens INTEGER DEFAULT 0,
                total_changes INTEGER DEFAULT 0,
                
                UNIQUE(external_session_id, platform)
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_session 
            ON conversations(session_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_platform_time 
            ON conversations(platform, started_at DESC)
        """)
        
        # Conversation turns table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                turn_number INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                turn_type TEXT CHECK (turn_type IN ('user_prompt', 'assistant_response', 'tool_use')),
                
                content_hash TEXT,
                metadata TEXT DEFAULT '{}',
                tokens_used INTEGER,
                latency_ms INTEGER,
                tools_called TEXT,
                
                UNIQUE(conversation_id, turn_number)
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_turn_conv 
            ON conversation_turns(conversation_id, turn_number)
        """)
        
        # Code changes table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS code_changes (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                turn_id TEXT REFERENCES conversation_turns(id),
                timestamp TIMESTAMP NOT NULL,
                
                file_extension TEXT,
                operation TEXT CHECK (operation IN ('create', 'edit', 'delete', 'read')),
                lines_added INTEGER DEFAULT 0,
                lines_removed INTEGER DEFAULT 0,
                
                accepted BOOLEAN,
                acceptance_delay_ms INTEGER,
                revision_count INTEGER DEFAULT 0
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_changes_conv 
            ON code_changes(conversation_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_changes_accepted 
            ON code_changes(accepted, timestamp)
        """)
        
        # Session mappings table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session_mappings (
                external_id TEXT PRIMARY KEY,
                internal_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(external_id, platform)
            )
        """)
        
        self.conn.commit()

    def create_conversation(
        self, session_id: str, external_session_id: str, platform: str, workspace_hash: Optional[str] = None
    ) -> str:
        """
        Create new conversation (called by conversation worker).
        
        - Generate UUID for conversation ID
        - INSERT into conversations table
        - Return conversation ID
        """
        conversation_id = str(uuid.uuid4())
        started_at = datetime.utcnow().isoformat()
        
        self.conn.execute("""
            INSERT INTO conversations (
                id, session_id, external_session_id, platform, workspace_hash, started_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (conversation_id, session_id, external_session_id, platform, workspace_hash, started_at))
        
        self.conn.commit()
        return conversation_id

    def get_or_create_conversation(
        self, session_id: str, external_session_id: str, platform: str, workspace_hash: Optional[str] = None
    ) -> str:
        """Get existing conversation or create new one."""
        cursor = self.conn.execute("""
            SELECT id FROM conversations
            WHERE external_session_id = ? AND platform = ?
        """, (external_session_id, platform))
        
        row = cursor.fetchone()
        if row:
            return row["id"]
        
        return self.create_conversation(session_id, external_session_id, platform, workspace_hash)

    def add_turn(
        self,
        conversation_id: str,
        turn_type: str,
        content_hash: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        tools_called: Optional[List[str]] = None,
    ) -> str:
        """
        Add turn to conversation.
        
        - Get next turn number (MAX + 1)
        - INSERT into conversation_turns
        - Update conversation interaction_count
        - Return turn ID
        """
        # Get next turn number
        cursor = self.conn.execute("""
            SELECT COALESCE(MAX(turn_number), 0) + 1 as next_turn
            FROM conversation_turns
            WHERE conversation_id = ?
        """, (conversation_id,))
        
        turn_number = cursor.fetchone()["next_turn"]
        turn_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        metadata_json = json.dumps(metadata or {})
        tools_called_json = json.dumps(tools_called or [])
        
        self.conn.execute("""
            INSERT INTO conversation_turns (
                id, conversation_id, turn_number, timestamp, turn_type,
                content_hash, metadata, tokens_used, latency_ms, tools_called
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            turn_id, conversation_id, turn_number, timestamp, turn_type,
            content_hash, metadata_json, tokens_used, latency_ms, tools_called_json
        ))
        
        # Update interaction count
        self.conn.execute("""
            UPDATE conversations
            SET interaction_count = interaction_count + 1
            WHERE id = ?
        """, (conversation_id,))
        
        self.conn.commit()
        return turn_id

    def track_code_change(
        self,
        conversation_id: str,
        turn_id: Optional[str],
        file_extension: Optional[str],
        operation: str,
        lines_added: int = 0,
        lines_removed: int = 0,
        accepted: Optional[bool] = None,
        acceptance_delay_ms: Optional[int] = None,
    ) -> str:
        """
        Track code change in conversation.
        
        - INSERT into code_changes
        - Update conversation acceptance metrics
        - Return change ID
        """
        change_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        self.conn.execute("""
            INSERT INTO code_changes (
                id, conversation_id, turn_id, timestamp,
                file_extension, operation, lines_added, lines_removed,
                accepted, acceptance_delay_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            change_id, conversation_id, turn_id, timestamp,
            file_extension, operation, lines_added, lines_removed,
            accepted, acceptance_delay_ms
        ))
        
        # Update conversation metrics
        if accepted is not None:
            # Calculate acceptance rate
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_changes,
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as accepted_changes
                FROM code_changes
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            row = cursor.fetchone()
            total = row["total_changes"] or 0
            accepted_count = row["accepted_changes"] or 0
            
            acceptance_rate = accepted_count / total if total > 0 else None
            
            self.conn.execute("""
                UPDATE conversations
                SET acceptance_rate = ?, total_changes = ?
                WHERE id = ?
            """, (acceptance_rate, total, conversation_id))
        
        self.conn.commit()
        return change_id

    def get_conversation_flow(self, conversation_id: str) -> Dict:
        """
        Get complete conversation with turns and changes.
        
        - Query conversation by ID
        - Query all turns ordered by turn_number
        - Query all code_changes ordered by timestamp
        - Return combined structure
        """
        # Get conversation
        cursor = self.conn.execute("""
            SELECT * FROM conversations WHERE id = ?
        """, (conversation_id,))
        
        conv_row = cursor.fetchone()
        if not conv_row:
            return {}
        
        conversation = dict(conv_row)
        
        # Parse JSON fields
        conversation["context"] = json.loads(conversation.get("context") or "{}")
        conversation["metadata"] = json.loads(conversation.get("metadata") or "{}")
        conversation["tool_sequence"] = json.loads(conversation.get("tool_sequence") or "[]")
        conversation["acceptance_decisions"] = json.loads(conversation.get("acceptance_decisions") or "[]")
        
        # Get turns
        cursor = self.conn.execute("""
            SELECT * FROM conversation_turns
            WHERE conversation_id = ?
            ORDER BY turn_number ASC
        """, (conversation_id,))
        
        turns = []
        for row in cursor:
            turn = dict(row)
            turn["metadata"] = json.loads(turn.get("metadata") or "{}")
            turn["tools_called"] = json.loads(turn.get("tools_called") or "[]")
            turns.append(turn)
        
        conversation["turns"] = turns
        
        # Get code changes
        cursor = self.conn.execute("""
            SELECT * FROM code_changes
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        changes = [dict(row) for row in cursor]
        conversation["code_changes"] = changes
        
        return conversation

    def get_conversations_by_session(self, session_id: str) -> List[Dict]:
        """Get all conversations for a session (for Layer 3 access)."""
        cursor = self.conn.execute("""
            SELECT id, external_session_id, platform, started_at, ended_at,
                   interaction_count, acceptance_rate, total_tokens, total_changes
            FROM conversations
            WHERE session_id = ?
            ORDER BY started_at DESC
        """, (session_id,))
        
        return [dict(row) for row in cursor]

    def get_all_conversations(self, limit: int = 50, offset: int = 0, platform: Optional[str] = None) -> List[Dict]:
        """Get all conversations with pagination (for Layer 3 access)."""
        query = """
            SELECT id, session_id, external_session_id, platform, started_at, ended_at,
                   interaction_count, acceptance_rate, total_tokens, total_changes
            FROM conversations
        """
        params = []
        
        if platform:
            query += " WHERE platform = ?"
            params.append(platform)
        
        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor]

    def get_global_acceptance_metrics(self) -> Dict:
        """Get global acceptance rate metrics (for Layer 3 dashboards)."""
        # Calculate from all conversations, handling NULL acceptance rates
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total_conversations,
                AVG(acceptance_rate) as avg_acceptance_rate,
                SUM(total_changes) as total_changes,
                SUM(CASE WHEN acceptance_rate > 0.5 THEN 1 ELSE 0 END) as high_acceptance_conversations
            FROM conversations
        """)
        
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Convert None to 0 for numeric fields
            if result.get("avg_acceptance_rate") is None:
                result["avg_acceptance_rate"] = 0
            if result.get("total_changes") is None:
                result["total_changes"] = 0
            if result.get("total_conversations") is None:
                result["total_conversations"] = 0
            return result
        return {}

    def get_acceptance_statistics(self, time_range: str = "7d") -> Dict:
        """Get acceptance statistics over time (for Layer 3 analytics)."""
        # Parse time range (simplified - assumes days)
        days = int(time_range.rstrip("d"))
        cutoff_date = datetime.utcnow().date()
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=days)
        
        cursor = self.conn.execute("""
            SELECT 
                DATE(started_at) as date,
                COUNT(*) as conversation_count,
                AVG(acceptance_rate) as avg_acceptance_rate,
                SUM(total_changes) as total_changes
            FROM conversations
            WHERE started_at >= ? AND acceptance_rate IS NOT NULL
            GROUP BY DATE(started_at)
            ORDER BY date ASC
        """, (cutoff_date.isoformat(),))
        
        return [dict(row) for row in cursor]

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

