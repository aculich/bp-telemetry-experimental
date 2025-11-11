# Cursor Telemetry Capture

Layer 1 telemetry capture system for Cursor IDE using global hooks and VSCode extension.

## Architecture

### Global Hooks Approach

Cursor doesn't support project-level hooks yet, so we install hooks globally at `~/.cursor/hooks/`:

- **Global Hooks**: Fire for ALL Cursor workspaces
- **Extension Events**: Send session start/end events with workspace hash to identify which workspace is active
- **Workspace-Specific Sessions**: Each workspace gets its own session file with unique session ID

### How It Works

```
┌─────────────────────┐
│  Cursor Workspace   │
│   (any project)     │
└──────────┬──────────┘
           │
           ├─ Extension activated
           │  └─> Sends session_start event (workspace_hash, PID)
           │
           ├─ User edits file
           │  └─> Global hook fires (reads workspace session file)
           │      └─> Sends file_edit event (session_id, workspace_hash, PID)
           │
           ├─ User runs command
           │  └─> Global hook fires
           │      └─> Sends shell_execution event
           │
           └─ Extension deactivated
              └─> Sends session_end event
```

## Installation

### Prerequisites

- Cursor IDE installed
- Python 3.11+
- Redis server running (localhost:6379)

### 1. Install Global Hooks

```bash
cd src/capture/cursor
./install_global_hooks.sh
```

This installs hooks to `~/.cursor/hooks/` for all workspaces.

### 2. Install Extension

```bash
cd extension
npm install
npm run compile
code --install-extension .  # Or install via VSCode Extensions panel
```

### 3. Start Redis

```bash
redis-server
```

### 4. Configure (Optional)

Create `~/.blueplane/config.yaml`:

```yaml
redis:
  host: localhost
  port: 6379

privacy:
  opt_out:
    - code_content
    - file_paths

stream:
  name: telemetry:events
  max_length: 10000
```

## Session Tracking

### Session Files

Each workspace gets a unique session file:

```
~/.blueplane/cursor-session/
  ├─ a1b2c3d4e5f6g7h8.json  (workspace 1)
  ├─ 9i8h7g6f5e4d3c2b.json  (workspace 2)
  └─ ...
```

Filename is SHA256 hash of workspace path (truncated to 16 chars).

### Session File Format

```json
{
  "CURSOR_SESSION_ID": "curs_1731283200000_abc123",
  "CURSOR_WORKSPACE_HASH": "a1b2c3d4e5f6g7h8",
  "workspace_path": "/home/user/my-project",
  "updated_at": "2025-11-11T10:30:00.000Z"
}
```

### Session Events

The extension sends session lifecycle events to Redis:

**session_start:**
```json
{
  "hook_type": "session",
  "event_type": "session_start",
  "timestamp": "2025-11-11T10:30:00.000Z",
  "payload": {
    "workspace_path": "/home/user/my-project",
    "session_id": "curs_1731283200000_abc123",
    "workspace_hash": "a1b2c3d4e5f6g7h8"
  },
  "metadata": {
    "pid": 12345,
    "workspace_hash": "a1b2c3d4e5f6g7h8",
    "platform": "cursor"
  }
}
```

**session_end:**
Same format, but `event_type: "session_end"`.

## Hook Scripts

### Available Hooks

All hooks installed to `~/.cursor/hooks/`:

1. **before_submit_prompt.py** - User prompt submission
2. **after_agent_response.py** - AI response completion
3. **before_file_edit.py** - Before file modifications
4. **after_file_edit.py** - After file modifications
5. **before_read_file.py** - Before file reads
6. **before_shell_execution.py** - Before shell commands
7. **after_shell_execution.py** - After shell commands
8. **before_mcp_execution.py** - Before MCP tool execution
9. **after_mcp_execution.py** - After MCP tool execution

### Hook Event Format

```json
{
  "version": "0.1.0",
  "hook_type": "afterFileEdit",
  "event_type": "file_edit",
  "timestamp": "2025-11-11T10:30:00.000Z",
  "payload": {
    "file_path": "<redacted:path>",
    "operation": "edit"
  },
  "metadata": {
    "pid": 12345,
    "workspace_hash": "a1b2c3d4e5f6g7h8"
  }
}
```

## Event Flow

```
Extension Start → session_start event → Redis
     ↓
Hook Fires → Reads session file → Sends event → Redis
     ↓
Extension Stop → session_end event → Redis
```

## Privacy

All hooks respect privacy settings from `~/.blueplane/config.yaml`:

- **Code content**: Never captured by default
- **File paths**: Hashed if `file_paths` opt-out enabled
- **Error messages**: Redacted to error type only
- **Environment vars**: Never logged

See `config/privacy.yaml` for full privacy settings.

## Debugging

### Check Hook Installation

```bash
ls -la ~/.cursor/hooks/
```

Should show all 9 hook scripts + `hook_base.py` + `shared/` directory.

### Check Session File

```bash
cat ~/.blueplane/cursor-session/*.json
```

Should show session info for each workspace.

### Monitor Redis Events

```bash
redis-cli XREAD COUNT 10 STREAMS telemetry:events 0
```

### Extension Logs

View in VSCode:
- `View` → `Output` → Select "Blueplane Telemetry"

## Multiple Workspaces

The global hooks approach supports multiple Cursor workspaces simultaneously:

1. Each workspace gets unique session file (workspace hash)
2. Each workspace has unique session ID
3. Extension sends session events with workspace hash
4. Hooks read workspace-specific session file based on current directory
5. All events tagged with workspace_hash and PID

## Uninstallation

```bash
rm -rf ~/.cursor/hooks
rm -rf ~/.blueplane/cursor-session
```

## Troubleshooting

**Hooks not firing:**
- Check hooks are in `~/.cursor/hooks/` and executable
- Check Redis is running: `redis-cli ping`
- Check extension is activated in VSCode

**Wrong session ID:**
- Check session file for current workspace
- Verify workspace hash matches current directory hash
- Restart extension to create new session

**Events not appearing in Redis:**
- Check Redis connection in extension logs
- Verify config.yaml has correct Redis host/port
- Check for errors in hook execution (silent failures)

## Development

### Testing Hooks

Test individual hooks:

```bash
export CURSOR_SESSION_ID=test-session-123
export CURSOR_WORKSPACE_HASH=abc123def456

cd /path/to/workspace
~/.cursor/hooks/before_submit_prompt.py \
  --workspace-root /path/to/workspace \
  --generation-id gen-456 \
  --prompt-length 150
```

Check Redis queue:

```bash
redis-cli XLEN telemetry:events
redis-cli XREAD COUNT 1 STREAMS telemetry:events 0-0
```

### Adding New Hooks

1. Create new hook script in `hooks/`
2. Extend `CursorHookBase` class
3. Implement `execute()` method
4. Update `install_global_hooks.sh` to copy new hook
5. Make executable: `chmod +x hooks/your_hook.py`

## Architecture

See main documentation:
- [Layer 1 Capture](../../../docs/architecture/layer1_capture.md)
- [Database Architecture](../../../docs/architecture/layer2_db_architecture.md)
- [Overall Architecture](../../../docs/ARCHITECTURE.md)

## Next Steps

After installation, Layer 2 (Processing) will:
1. Read events from Redis Streams
2. Process and enrich events
3. Store in DuckDB (raw traces) and SQLite (conversations)
4. Derive metrics and update Redis TimeSeries

See `docs/architecture/layer2_async_pipeline.md` for details.
