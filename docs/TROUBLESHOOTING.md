# Troubleshooting Guide

## Quick Status Check

Run a comprehensive status check of all components:

```bash
cd /Users/bbalaran/Dev/sierra/blueplane/bp-telemetry-core
python3 scripts/check_status.py
```

Or manually check each component:

```bash
# 1. Check hooks
ls -la ~/.cursor/hooks/*.py | wc -l
cat ~/.cursor/hooks.json | jq '.hooks | length'

# 2. Check Redis queue
redis-cli XLEN telemetry:events
redis-cli XINFO GROUPS telemetry:events

# 3. Check database
sqlite3 ~/.blueplane/telemetry.db "SELECT COUNT(*) FROM raw_traces;"

# 4. Check processing server
ps aux | grep start_server.py
```

---

## Comprehensive Status Check Script

Create `scripts/check_status.py`:

```python
#!/usr/bin/env python3
"""Comprehensive status check for Blueplane Telemetry Core."""

import sys
import json
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_hooks():
    """Check hooks installation status."""
    print("\n1️⃣  HOOKS STATUS")
    print("-" * 70)
    hooks_dir = Path.home() / ".cursor" / "hooks"
    if hooks_dir.exists():
        hook_files = list(hooks_dir.glob("*.py"))
        print(f"✅ Hooks directory exists: {hooks_dir}")
        print(f"   Hook scripts found: {len(hook_files)}")

        hooks_json = Path.home() / ".cursor" / "hooks.json"
        if hooks_json.exists():
            print(f"✅ hooks.json exists")
            try:
                with open(hooks_json) as f:
                    hooks_config = json.load(f)
                    hooks_dict = hooks_config.get("hooks", {})
                    if isinstance(hooks_dict, dict):
                        enabled = sum(1 for h in hooks_dict.values()
                                    if isinstance(h, dict) and h.get("enabled", True))
                        print(f"   Enabled hooks: {enabled}")
            except Exception as e:
                print(f"   ⚠️  Could not parse hooks.json: {e}")
        else:
            print("⚠️  hooks.json not found")
        return True
    else:
        print("❌ Hooks directory not found!")
        return False

def check_database_traces():
    """Check database trace monitoring setup."""
    print("\n2️⃣  DATABASE TRACES STATUS")
    print("-" * 70)
    extension_dir = project_root / "src" / "capture" / "cursor" / "extension"
    if extension_dir.exists():
        compiled_js = list(extension_dir.glob("out/**/*.js"))
        print(f"✅ Extension source exists")
        print(f"   Compiled JS files: {len(compiled_js)}")

        # Check for Cursor database
        cursor_db_paths = [
            Path.home() / "Library/Application Support/Cursor/User/workspaceStorage",
            Path.home() / ".config/Cursor/User/workspaceStorage",
        ]
        for db_path in cursor_db_paths:
            if db_path.exists():
                db_files = list(db_path.glob("*/state.vscdb"))
                if db_files:
                    print(f"✅ Found Cursor database: {db_files[0]}")
                    return True
        print("⚠️  Cursor database not found (extension may not be able to monitor)")
        return False
    else:
        print("⚠️  Extension directory not found")
        return False

def check_redis_queue():
    """Check Redis queue and consumer status."""
    print("\n3️⃣  REDIS QUEUE STATUS")
    print("-" * 70)
    try:
        result = subprocess.run(['redis-cli', 'XLEN', 'telemetry:events'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            queue_len = int(result.stdout.strip())
            print(f"✅ Redis connection: OK")
            print(f"   Events in queue: {queue_len}")

            result = subprocess.run(['redis-cli', 'XINFO', 'GROUPS', 'telemetry:events'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                consumers = 0
                pending = 0
                lag = 0
                for i, line in enumerate(lines):
                    if line == 'consumers' and i+1 < len(lines):
                        try:
                            consumers = int(lines[i+1])
                        except:
                            pass
                    elif line == 'pending' and i+1 < len(lines):
                        try:
                            pending = int(lines[i+1])
                        except:
                            pass
                    elif line == 'lag' and i+1 < len(lines):
                        try:
                            lag = int(lines[i+1])
                        except:
                            pass

                print(f"   Active consumers: {consumers}")
                print(f"   Pending messages: {pending}")
                print(f"   Lag: {lag}")

                if consumers == 0:
                    print("   ⚠️  WARNING: No active consumers!")
                    return False
                elif lag > 100:
                    print(f"   ⚠️  WARNING: High lag ({lag} messages)")
                    return False
                else:
                    print("   ✅ Consumer group healthy")
                    return True
        else:
            print("❌ Redis not responding")
            return False
    except Exception as e:
        print(f"❌ Redis check failed: {e}")
        return False

def check_database():
    """Check database status and content."""
    print("\n4️⃣  DATABASE STATUS")
    print("-" * 70)
    from src.processing.database.sqlite_client import SQLiteClient

    db_path = Path.home() / ".blueplane" / "telemetry.db"
    if db_path.exists():
        print(f"✅ Database exists: {db_path}")
        print(f"   Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")

        try:
            client = SQLiteClient(str(db_path))
            with client.get_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM raw_traces')
                total = cursor.fetchone()[0]
                print(f"   Total events: {total}")

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM raw_traces
                    WHERE timestamp > datetime('now', '-1 hour')
                ''')
                recent = cursor.fetchone()[0]
                print(f"   Events (last hour): {recent}")

                cursor = conn.execute('''
                    SELECT event_type, COUNT(*) as cnt
                    FROM raw_traces
                    GROUP BY event_type
                    ORDER BY cnt DESC
                    LIMIT 10
                ''')
                print("   Event breakdown:")
                for row in cursor.fetchall():
                    print(f"     - {row[0]}: {row[1]}")

                cursor = conn.execute('SELECT COUNT(*) FROM raw_traces WHERE model IS NOT NULL')
                with_model = cursor.fetchone()[0]
                if with_model > 0:
                    print(f"   ✅ Events with model data: {with_model}")
                else:
                    print(f"   ⚠️  No events with model data (hooks may need update)")

                cursor = conn.execute('SELECT COUNT(*) FROM raw_traces WHERE event_type = "database_trace"')
                db_traces = cursor.fetchone()[0]
                if db_traces > 0:
                    print(f"   ✅ Database traces: {db_traces}")
                else:
                    print(f"   ⚠️  No database traces (extension may not be active)")

            return True
        except Exception as e:
            print(f"   ❌ Database error: {e}")
            return False
    else:
        print(f"❌ Database not found: {db_path}")
        return False

def check_processing_server():
    """Check if processing server is running."""
    print("\n5️⃣  PROCESSING SERVER STATUS")
    print("-" * 70)
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    server_processes = [line for line in result.stdout.split('\n')
                       if 'start_server' in line or 'processing.server' in line]
    if server_processes:
        print("✅ Processing server running:")
        for proc in server_processes[:3]:
            parts = proc.split()
            if len(parts) > 1:
                pid = parts[1]
                print(f"   PID: {pid}")
        return True
    else:
        print("❌ Processing server not running!")
        print("   Start with: python scripts/start_server.py")
        return False

def main():
    """Run all status checks."""
    print("=" * 70)
    print("BLUEPLANE TELEMETRY CORE - COMPREHENSIVE STATUS CHECK")
    print("=" * 70)

    results = {
        'hooks': check_hooks(),
        'database_traces': check_database_traces(),
        'redis': check_redis_queue(),
        'database': check_database(),
        'server': check_processing_server(),
    }

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("-" * 70)
    for component, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {component.replace('_', ' ').title()}")

    all_ok = all(results.values())
    print("\n" + "=" * 70)
    if all_ok:
        print("✅ All systems operational")
    else:
        print("⚠️  Some issues detected - see details above")
    print("=" * 70)

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
```

