# TODO: Health Monitoring & Packaging

Based on Ben's request and codebase analysis, this document outlines the tasks for implementing health monitoring and exploring packaging approaches.

## Overview

This work focuses on two main areas:
1. **Health Monitoring Layer**: At-a-glance view of system health (Redis queue, database writes, hook/trace capture)
2. **Packaging Exploration**: Research and implement distribution strategy

---

## Part 1: Health Monitoring Layer

### Current State Analysis

**Existing Monitoring:**
- Basic `/health` endpoint in `src/blueplane/server/api.py` (lines 383-402)
  - Checks database connection (SQLite)
  - Checks Redis connection
  - Returns simple healthy/unhealthy status
- Backpressure monitoring in `WorkerPoolManager._monitor_backpressure()` (lines 146-181)
  - Monitors CDC queue depth
  - Logs warnings at thresholds (10k, 50k, 100k)
  - No metrics exposed or persisted

**Gaps Identified:**
1. No visibility into Redis message queue (`telemetry:events`) health
2. No tracking of database write performance/latency
3. No monitoring of hook execution (success/failure rates)
4. No monitoring of trace capture (transcript monitor, database monitor)
5. No aggregated health dashboard/metrics endpoint
6. No historical health metrics storage

### 1.1 Redis Message Queue Health Monitoring

**Location**: `src/blueplane/monitoring/queue_health.py` (new file)

**Requirements:**
- Monitor `telemetry:events` stream health
- Track queue depth (XINFO STREAM)
- Track consumer lag (XPENDING analysis)
- Track consumer group health (XINFO GROUPS)
- Track dead letter queue size (`telemetry:dlq`)
- Calculate processing rate (events/second)
- Detect stuck consumers

**Metrics to Track:**
```python
{
    "queue_depth": int,              # Current stream length
    "pending_messages": int,         # Unprocessed messages in PEL
    "oldest_pending_age_ms": int,     # Age of oldest pending message
    "consumer_count": int,            # Active consumers in group
    "processing_rate_events_per_sec": float,
    "dlq_size": int,                 # Dead letter queue size
    "consumer_lag_ms": int,           # Time since last processed message
    "health_status": "green|yellow|orange|red"
}
```

**Implementation Tasks:**
- [ ] Create `QueueHealthMonitor` class
- [ ] Implement Redis Stream info collection (XINFO, XPENDING)
- [ ] Calculate processing rate from stream timestamps
- [ ] Detect stuck consumers (no ACK in >30 seconds)
- [ ] Add health status calculation (green/yellow/orange/red thresholds)
- [ ] Add to health monitoring service

**Thresholds:**
- Green: queue_depth < 1000, pending < 100, lag < 5s
- Yellow: queue_depth 1000-10000, pending 100-1000, lag 5-30s
- Orange: queue_depth 10000-50000, pending 1000-5000, lag 30-60s
- Red: queue_depth > 50000, pending > 5000, lag > 60s

### 1.2 Database Write Health Monitoring

**Location**: `src/blueplane/monitoring/database_health.py` (new file)

**Requirements:**
- Monitor SQLite write performance
- Track write latency (P50, P95, P99)
- Track write throughput (events/second)
- Monitor database file size and growth rate
- Check WAL file size
- Monitor compression ratio
- Track write errors/failures

**Metrics to Track:**
```python
{
    "write_latency_p50_ms": float,
    "write_latency_p95_ms": float,
    "write_latency_p99_ms": float,
    "write_throughput_events_per_sec": float,
    "db_size_mb": float,
    "wal_size_mb": float,
    "compression_ratio": float,      # compressed_size / uncompressed_size
    "write_errors_count": int,
    "last_write_timestamp": str,
    "health_status": "green|yellow|orange|red"
}
```

