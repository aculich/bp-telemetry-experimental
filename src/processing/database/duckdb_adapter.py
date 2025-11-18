#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
DuckDB adapter scaffold for Blueplane Telemetry Core.

This module is intentionally minimal and optional:
- It only activates if DuckDB is installed and explicitly enabled.
- It mirrors the core SQLite schema for future OLAP-style aggregation.

For now, the adapter is used as a foundation for future work and does not
participate in the main ingestion/markdown paths by default.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json
import time

logger = logging.getLogger(__name__)

try:
    import duckdb  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    duckdb = None  # type: ignore[assignment]


class DuckDBAdapter:
    """
    Minimal DuckDB adapter scaffold.

    Responsibilities (current scope):
    - Initialize a DuckDB database at the given path.
    - Ensure a raw_traces table exists with a schema roughly mirroring SQLite.
    - Provide a hook for future bulk-ingest from SQLite or direct writers.

    This should only be constructed when the feature flag is enabled and
    DuckDB is available.
    """

    def __init__(self, db_path: Path):
        if duckdb is None:
            raise RuntimeError(
                "DuckDBAdapter requires the 'duckdb' package. "
                "Install with `pip install duckdb` and enable the feature flag."
            )

        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing DuckDB database at {self.db_path}")
        self._conn = duckdb.connect(str(self.db_path))
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """
        Create a raw_traces-like table if it does not already exist.

        The schema is intentionally simplified; it mirrors the main identifiers
        and a JSON payload column for future expansion.
        """
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_traces (
                sequence BIGINT,
                ingested_at TIMESTAMP,
                event_id VARCHAR,
                session_id VARCHAR,
                event_type VARCHAR,
                platform VARCHAR,
                timestamp TIMESTAMP,
                workspace_hash VARCHAR,
                model VARCHAR,
                tool_name VARCHAR,
                duration_ms BIGINT,
                tokens_used BIGINT,
                lines_added BIGINT,
                lines_removed BIGINT,
                event_data_json JSON
            )
            """
        )
        logger.info("Ensured DuckDB raw_traces table exists")

    def close(self) -> None:
        """Close the DuckDB connection."""
        try:
            self._conn.close()
        except Exception:
            logger.debug("DuckDB connection already closed or failed to close")

    def insert_workspace_snapshot(
        self,
        workspace_hash: str,
        workspace_path: str,
        markdown_path: Path,
        session_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Insert a workspace snapshot record into DuckDB.

        This stores a minimal row in raw_traces with event_type=workspace_snapshot
        and a JSON payload describing where the Markdown artifact lives.
        """
        now = datetime.utcnow()
        event_id = f"wsnap:{workspace_hash}:{int(time.time() * 1000)}"

        payload: Dict[str, Any] = {
            "workspace_hash": workspace_hash,
            "workspace_path": workspace_path,
            "markdown_path": str(markdown_path),
        }
        if extra_metadata:
            payload.update(extra_metadata)

        # Insert row; many columns intentionally left NULL for now
        self._conn.execute(
            """
            INSERT INTO raw_traces (
                sequence,
                ingested_at,
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
                event_data_json
            ) VALUES (
                NULL,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                ?
            )
            """,
            [
                now,
                event_id,
                session_id or "",
                "workspace_snapshot",
                "cursor",
                now,
                workspace_hash,
                json.dumps(payload),
            ],
        )
        logger.debug("Inserted workspace snapshot into DuckDB: %s", event_id)