---

## Common Issues and Solutions

### 1. Redis Socket Timeout Error

**Error:**

```
ERROR - Error reading messages: Timeout reading from socket
```

**Cause:**
The Redis `socket_timeout` was too short (1 second) for blocking read operations. When `XREADGROUP` blocks for `block_ms` milliseconds waiting for messages, the socket timeout fires first.

**Solution:**
Already fixed in `config/redis.yaml`:

```yaml
connection_pool:
  socket_timeout: 5.0 # Must be > block_ms (1000ms = 1s)
  socket_connect_timeout: 2.0
  retry_on_timeout: true
```

**How to Apply:**

```bash
# Restart the processing server
# Press Ctrl+C to stop the current server
python scripts/start_server.py
```

---

### 2. Events Stuck in Redis Queue

**Symptom:**

```bash
redis-cli XLEN telemetry:events
# Returns large number (e.g., 403)
```

**Cause:**
Processing server not running or crashed.

**Solution:**

```bash
# Start the processing server
cd /Users/bbalaran/Dev/sierra/blueplane/bp-telemetry-core
python scripts/start_server.py
```

**Monitor Progress:**

```bash
# In another terminal, watch the queue drain
watch -n 1 'redis-cli XLEN telemetry:events'
```

---

### 3. No Model Data or Tokens Captured

