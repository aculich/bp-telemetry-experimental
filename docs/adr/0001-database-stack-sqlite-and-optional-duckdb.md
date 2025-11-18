<!--
Copyright © 2025 Sierra Labs LLC
SPDX-License-Identifier: AGPL-3.0-only
License-Filename: LICENSE
-->

## ADR 0001 – Local Database Stack: SQLite Primary, DuckDB Optional

### Status

- **Status**: Accepted  
- **Date**: 2025-11-18  

### Context

Blueplane Telemetry Core is a **local-only telemetry and analytics system** for AI-assisted coding.  
Key constraints:

- All data stays on the user’s machine (no external services).
- Installation should be as close to “just Python, Redis, and this repo” as possible.
- Ingestion must be **fast and robust** (sub-10ms P95 for batched writes).
- Future roadmap includes **analytics and AI/LLM-powered insights** over historical data.

Current implementation (as of this ADR):

- The main ingest path uses `SQLiteClient` and `SQLiteBatchWriter`:
  - `src/processing/database/sqlite_client.py`  
  - `src/processing/database/writer.py`
- The **Workspace History Server**:
  - Ensures `~/.blueplane/telemetry.db` exists via `SQLiteClient` + `create_schema`.
  - Runs `SessionMonitor` + `CursorMarkdownMonitor` for history/Markdown output.
  - Optionally initializes a `DuckDBAdapter`, controlled by `BLUEPLANE_HISTORY_USE_DUCKDB=1`.
- `CursorMarkdownMonitor` always writes Markdown; if a `DuckDBAdapter` is present it also inserts a **workspace snapshot row** into DuckDB as metadata.

In other words, **SQLite is already the canonical, always-on store** for raw traces and conversations, and DuckDB is only used (optionally) as a sidecar for workspace history metadata.

### Decision

We will:

- **Keep SQLite as the primary, authoritative database** for:
  - Raw traces (`raw_traces` table, compressed).
  - Conversations and structured telemetry used by CLI/MCP/Dashboard.
  - Session mappings and other small relational tables.
- **Keep DuckDB as an optional analytical sink**, not a replacement for SQLite:
  - Enabled only when `BLUEPLANE_HISTORY_USE_DUCKDB=1` and the `duckdb` Python package is installed.
  - Used for **workspace history / snapshot metadata** and future OLAP-style analyses.
  - Safe to disable entirely without breaking ingestion or core telemetry.

This means:

- No ingestion or core processing path will require DuckDB.
- SQLite remains the **single required local database file** (`~/.blueplane/telemetry.db`) for correctness.
- DuckDB files (e.g., `~/.blueplane/history.duckdb`) are **derived artifacts**, safe to regenerate.

### Rationale

- **Simplicity and reliability**
  - SQLite is already integrated, battle-tested in this codebase, and documented in `layer2_db_architecture.md`.
  - Shipping only SQLite + Redis as required dependencies keeps the “first run” experience minimal.

- **Workload fit**
  - Ingestion is mostly **append-only event writes** and session-level queries → SQLite (row store + WAL) is a good match.
  - Heavy “scan a long history of workspaces / sessions” queries can be offloaded to DuckDB where desired.

- **Privacy and local-only constraint**
  - Both databases are embedded and local; no servers to manage.
  - We avoid introducing an external vector DB or analytical warehouse while still leaving room for advanced analytics.

- **AI/LLM and vector-search roadmap**
  - For local similarity search and “find similar past traces” features, we can:
    - Store embeddings and metadata in SQLite (possibly via a vector/FTS extension).
    - Optionally mirror compacted/derived data into DuckDB for heavier offline analytics.
  - This lets us build AI/LLM features **incrementally** without changing the ingestion story.

### Consequences

**Positive:**

- Users can run Blueplane with **only SQLite + Redis**; DuckDB is additive.
- Ingestion performance and behavior are clear: everything goes through SQLite first.
- Workspace history and advanced analytics can evolve independently, behind a feature flag.
- Documentation can point to a single canonical DB (`telemetry.db`) for backup/export.

**Negative / tradeoffs:**

- Some analytical workloads that DuckDB would handle elegantly will first require **exporting or mirroring** data from SQLite.
- We maintain two schemas for related data (SQLite and DuckDB), even if DuckDB only holds a subset.
- Power users who want “all analytics in DuckDB” still need to think about data movement from SQLite.

### Alignment with current implementation

- The current code **already follows this decision**:
  - Ingestion and core telemetry read/write paths go through SQLite (`SQLiteClient`, `SQLiteBatchWriter`, and schema definitions in `schema.py` / `layer2_db_architecture.md`).
  - The **Workspace History Server** initializes SQLite unconditionally and uses DuckDB **only** if the `BLUEPLANE_HISTORY_USE_DUCKDB` flag is set.
  - `CursorMarkdownMonitor` always writes Markdown, and conditionally writes DuckDB workspace snapshots when a `DuckDBAdapter` is present.
- Therefore, this ADR does **not** require major refactors; it mostly:
  - Clarifies that **DuckDB is optional and secondary**.
  - Codifies that any new feature must treat SQLite as the first-write, canonical store.

### Follow-ups

- **Docs**
  - Cross-link this ADR from `docs/SQLITE_VS_DUCKDB.md` and `ARCHITECTURE.md`.
  - Make it clear in user-facing docs that DuckDB is an **optional analytics add-on**.

- **Implementation**
  - Keep any new DuckDB usage (e.g., for history analytics or AI/LLM experiments) **behind a feature flag** and derived from SQLite/Markdown, not as a replacement ingestion path.
  - If we add embeddings or vector search, default to **SQLite-based storage** with a clear path to export to DuckDB for analysis when needed.


