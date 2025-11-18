<!--
Copyright © 2025 Sierra Labs LLC
SPDX-License-Identifier: AGPL-3.0-only
License-Filename: LICENSE
-->

## SQLite vs DuckDB for Blueplane Telemetry Core

> Local-only telemetry and analytics for AI-assisted coding, with future AI/LLM-powered insights

This document summarizes the tradeoffs between **SQLite** and **DuckDB** for Blueplane’s local telemetry stack, including emerging AI/LLM-related capabilities, and proposes a **decision rubric** plus a **concrete recommendation** for this project.

Blueplane today uses:

- **SQLite**: Primary store for raw traces and conversations in a single `telemetry.db` file.
- **Redis**: Message queue + real-time metrics.
- **DuckDB**: Optional, scaffolded adapter (`DuckDBAdapter`) used only when explicitly enabled, intended for future OLAP-style aggregation and workspace history.

### 1. High-level comparison

- **SQLite (row-store, OLTP-oriented)**
  - Embedded, single-file, zero configuration.
  - Excellent for **frequent, small writes** and point queries.
  - WAL mode gives good concurrent **read-while-write** behavior with a single writer.
  - Backed by stdlib (`sqlite3`) with no extra dependency surface.
  - Works well as the **authoritative operational store** for telemetry events and conversations.

- **DuckDB (columnar, OLAP-oriented)**
  - Embedded analytical engine, optimized for **scans, joins, aggregations** over large tables.
  - Multi-threaded execution, automatic compression, very strong performance for analytical queries.
  - Especially good at “**query my history**” style workloads and aggregation across many workspaces or long time ranges.
  - Optional dependency (`duckdb` Python package), better suited as a **read-optimized sidecar** than as the first-write target for a simple local agent.

### 2. AI/LLM and vector-search related considerations

- **SQLite ecosystem**
  - Extensions like **`sqlite-vec`** / **VSS** add vector columns and approximate nearest neighbor search on top of SQLite.
  - Fits well with Blueplane’s **local-only** and **single-file** model: embeddings and metadata can live in the same `telemetry.db` (or a sibling file) without introducing a networked vector DB.
  - Good match for features like:
    - “Find similar past sessions/interactions.”
    - “Show me previous traces that look like this one.”

- **DuckDB ecosystem**
  - Rapidly growing extension ecosystem focused on **analytics and data science tooling**.
  - Research and early work on **in-database LLM integrations** and model-driven functions (e.g., LLM-backed transforms, RAG-like queries against tables).
  - Very strong for **batch analytics over embeddings** (e.g., running statistics, clustering, joins between embeddings and structured telemetry).

- **Other options (for context)**
  - Full vector databases (Qdrant, Milvus, etc.) are powerful but introduce servers, network, and more ops surface.
  - Given Blueplane’s **privacy-first, local-only, zero-config** goals, these are less aligned than “SQLite + extensions” or “DuckDB as an embedded OLAP engine”.

For Blueplane’s foreseeable roadmap, **SQLite with optional vector/FTS extensions plus an optional DuckDB sink** provides more than enough headroom without leaving the embedded, local-only world.

### 3. Decision rubric

Use the following rubric when deciding where a **new data flow or feature** should primarily live. Think in terms of the **first-write store** and any **secondary analytic sinks**.

- **Workload type**
  - Mostly **append-only event ingestion**, small batched writes, and simple lookups by session/time → **SQLite**.
  - Heavy **aggregations, scans across many days/workspaces**, ad-hoc analytics, and “data science” queries → **DuckDB** (fed from SQLite or Markdown history).

- **Data volume and growth**
  - Up to a few **tens of thousands of events/day**, with 60–90 days retention and modest per-user disk → **SQLite is sufficient** (especially with compression).
  - If you expect **hundreds of millions of rows** per user and frequent cross-cutting analyses, consider a **DuckDB warehouse-style file** for derived, compacted data.

- **Query complexity**
  - Point lookups, “session-by-session” flows, and small-window aggregations (per session, per day) → **SQLite**.
  - Complex joins across multiple fact tables, multi-dimensional rollups, and exploratory notebooks → **DuckDB**.

- **Concurrency and integration**
  - Single local processing server with one main writer and a few readers (current Blueplane design) → **SQLite** fits perfectly.
  - If you later add **heavier concurrent analytical workloads** (e.g., an interactive dashboard running many large queries), it is safer to keep those against **DuckDB** rather than pounding the ingestion DB.

- **Operational footprint and dependencies**
  - Minimal dependencies, “just Python and Redis,” no extra wheels to install → **SQLite**.
  - It is acceptable to require `duckdb` **only for advanced features** (history analytics, export, power-user tooling) that can be gated behind a flag.

- **AI/LLM adjacent features**
  - Simple, local **similarity search** or FTS over telemetry → **SQLite + vector/FTS extension**.
  - Heavy offline analytics over embeddings, clustering, or model-driven table transforms → consider **materializing from SQLite into DuckDB** and running those jobs there.

### 4. Recommendation for this project

- **Primary store (authoritative source of truth)**
  - Keep **SQLite** as the **only required, always-on database** for:
    - Raw traces (`raw_traces`) with zlib compression.
    - Conversations and structured metrics data used by CLI/MCP/Dashboard.
  - This aligns with the existing async pipeline and `layer2_db_architecture.md`, and keeps the core install path simple and robust.

- **Optional analytical sink**
  - Treat **DuckDB as an optional OLAP sink**, enabled via a feature flag (e.g., environment variable) and wired through the existing `DuckDBAdapter`.
  - Use it for:
    - Recording **workspace snapshot metadata** alongside `.history/*.md` outputs.
    - Future **cross-workspace, long-horizon analytics** that would be expensive to run directly on `telemetry.db`.
  - Import or mirror selected, compacted data from SQLite (or Markdown summaries) into DuckDB on a schedule or as part of history-server pipelines.

- **AI/LLM and vector search path**
  - When you introduce “similar past traces/sessions” features, start by:
    - Storing embeddings and similarity metadata **in SQLite**, using a vector-search or FTS extension as needed.
    - Optionally exporting a **subset** of this data to DuckDB for offline experimentation, clustering, and research workflows.

- **Greenfield guidance (if starting from zero again)**
  - For a **local, privacy-first telemetry system** like Blueplane, the best pattern is:
    - **SQLite** as the primary OLTP-style event store and source of truth.
    - **Redis** for real-time metrics and queues.
    - **DuckDB** as an **optional, power-user analytic engine**, fed from SQLite/Markdown when needed.
  - In other words, don’t replace SQLite with DuckDB; pair them, and only require DuckDB when truly necessary.

This approach keeps the core experience simple and robust for all users while leaving a clear path to more advanced analytics and AI/LLM-powered features without changing the fundamental architecture.


