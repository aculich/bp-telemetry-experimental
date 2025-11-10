# Blueplane Telemetry Core - Setup Guide

## Prerequisites

- Python 3.11 or later
- Redis server (running on localhost:6379 by default)
- (Optional) Redis TimeSeries module for advanced metrics

## Quick Start

### 1. Set Up Virtual Environment

```bash
cd experiment/core
./scripts/setup_venv.sh
```

This will:
- Create a virtual environment at `.venv/`
- Install all dependencies
- Set up the project

### 2. Activate Virtual Environment

```bash
source scripts/activate_venv.sh
# Or manually:
source .venv/bin/activate
```

### 3. Test Setup

```bash
python scripts/test_setup.py
```

This verifies:
- ✅ Redis connection
- ✅ SQLite database initialization
- ✅ Redis Streams consumer groups

### 4. Start the Server

**Option A: Full Server (Fast Path + Slow Path + API)**

```bash
# Terminal 1: Processing server
python scripts/run_server.py

# Terminal 2: API server
python scripts/run_api_server.py
```

**Option B: API Server Only** (if processing is running elsewhere)

```bash
python scripts/run_api_server.py
```

### 5. Use the CLI

```bash
# View metrics
blueplane metrics

# List sessions
blueplane sessions

# Analyze a session
blueplane analyze <session_id>

# Export data
blueplane export --format json --output data.json
```

## Architecture Overview

The system consists of three main components:

1. **Processing Server** (`run_server.py`)
   - Fast path: Consumes events from Redis Streams, writes to SQLite
   - Slow path: Enriches events, calculates metrics, builds conversations

2. **API Server** (`run_api_server.py`)
   - REST API endpoints for accessing telemetry data
   - WebSocket endpoints for real-time updates

3. **CLI** (`blueplane` command)
   - Terminal interface for querying metrics and sessions

## Configuration

Configuration is managed via environment variables or `config.py`:

```bash
export BLUEPLANE_DATA_DIR=~/.blueplane
export BLUEPLANE_REDIS_HOST=localhost
export BLUEPLANE_REDIS_PORT=6379
export BLUEPLANE_PORT=7531
```

## Data Storage

- **SQLite**: `~/.blueplane/telemetry.db`
  - Raw traces (compressed with zlib)
  - Conversations (structured data)
  
- **Redis**: Local Redis instance
  - Message queue (`telemetry:events`)
  - CDC queue (`cdc:events`)
  - Metrics (TimeSeries or sorted sets)

## API Endpoints

- `GET /api/v1/metrics` - Get current metrics
- `GET /api/v1/sessions` - List sessions
- `GET /api/v1/sessions/{id}` - Get session details
- `GET /api/v1/sessions/{id}/analysis` - Analyze session
- `GET /api/v1/conversations/{id}` - Get conversation flow
- `GET /api/v1/insights` - Get AI insights
- `GET /api/v1/export` - Export data
- `WS /ws/metrics` - Real-time metrics stream
- `WS /ws/events` - Real-time events stream
- `GET /health` - Health check

## Troubleshooting

### Redis Connection Failed

```bash
# Check if Redis is running
redis-cli ping

# Start Redis (macOS)
brew services start redis

# Start Redis (Linux)
sudo systemctl start redis
```

### Database Errors

```bash
# Check database file
ls -lh ~/.blueplane/telemetry.db

# Remove and recreate (WARNING: deletes all data)
rm ~/.blueplane/telemetry.db
python scripts/test_setup.py
```

### Port Already in Use

```bash
# Change port via environment variable
export BLUEPLANE_PORT=7532
python scripts/run_api_server.py
```

## Development

### Install in Development Mode

```bash
source .venv/bin/activate
pip install -e .
```

### Run Tests

```bash
# TODO: Add tests
pytest tests/
```

### Code Style

```bash
# Format code
black src/

# Lint code
ruff check src/
```

## Next Steps

1. **Layer 1 Capture**: Implement IDE hooks for Claude Code and Cursor
2. **Testing**: Add comprehensive test suite
3. **Monitoring**: Add instrumentation and observability
4. **Documentation**: Expand API documentation

## Support

For issues or questions, refer to:
- Architecture documentation: `docs/ARCHITECTURE.md`
- Implementation status: `README_IMPLEMENTATION.md`
- Project overview: `../design/overview.md`