**Implementation Tasks:**
- [ ] Create `DatabaseHealthMonitor` class
- [ ] Instrument `SQLiteBatchWriter.write_batch()` with timing
- [ ] Track write latencies using histogram
- [ ] Calculate compression ratio from batch stats
- [ ] Monitor database file size (periodic checks)
- [ ] Track WAL file size
- [ ] Add error counting
- [ ] Add to health monitoring service

**Thresholds:**
- Green: P95 < 10ms, throughput > 100 events/sec, no errors
- Yellow: P95 10-50ms, throughput 50-100 events/sec, <1% errors
- Orange: P95 50-100ms, throughput 10-50 events/sec, 1-5% errors
- Red: P95 > 100ms, throughput < 10 events/sec, >5% errors

### 1.3 Hook and Trace Capture Health Monitoring

**Location**: `src/blueplane/monitoring/capture_health.py` (new file)

**Requirements:**
- Monitor hook execution (Claude Code and Cursor)
- Track hook success/failure rates
- Monitor transcript file processing
- Monitor database monitor (Cursor) health
- Track event capture rate by platform
- Detect missing hooks or inactive capture

**Metrics to Track:**
```python
{
    "claude_hooks": {
        "total_executions": int,
        "success_count": int,
        "failure_count": int,
        "success_rate": float,
        "last_execution_timestamp": str,
        "hooks_active": {
            "SessionStart": bool,
            "PreToolUse": bool,
            "PostToolUse": bool,
            "UserPromptSubmit": bool,
            "Stop": bool,
            "PreCompact": bool
        }
    },
    "cursor_hooks": {
        "total_executions": int,
        "success_count": int,
        "failure_count": int,
        "success_rate": float,
        "last_execution_timestamp": str,
        "hooks_active": {...}  # Similar to Claude
    },
    "transcript_monitor": {
        "active": bool,
        "files_monitored": int,
        "lines_processed": int,
        "last_activity_timestamp": str,
        "errors_count": int
    },
    "database_monitor": {
        "active": bool,
        "sessions_monitored": int,
        "events_captured": int,
        "last_activity_timestamp": str,
        "errors_count": int
    },
    "capture_rate_events_per_min": float,
    "health_status": "green|yellow|orange|red"
}
```

**Implementation Tasks:**
- [ ] Create `CaptureHealthMonitor` class
- [ ] Add hook execution tracking to `MessageQueueWriter.enqueue()`
  - Track success/failure per hook type
  - Track last execution timestamp
- [ ] Add transcript monitor health tracking
  - Monitor `TranscriptMonitor` activity
  - Track files monitored and lines processed
- [ ] Add database monitor health tracking
  - Monitor `CursorDatabaseMonitor` activity
  - Track sessions and events captured
- [ ] Calculate capture rate from recent events
- [ ] Detect inactive hooks (no events in >5 minutes)
- [ ] Add to health monitoring service

**Thresholds:**
- Green: success_rate > 99%, capture_rate > 10 events/min, all monitors active
- Yellow: success_rate 95-99%, capture_rate 5-10 events/min, some monitors inactive
- Orange: success_rate 90-95%, capture_rate 1-5 events/min, monitors inactive
- Red: success_rate < 90%, capture_rate < 1 events/min, monitors down

### 1.4 Unified Health Monitoring Service

**Location**: `src/blueplane/monitoring/health_service.py` (new file)

**Requirements:**
- Aggregate health from all monitors
- Provide at-a-glance status endpoint
- Store health metrics in Redis (time-series)
- Expose health metrics via API
- Provide health dashboard data

**API Endpoints:**
- `GET /api/v1/health` - Overall system health (enhanced)
- `GET /api/v1/health/queue` - Queue-specific health
- `GET /api/v1/health/database` - Database-specific health
- `GET /api/v1/health/capture` - Capture-specific health
- `GET /api/v1/health/metrics` - Historical health metrics

