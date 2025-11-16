## Session TODO: feature/python-server-ingest

> Working notes for this dev session on the Python processing server ingestion path.

### Status: Core Implementation Complete ✅

**The Python server ingest feature is fully implemented and pushed to `upstream/main`** (as of January 2025). All core components are in place:

- ✅ **TelemetryServer** (`src/processing/server.py`) - Main server orchestration
- ✅ **FastPathConsumer** (`src/processing/fast_path/consumer.py`) - Redis Streams consumer with batching, DLQ, PEL retry
- ✅ **SQLiteBatchWriter** (`src/processing/database/writer.py`) - Compressed batch writes to SQLite
- ✅ **CDCPublisher** (`src/processing/fast_path/cdc_publisher.py`) - Change Data Capture event publishing
- ✅ **CursorDatabaseMonitor** - Reads Cursor's SQLite database for metadata
- ✅ **ClaudeCodeTranscriptMonitor** - Processes Claude Code transcript files
- ✅ **SessionMonitor** - Tracks Cursor sessions via Redis events
- ✅ **Entrypoint** (`scripts/start_server.py`) - Server startup script

**Key commits in upstream/main:**
- `637985b` - Initial Layer 2 processing pipeline implementation
- `f76b005` - Integrate Cursor database monitor into processing server
- `431f961` - Implement Claude Code hook and trace capture system
- `c8ed636` - Implement Layer 2 metrics processing pipeline
- `2784bd7` - Fix retry logic and remove async inconsistencies
- `2cdc943` - Fix pending message processing in fast path consumer
- Plus 25+ additional commits refining performance, error handling, and robustness

### Big Picture

- **Overall goal**: Have the Python processing server (Layer 2) reliably ingest all Cursor/Claude telemetry emitted by Layer 1 (hooks + extension + database monitor), persist it to the local SQLite `telemetry.db`, and fan out CDC events for downstream metrics/conversation workers.
- **Context from `STARTHERE.md`**:
  - Layer 1 (Python hooks + Cursor extension + database monitoring) is responsible for capturing events and writing them to Redis Streams.
  - Layer 2 (this feature) is the always-on local server that:
    - Consumes `telemetry:events` from Redis Streams using consumer groups,
    - Writes compressed raw traces to SQLite (`raw_traces` table),
    - Publishes CDC events to `cdc:events` stream for slow-path workers,
    - Runs monitors like `CursorDatabaseMonitor` and `ClaudeCodeTranscriptMonitor`.
- **Success criterion**: After this feature, we should be able to run the server locally, work in Cursor, and see events flowing end-to-end: hooks → Redis → Python server → SQLite (and CDC) with no manual glue scripts.

### Current Status Snapshot

- **Layer 1 capture (Cursor)**
  - ✅ Hooks, shared queue writer, and Cursor extension implemented and documented (`IMPLEMENTATION_SUMMARY.md`, `STARTHERE.md`).
  - ✅ Events are written to Redis Streams `telemetry:events` with a stable schema.