**Symptom:**
Database has events but `model` and `tokens_used` columns are empty/NULL.

**Cause:**
Using old hook scripts that only capture metadata, not full content.

**Solution:**

```bash
# Reinstall updated hooks with full content capture
cd src/capture/cursor
./install_global_hooks.sh

# Restart Cursor
# Command Palette → "Developer: Reload Window"
```

**Verify:**
Submit a new prompt in Cursor and check:

```bash
python3 << 'EOF'
from src.processing.database.sqlite_client import SQLiteClient
from pathlib import Path
client = SQLiteClient(str(Path.home() / '.blueplane' / 'telemetry.db'))
with client.get_connection() as conn:
    cursor = conn.execute('''
        SELECT model, tokens_used, timestamp
        FROM raw_traces
        WHERE model IS NOT NULL
        ORDER BY sequence DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f"Model: {row[0]}, Tokens: {row[1]}, Time: {row[2]}")
EOF
```

---

### 4. No Database Traces

**Symptom:**
No events with `event_type = 'database_trace'` in database.

**Cause:**
Cursor extension not running or database monitor failed to start.

**Solution:**

1. Check extension status in Cursor:

   ```
   Command Palette → "Blueplane: Show Status"
   ```

2. If extension not active:

   ```bash
   # Recompile extension
   cd src/capture/cursor/extension
   npm install
   npm run compile

   # Install in Cursor via Extensions panel
   # Look for "Blueplane Cursor Telemetry"
   ```

3. Check extension logs:
   ```
   Command Palette → "Developer: Open Extension Logs"
   Filter by: "Blueplane"
   ```

**Common Extension Issues:**