**Implementation Tasks:**
- [ ] Create `HealthService` class
- [ ] Integrate `QueueHealthMonitor`, `DatabaseHealthMonitor`, `CaptureHealthMonitor`
- [ ] Calculate overall health status (worst of all components)
- [ ] Store health metrics in Redis TimeSeries (1-minute intervals)
- [ ] Create FastAPI endpoints for health data
- [ ] Add health metrics to existing `/health` endpoint
- [ ] Create health dashboard data endpoint (for future UI)

**Health Status Calculation:**
```python
overall_status = max(
    queue_health.status,
    database_health.status,
    capture_health.status
)
# green=0, yellow=1, orange=2, red=3
```

### 1.5 Health Metrics Storage

**Location**: `src/blueplane/monitoring/health_storage.py` (new file)

**Requirements:**
- Store health metrics in Redis TimeSeries
- 1-minute resolution, 7-day retention
- Enable historical analysis
- Support health trend visualization

**Implementation Tasks:**
- [ ] Create `HealthMetricsStorage` class
- [ ] Use Redis TimeSeries for metrics storage
- [ ] Store metrics: queue_depth, write_latency_p95, capture_rate, etc.
- [ ] Implement retention policy (7 days)
- [ ] Add query methods for historical data

### 1.6 Integration Points

**Files to Modify:**
- `src/blueplane/server/api.py` - Add health endpoints
- `src/blueplane/fast_path/writer.py` - Add write latency tracking
- `src/blueplane/capture/queue_writer.py` - Add hook execution tracking
- `src/blueplane/capture/transcript_monitor.py` - Add activity tracking
- `src/blueplane/capture/database_monitor.py` - Add activity tracking
- `scripts/run_server.py` - Start health monitoring service

---

## Part 2: Packaging Exploration

### Current State Analysis

**Existing Packaging:**
- `pyproject.toml` configured with hatchling build backend
- Package name: `blueplane-telemetry-core`
- Version: `0.1.0`
- Entry point: `blueplane = blueplane.cli.main:main`
- Dependencies specified
- Optional dev dependencies

**Gaps Identified:**
1. No distribution strategy (PyPI, local wheels, etc.)
2. No installation documentation
3. No hook installation as part of package install
4. No systemd/service files for server
5. No Docker containerization
6. No dependency on Redis/SQLite (assumed installed)
7. No post-install scripts

### 2.1 Packaging Strategy Research

**Options to Explore:**

1. **PyPI Distribution**
   - Public package on PyPI
   - `pip install blueplane-telemetry-core`
   - Pros: Standard, easy installation
   - Cons: Requires public release, versioning strategy

2. **Local Wheel Distribution**
   - Build wheels locally
   - Install via `pip install wheel_file.whl`
   - Pros: Private, version control
   - Cons: Manual distribution

3. **Git-based Installation**
   - `pip install git+https://...`
   - Pros: Always latest, version control
   - Cons: Requires git access, build on install

4. **Standalone Executable**
   - PyInstaller/cx_Freeze
   - Single binary distribution
   - Pros: No Python version dependency
   - Cons: Larger size, platform-specific

5. **Docker Container**
   - Containerized distribution
   - Includes Redis, SQLite
   - Pros: Self-contained, reproducible
   - Cons: Docker dependency

**Research Tasks:**
- [ ] Evaluate each option for this use case
- [ ] Document pros/cons for each
- [ ] Recommend primary and secondary approaches
- [ ] Consider hybrid approach (PyPI + Docker)

### 2.2 Package Structure Improvements

**Current Structure:**
```
blueplane-telemetry-core/
├── src/blueplane/
├── hooks/
├── scripts/
├── tests/
└── pyproject.toml
```

**Improvements Needed:**
- [ ] Ensure all necessary files included in package
- [ ] Add hook scripts to package data
- [ ] Add configuration templates
- [ ] Add service files (systemd, launchd)
- [ ] Add installation scripts

