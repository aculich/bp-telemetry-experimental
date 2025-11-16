#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Utility script to inspect recent traces ingested by the Python processing server.

Examples:
    # Show 20 most recent events (default)
    python scripts/show_recent_traces.py

    # Show 10 most recent Cursor events
    python scripts/show_recent_traces.py --limit 10 --platform cursor

    # Show recent events for a specific session_id
    python scripts/show_recent_traces.py --session-id sess_abc123 --limit 50
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processing.database.sqlite_client import SQLiteClient


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show recent events from raw_traces in ~/.blueplane/telemetry.db"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of events to display (default: 20)",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Optional session_id to filter on",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help="Optional platform filter (e.g. 'cursor', 'claude_code')",
    )

    args = parser.parse_args()

    db_path = Path.home() / ".blueplane" / "telemetry.db"
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        print("   Make sure you've run scripts/init_database.py and the processing server.")
        return 1

    client = SQLiteClient(str(db_path))

    query = (
        "SELECT sequence, session_id, event_type, platform, timestamp "
        "FROM raw_traces"
    )
    where_clauses = []
    params = []

    if args.session_id:
        where_clauses.append("session_id = ?")
        params.append(args.session_id)

    if args.platform:
        where_clauses.append("platform = ?")
        params.append(args.platform)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY sequence DESC LIMIT ?"
    params.append(args.limit)

    with client.get_connection() as conn:
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()

    if not rows:
        print("ℹ️  No matching events found in raw_traces.")
        return 0

    print(
        f"Showing up to {args.limit} most recent event(s) "
        f"from {db_path} (filters: "
        f"session_id={args.session_id or '*'}, platform={args.platform or '*'})"
    )
    print("-" * 80)
    for seq, session_id, event_type, platform, ts in rows:
        print(f"{seq:8d}  {event_type:20s}  {platform:12s}  {session_id}  {ts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