- **Layer 2 server implementation** (✅ **COMPLETE**)
  - ✅ `TelemetryServer` (`src/processing/server.py`) initializes SQLite (`SQLiteClient` + `create_schema` + `SQLiteBatchWriter`), Redis, fast-path consumer, and Cursor/Claude monitors.
  - ✅ Fast-path consumer (`FastPathConsumer`) implemented: XREADGROUP from `telemetry:events`, batch write to SQLite via `SQLiteBatchWriter`, CDC publish via `CDCPublisher`, DLQ + PEL retry logic with adaptive backpressure.
  - ✅ SQLite schema and writer implemented per `layer2_db_architecture.md` (raw traces compressed + indexed).
  - ✅ `scripts/start_server.py` entrypoint exists and wires into `TelemetryServer.main()`.
  - ✅ Async-to-sync refactor completed (PR #10) for simpler, more reliable operation.
  - ✅ Performance optimizations: batch processing, compression, backpressure handling.
- **Gaps / assumptions to validate**
  - ☐ End-to-end ingestion has not yet been fully smoke-tested against a live Cursor session in this branch.
  - ☐ We don't yet have a small, focused test harness that proves "push N events into Redis → see N rows in `raw_traces` with expected fields" **for this session specifically** (note: `scripts/test_end_to_end.py` provides a general ingest smoke test and now validates `event_data` decompression).
  - ☐ Operational docs for the server (how to run, how to verify, how to debug) are still thin compared to Layer 1.

### Immediate Next Steps (Implementation)

- **1. Fast-path ingestion sanity checks**
  - [ ] Verify `FastPathConsumer` correctly decodes the current event schema from Layer 1 (including `payload` / `metadata` JSON, `session_id` / `external_session_id`, `event_type`, `platform`).
  - [ ] Add or refine logging around consumer startup, batch flushes, DLQ routing, and backpressure adjustment so ingest issues are easy to see when running `scripts/start_server.py`.
  - [ ] Confirm `SQLiteBatchWriter` is using the expected schema/columns and compression for `raw_traces` (fields line up with `layer2_db_architecture.md` and Architecture docs).

- **2. Minimal automated ingest test**
  - [ ] Ensure there is a small Python test or script (either by extending `scripts/test_end_to_end.py` or adding a dedicated ingest smoke test) that:
    - Starts Redis + initializes streams (`scripts/init_redis.py`).
    - Writes a handful of synthetic events to `telemetry:events` using the same shape as Layer 1.
    - Runs the fast-path consumer (or full `TelemetryServer`) for a short window.
    - Asserts that `raw_traces` contains matching rows (correct `event_type`, `platform`, `session_id`, non-empty `event_data`) and that at least one `event_data` value round-trips via zlib decompression and JSON parsing.

- **3. Live Cursor path validation**
  - [ ] Run the full stack for Cursor:
    - Install / verify global hooks and extension (per `STARTHERE.md` / `IMPLEMENTATION_SUMMARY.md`).
    - Start Redis + SQLite initialization (`init_redis.py`, `init_database.py`).
    - Start the Python server via `scripts/start_server.py`.
    - Perform a short real Cursor session (prompt, agent response, file edit, MCP tool call).
  - [ ] Inspect `telemetry.db`:
    - `raw_traces` shows events from both Python hooks and `CursorDatabaseMonitor` (database trace events).
    - Timestamps, `session_id`, `workspace_hash`, and basic metrics fields (duration/tokens/etc. where available) look coherent.

- **4. Robustness & backpressure**
  - [ ] Exercise DLQ and PEL retry paths by injecting a few malformed or intentionally failing events and verify:
    - They route to `telemetry:dlq` after `max_retries`.
    - The consumer remains healthy and continues ingesting good events.
  - [ ] Validate backpressure behavior under light load (no excessive throttling) and simulated “slow SQLite” conditions.

- **5. Developer experience & docs**
  - [ ] Add/expand a short “Python Server Ingest” section to the main `README.md` (or a focused doc) that describes:
    - How to start the server for local dev.
    - How to confirm it’s ingesting events (Redis + SQLite checks).
    - How it ties into the 3-layer Cursor instrumentation described in `STARTHERE.md`.
  - [ ] Note any known limitations (e.g., slow-path workers not implemented yet, metrics/conversations still TODO) so scope of this feature remains clear.

### Definition of Done: feature/python-server-ingest

- **End-to-end ingestion**
  - [ ] With Redis + SQLite initialized and `scripts/start_server.py` running, events produced by:
    - Cursor Python hooks (`src/capture/cursor/hooks/*`),
    - Cursor database monitor (`CursorDatabaseMonitor`),
    - (optionally) Claude Code transcript monitor,
    are reliably drained from `telemetry:events` and written to `raw_traces` without message loss under normal conditions.

- **Data correctness**
  - [ ] Each ingested event in `raw_traces` includes the critical indexed fields from the architecture docs (`event_id`, `session_id`, `event_type`, `platform`, `timestamp`, `workspace_hash` where available) plus a non-empty compressed `event_data` blob that round-trips correctly when decompressed.
  - [ ] Event types and platforms match the enums/contract from `event_schema.py`, and database-trace events from `CursorDatabaseMonitor` are distinguishable (e.g., `event_type=database_trace`, `metadata.source=python_monitor`).

- **Operational robustness**
  - [ ] DLQ and PEL retry behavior are verified and documented (what happens when events cannot be processed, how to inspect DLQ).
  - [ ] Basic logging is sufficient to debug startup failures, Redis connectivity issues, and SQLite write problems without diving into code.

- **Tooling & docs**
  - [ ] There is at least one automated or semi-automated ingest test that can be run locally to verify ingest correctness after changes.
  - [ ] Documentation clearly explains how this Python server ingest layer fits into the three-layer Cursor instrumentation strategy from `STARTHERE.md`, and how to run/verify it during development.