**Tasks:**
- [ ] Review `pyproject.toml` package configuration
- [ ] Add `[tool.hatch.build.targets.wheel.shared-data]` for hooks
- [ ] Add `[tool.hatch.build.targets.wheel.scripts]` for additional scripts
- [ ] Create `MANIFEST.in` if needed for extra files
- [ ] Test package build: `python -m build`

### 2.3 Installation Scripts

**Location**: `src/blueplane/cli/install.py` (new command)

**Requirements:**
- Post-install hook installation
- Redis check/configuration
- Database initialization
- Service setup (optional)

**Tasks:**
- [ ] Create `blueplane install` CLI command
- [ ] Integrate hook installation (`install_hooks.py` logic)
- [ ] Add Redis connectivity check
- [ ] Add database initialization
- [ ] Add service file installation (systemd/launchd)
- [ ] Add verification step

### 2.4 Distribution Artifacts

**Artifacts to Create:**
- [ ] Source distribution (sdist)
- [ ] Wheel distribution (wheel)
- [ ] Docker image (if chosen)
- [ ] Installation documentation
- [ ] Quick start guide

**Tasks:**
- [ ] Set up build process (`python -m build`)
- [ ] Create `.github/workflows/build.yml` for CI/CD
- [ ] Document build process
- [ ] Test installation from each artifact type

### 2.5 Dependency Management

**Current Dependencies:**
- Redis (external)
- SQLite (built-in Python)
- Python 3.11+

**Considerations:**
- [ ] Document Redis installation requirements
- [ ] Consider bundling Redis (Docker only)
- [ ] Document Python version requirements
- [ ] Consider optional dependencies (e.g., dashboard)

**Tasks:**
- [ ] Update `pyproject.toml` with optional dependencies
- [ ] Create `requirements.txt` for easy install
- [ ] Document external dependencies
- [ ] Add dependency check script

### 2.6 Platform-Specific Considerations

**Platforms:**
- macOS (Darwin)
- Linux
- Windows (if supported)

**Tasks:**
- [ ] Test package build on each platform
- [ ] Document platform-specific installation
- [ ] Handle platform-specific service files
- [ ] Test hook installation on each platform

### 2.7 Documentation

**Documentation Needed:**
- [ ] Installation guide
- [ ] Packaging strategy document
- [ ] Distribution process
- [ ] Versioning strategy
- [ ] Release process

**Tasks:**
- [ ] Create `docs/PACKAGING.md`
- [ ] Create `docs/INSTALLATION.md`
- [ ] Update `README.md` with installation instructions
- [ ] Document versioning approach (semver?)

---

## Implementation Priority

### Phase 1: Core Health Monitoring (High Priority)
1. Redis Queue Health Monitoring (1.1)
2. Database Write Health Monitoring (1.2)
3. Unified Health Service (1.4) - Basic version

### Phase 2: Capture Health Monitoring (Medium Priority)
4. Hook and Trace Capture Health (1.3)
5. Health Metrics Storage (1.5)
6. Enhanced Health Service (1.4) - Full version

### Phase 3: Packaging Research (Medium Priority)
7. Packaging Strategy Research (2.1)
8. Package Structure Improvements (2.2)
9. Installation Scripts (2.3)

### Phase 4: Distribution (Lower Priority)
10. Distribution Artifacts (2.4)
11. Dependency Management (2.5)
12. Platform-Specific Considerations (2.6)
13. Documentation (2.7)

---

## Notes

- Health monitoring should be lightweight and not impact performance
- Consider using Redis for health metrics storage (already in use)
- Health endpoints should be fast (<10ms response time)
- Packaging should support both development and production use cases
- Consider backward compatibility when changing package structure

---

## References

- Current health check: `src/blueplane/server/api.py:383-402`
- Backpressure monitoring: `src/blueplane/slow_path/worker_pool.py:146-181`
- Package config: `pyproject.toml`
- Hook installation: `scripts/install_hooks.py`
- Architecture docs: `docs/architecture/`

