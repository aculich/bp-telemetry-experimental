"""
SQLite storage for raw traces with zlib compression.
Implements fast path writer pattern with batch inserts.
"""

import json
import sqlite3
import zlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..config import config


class SQLiteTraceStorage:
    """
    SQLite storage for raw traces with zlib compression.
    Implements fast path writer pattern with batch inserts.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        
        - Open connection to db_path
        - Enable WAL mode and configure PRAGMAs
        - Create tables if not exist
        """
        self.db_path = db_path or config.db_path
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.compression_level = config.compression_level
        
        self._initialize_database()
        self._prepare_statements()

    def _initialize_database(self) -> None:
        """Initialize database with optimal settings and schema."""
        # Performance settings
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self.conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        
        # Create raw_traces table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_traces (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Event metadata (indexed fields)
                event_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                platform TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                
                -- Context fields
                workspace_hash TEXT,
                model TEXT,
                tool_name TEXT,
                
                -- Metrics (for fast filtering)
                duration_ms INTEGER,
                tokens_used INTEGER,
                lines_added INTEGER,
                lines_removed INTEGER,
                
                -- Compressed payload (zlib level 6, achieves 7-10x compression)
                event_data BLOB NOT NULL,
                
                -- Generated columns for partitioning
                event_date DATE GENERATED ALWAYS AS (DATE(timestamp)),
                event_hour INTEGER GENERATED ALWAYS AS (CAST(strftime('%H', timestamp) AS INTEGER))
            )
        """)
        
        # Create indexes
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_time 
            ON raw_traces(session_id, timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type_time 
            ON raw_traces(event_type, timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_date_hour 
            ON raw_traces(event_date, event_hour)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON raw_traces(timestamp DESC)
        """)
        
        # Create daily statistics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_stats (
                stat_date DATE PRIMARY KEY,
                total_events INTEGER NOT NULL,
                unique_sessions INTEGER NOT NULL,
                event_types TEXT NOT NULL,
                platform_breakdown TEXT NOT NULL,
                error_count INTEGER DEFAULT 0,
                avg_duration_ms REAL,
                total_tokens INTEGER DEFAULT 0,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()

    def _prepare_statements(self) -> None:
        """Prepare SQL statements for batch inserts."""
        self.insert_sql = """
            INSERT INTO raw_traces (
                event_id, session_id, event_type, platform, timestamp,
                workspace_hash, model, tool_name,
                duration_ms, tokens_used, lines_added, lines_removed,
                event_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    def batch_insert(self, events: List[Dict]) -> None:
        """
        Fast path batch insert with compression.
        Target: <8ms for 100 events at P95.
        
        Steps:
        - For each event:
            - Extract indexed fields (event_id, session_id, event_type, etc.)
            - Compress full event data with zlib.compress(json.dumps(event), level=6)
            - Build row tuple
        - Execute single INSERT with executemany()
        - No explicit commit (WAL mode handles concurrency)
        """
        rows = []
        for event in events:
            # Extract indexed fields
            event_id = event.get("event_id", "")
            session_id = event.get("session_id", "")
            event_type = event.get("event_type", "")
            platform = event.get("platform", "")
            timestamp = event.get("timestamp", datetime.utcnow().isoformat())
            
            # Extract context fields
            metadata = event.get("metadata", {})
            workspace_hash = metadata.get("workspace_hash")
            model = metadata.get("model")
            
            payload = event.get("payload", {})
            tool_name = payload.get("tool") or payload.get("tool_name")
            
            # Extract metrics
            duration_ms = payload.get("duration_ms") or event.get("duration_ms")
            tokens_used = payload.get("tokens_used") or event.get("tokens_used")
            lines_added = payload.get("lines_added") or event.get("lines_added")
            lines_removed = payload.get("lines_removed") or event.get("lines_removed")
            
            # Compress full event data
            event_json = json.dumps(event, default=str)
            event_data = zlib.compress(event_json.encode("utf-8"), self.compression_level)
            
            # Build row tuple
            row = (
                event_id,
                session_id,
                event_type,
                platform,
                timestamp,
                workspace_hash,
                model,
                tool_name,
                duration_ms,
                tokens_used,
                lines_added,
                lines_removed,
                event_data,
            )
            rows.append(row)
        
        # Batch insert
        self.conn.executemany(self.insert_sql, rows)
        self.conn.commit()

    def get_by_sequence(self, sequence: int) -> Optional[Dict]:
        """
        Read single event by sequence (used by slow path workers).
        
        - SELECT event_data, indexed fields WHERE sequence = ?
        - Decompress event_data with zlib.decompress()
        - Parse JSON and merge with indexed fields
        - Return complete event dict
        """
        cursor = self.conn.execute("""
            SELECT sequence, ingested_at, event_id, session_id, event_type,
                   platform, timestamp, workspace_hash, model, tool_name,
                   duration_ms, tokens_used, lines_added, lines_removed,
                   event_data
            FROM raw_traces
            WHERE sequence = ?
        """, (sequence,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # Decompress event data
        event_data = zlib.decompress(row["event_data"])
        event = json.loads(event_data.decode("utf-8"))
        
        # Merge indexed fields
        event["_sequence"] = row["sequence"]
        event["_ingested_at"] = row["ingested_at"]
        
        return event

    def get_session_events(
        self, session_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None
    ) -> List[Dict]:
        """
        Query events for conversation reconstruction.
        
        - SELECT WHERE session_id = ? AND timestamp BETWEEN ? AND ?
        - ORDER BY timestamp ASC
        - Decompress and parse each event_data
        - Return list of event dicts
        """
        query = """
            SELECT sequence, event_data
            FROM raw_traces
            WHERE session_id = ?
        """
        params = [session_id]
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp ASC"
        
        cursor = self.conn.execute(query, params)
        events = []
        
        for row in cursor:
            event_data = zlib.decompress(row["event_data"])
            event = json.loads(event_data.decode("utf-8"))
            event["_sequence"] = row["sequence"]
            events.append(event)
        
        return events

    def _get_sequences_by_event_ids(self, event_ids: List[str]) -> List[int]:
        """Get sequence numbers for a list of event IDs."""
        if not event_ids:
            return []
        
        placeholders = ",".join("?" * len(event_ids))
        cursor = self.conn.execute(
            f"""
            SELECT event_id, sequence
            FROM raw_traces
            WHERE event_id IN ({placeholders})
            ORDER BY sequence ASC
            """,
            event_ids,
        )
        
        # Create mapping
        id_to_seq = {row["event_id"]: row["sequence"] for row in cursor}
        
        # Return sequences in same order as event_ids
        return [id_to_seq.get(eid, 0) for eid in event_ids]

    def calculate_session_metrics(self, session_id: str) -> Dict:
        """
        Calculate aggregated metrics for session.
        
        - Query raw_traces for session_id
        - Aggregate: SUM(tokens_used), COUNT(*), SUM(duration_ms), etc.
        - Return metrics dict (no decompression needed for aggregates)
        """
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as event_count,
                SUM(tokens_used) as total_tokens,
                SUM(duration_ms) as total_duration_ms,
                AVG(duration_ms) as avg_duration_ms,
                SUM(lines_added) as total_lines_added,
                SUM(lines_removed) as total_lines_removed,
                COUNT(DISTINCT event_type) as unique_event_types
            FROM raw_traces
            WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        if not row:
            return {}
        
        return {
            "event_count": row["event_count"] or 0,
            "total_tokens": row["total_tokens"] or 0,
            "total_duration_ms": row["total_duration_ms"] or 0,
            "avg_duration_ms": row["avg_duration_ms"] or 0,
            "total_lines_added": row["total_lines_added"] or 0,
            "total_lines_removed": row["total_lines_removed"] or 0,
            "unique_event_types": row["unique_event_types"] or 0,
        }

    def vacuum_old_traces(self, days_to_keep: int = None) -> None:
        """
        Delete old traces and reclaim space.
        
        - DELETE FROM raw_traces WHERE event_date < (today - days_to_keep)
        - Execute VACUUM to reclaim disk space
        - Update trace_stats to remove old dates
        """
        days_to_keep = days_to_keep or config.raw_trace_retention_days
        
        cutoff_date = datetime.utcnow().date()
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=days_to_keep)
        
        self.conn.execute("""
            DELETE FROM raw_traces
            WHERE event_date < ?
        """, (cutoff_date.isoformat(),))
        
        self.conn.execute("VACUUM")
        self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