- Database file not found (Cursor's `state.vscdb`)
- Permission denied reading database
- Database schema mismatch

---

### 5. Permission Denied on Hook Installation

**Error:**

```
cp: /Users/username/.cursor/hooks/...: Operation not permitted
```

**Cause:**
Sandbox restrictions or file system permissions.

**Solution:**

```bash
# Install with sudo if needed
sudo ./install_global_hooks.sh

# Or manually:
sudo mkdir -p ~/.cursor/hooks
sudo cp hooks/*.py ~/.cursor/hooks/
sudo cp -r ../shared ~/.cursor/hooks/
sudo chmod +x ~/.cursor/hooks/*.py
```

---

### 6. Empty event_data BLOB

**Symptom:**
Events in database but `event_data` column is NULL or empty.

**Cause:**
Compression or serialization error during batch write.

**Solution:**
Check processing server logs for errors:

```bash
# Look for write errors
grep "Failed to process batch" ~/.blueplane/logs/processing.log

# Check SQLite writer errors
python3 << 'EOF'
import logging
logging.basicConfig(level=logging.DEBUG)
from src.processing.database.writer import SQLiteBatchWriter
# Test write with sample event
EOF
```

---

### 7. High Memory Usage

**Symptom:**
Processing server using excessive RAM (>500MB).

**Cause:**

- Large backlog in Redis queue
- Batch size too large
- Memory leak in consumer

**Solution:**

1. **Reduce batch size** in `config/redis.yaml`:

   ```yaml
   streams:
     message_queue:
       count: 50 # Reduce from 100
   ```

2. **Enable adaptive backpressure** (already enabled by default)

3. **Monitor memory:**

   ```bash
   # Check Python process memory
   ps aux | grep start_server.py

   # Or use htop/top
   htop -p $(pgrep -f start_server)
   ```

---

### 8. Database Locked Error

**Error:**

```
sqlite3.OperationalError: database is locked
```

**Cause:**
Multiple processes trying to write to SQLite simultaneously.

**Solution:**
SQLite is configured with WAL mode to prevent this, but if it persists:

1. **Check for zombie processes:**

   ```bash
   ps aux | grep start_server
   pkill -f start_server.py
   ```

2. **Verify WAL mode:**

   ```bash
   sqlite3 ~/.blueplane/telemetry.db "PRAGMA journal_mode;"
   # Should return: wal
   ```

3. **Rebuild database** (last resort):
   ```bash
   mv ~/.blueplane/telemetry.db ~/.blueplane/telemetry.db.backup
   python scripts/init_database.py
   ```

---

## Service Status Monitoring

### Real-time Monitoring

**Watch Redis queue:**

```bash
watch -n 1 'redis-cli XLEN telemetry:events'
```

**Monitor processing server logs:**

```bash
tail -f /tmp/bp_server.log
# Or if using log file:
tail -f ~/.blueplane/logs/processing.log
```

**Check database growth:**

```bash
watch -n 5 'sqlite3 ~/.blueplane/telemetry.db "SELECT COUNT(*) FROM raw_traces;"'
```

### Health Check Dashboard

Run comprehensive status check:

```bash
python scripts/check_status.py
```

Expected output:

```
✅ Hooks: 11 scripts installed
✅ Database Traces: Extension compiled, Cursor DB found
✅ Redis Queue: 454 events, 2 consumers, lag: 0
✅ Database: 740 events, 661 in last hour
✅ Processing Server: Running (PID: 85691)
```

---

## Diagnostic Commands

### Check System Health

```bash
# Redis queue length
redis-cli XLEN telemetry:events

# Database event count
sqlite3 ~/.blueplane/telemetry.db "SELECT COUNT(*) FROM raw_traces;"

# Recent events
sqlite3 ~/.blueplane/telemetry.db "SELECT event_type, COUNT(*) FROM raw_traces WHERE timestamp > datetime('now', '-1 hour') GROUP BY event_type;"

# Redis consumer group info
redis-cli XINFO GROUPS telemetry:events

# Processing server status
ps aux | grep start_server.py
```

### Full System Test

```bash
# Run end-to-end test
python scripts/test_end_to_end.py

# Check installation
python scripts/verify_installation.py
```

---

## Getting Help

If issues persist:

1. **Enable debug logging:**

   ```yaml
   # config/redis.yaml
   logging:
     level: DEBUG
   ```

2. **Collect logs:**

   ```bash
   # Processing server logs
   tail -f logs/processing.log

   # Extension logs (in Cursor)
   Command Palette → "Developer: Open Extension Logs"
   ```

3. **Check GitHub issues:**
   - Search existing issues
   - Create new issue with logs and config

---

**Last Updated:** November 11, 2025
