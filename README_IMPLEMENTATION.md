# Blueplane Telemetry Core - Implementation Status

## Overview

This document tracks the implementation progress of the Blueplane Telemetry Core experimental system.

## Current Status

### ✅ Completed Components

1. **Project Structure**
   - Python package layout (`src/blueplane/`)
   - Dependency management (`pyproject.toml`)
   - Configuration system (`config.py`)

2. **Database Layer**
   - SQLite raw trace storage with zlib compression (`sqlite_traces.py`)
   - SQLite conversation storage (`sqlite_conversations.py`)
   - Redis metrics storage (`redis_metrics.py`)
   - Redis CDC work queue (`redis_cdc.py`)

3. **Fast Path (Layer 2)**
   - Redis Streams consumer (`fast_path/consumer.py`)
   - SQLite batch writer with compression (`fast_path/writer.py`)
   - CDC publisher (`fast_path/cdc.py`)

4. **Setup & Testing**
   - Test script (`scripts/test_setup.py`)
   - Server runner script (`scripts/run_server.py`)

### ✅ Recently Completed

1. **Slow Path (Layer 2)**
   - ✅ Worker pool manager (`slow_path/worker_pool.py`)
   - ✅ Metrics worker (`slow_path/metrics_worker.py`)
   - ✅ Conversation worker (`slow_path/conversation_worker.py`)

2. **Layer 2 Server**
   - ✅ REST API endpoints (`server/api.py`)
   - ✅ WebSocket endpoints (`server/websocket.py`)

3. **Layer 3 CLI**
   - ✅ CLI entry point (`cli/main.py`)
   - ✅ Command implementations (`cli/commands/`)
     - `metrics` - Display current metrics
     - `sessions` - List sessions
     - `analyze` - Analyze session
     - `export` - Export data

### ⏳ Pending

1. **Layer 3 MCP Server**
   - MCP server implementation (`mcp/server.py`)

2. **Tests**
   - Unit tests for storage layer
   - Integration tests for fast path
   - End-to-end tests

3. **Layer 1 Capture**
   - IDE hooks for Claude Code
   - IDE hooks for Cursor
   - Database monitors

## Quick Start

### Prerequisites

- Python 3.11+
- Redis server running on localhost:6379
- (Optional) Redis TimeSeries module (for advanced metrics)

### Setup

1. **Set up virtual environment**:
   ```bash
   cd experiment/core
   ./scripts/setup_venv.sh
   source scripts/activate_venv.sh
   ```

2. **Test setup**:
   ```bash
   python scripts/test_setup.py
   ```

3. **Run servers**:
   ```bash
   # Terminal 1: Processing server (fast + slow path)
   python scripts/run_server.py
   
   # Terminal 2: API server
   python scripts/run_api_server.py
   ```

4. **Use CLI**:
   ```bash
   blueplane metrics
   blueplane sessions
   blueplane analyze <session_id>
   ```

See [SETUP.md](./SETUP.md) for detailed setup instructions.

### Architecture

The system follows a three-layer architecture:

- **Layer 1**: Capture (hooks, database monitors) - Not yet implemented
- **Layer 2**: Processing (fast path + slow path) - Fast path implemented
- **Layer 3**: Interfaces (CLI, MCP, Dashboard) - Not yet implemented

## Implementation Details

### Fast Path

The fast path consumer:
1. Reads events from Redis Streams (`telemetry:events`)
2. Batches events (100 events or 100ms timeout)
3. Compresses and writes to SQLite `raw_traces` table
4. Publishes CDC events to Redis Streams (`cdc:events`)
5. Acknowledges processed messages

**Performance Targets**:
- <10ms P95 latency per batch (100 events)
- 7-10x compression ratio with zlib level 6
- Zero database reads (pure writes)

### Database Schema

**SQLite (`telemetry.db`)**:
- `raw_traces`: Compressed raw events (Layer 2 internal)
- `conversations`: Structured conversation data (Layer 2 & 3)
- `conversation_turns`: Individual conversation turns
- `code_changes`: Code modification tracking

**Redis**:
- `telemetry:events`: Main message queue (Layer 1 → Layer 2)
- `cdc:events`: Change data capture queue (Fast path → Slow path)
- `telemetry:dlq`: Dead letter queue for failed messages
- `metric:*`: Real-time metrics (TimeSeries or sorted sets)

## Next Steps

1. Implement slow path workers (metrics, conversation reconstruction)
2. Implement Layer 2 REST API server
3. Implement CLI interface
4. Add comprehensive tests
5. Add instrumentation and monitoring

## Notes

- The fast path is designed to never block - errors are logged but don't stop ingestion
- CDC events are published fire-and-forget (failures don't affect fast path)
- SQLite uses WAL mode for concurrent read/write access
- All sensitive data is hashed/compressed before storage

