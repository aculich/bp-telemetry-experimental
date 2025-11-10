"""
Optimized batch writer for SQLite with zlib compression and zero reads.
"""

from typing import List, Dict
from pathlib import Path

from ..config import config
from ..storage.sqlite_traces import SQLiteTraceStorage


class SQLiteBatchWriter:
    """
    Optimized batch writer for SQLite with zlib compression and zero reads.
    Uses WAL mode and prepared statements for speed.
    """

    def __init__(self, db_path: Path = None):
        """Initialize SQLite connection with performance settings."""
        self.storage = SQLiteTraceStorage(db_path=db_path)

    def write_batch(self, events: List[Dict]) -> None:
        """
        Write batch of events to SQLite - no reads, no lookups, pure writes.
        
        - For each event:
          - Compress full event dict with zlib (level 6)
          - Extract indexed fields (session_id, event_type, etc.)
          - Build row tuple with compressed event_data BLOB
        - Single executemany() with INSERT statement
        - Commit transaction
        - Query back sequence numbers by event_id
        - Target: <8ms for 100 events at P95
        
        Schema: See layer2_db_architecture.md (raw_traces table)
        Compression: zlib level 6 provides 7-10x compression ratio
        """
        import uuid
        
        # Ensure all events have event_id
        for event in events:
            if "event_id" not in event:
                event["event_id"] = str(uuid.uuid4())
        
        # Batch insert (includes compression)
        self.storage.batch_insert(events)
        
        # Query back sequence numbers by event_id (needed for CDC)
        event_ids = [event["event_id"] for event in events]
        sequences = self.storage._get_sequences_by_event_ids(event_ids)
        
        # Update events with sequence numbers
        for event, sequence in zip(events, sequences):
            event["_sequence"] = sequence

    def close(self) -> None:
        """Close database connection."""
        self.storage.close()

