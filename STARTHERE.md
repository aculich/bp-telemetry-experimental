# Developer's Blueprint: Cursor Extension Development & Instrumentation

**Last Updated**: January 2025  
**Purpose**: Complete guide for developing and testing Cursor extensions, plus comprehensive Cursor instrumentation strategies

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Extension Development Workflow](#extension-development-workflow)
3. [Cursor Instrumentation Strategies](#cursor-instrumentation-strategies)
4. [Data Capture Capabilities](#data-capture-capabilities)
5. [Best Practices & Conventions](#best-practices--conventions)
6. [Troubleshooting](#troubleshooting)

---

## Development Environment Setup

### VS Code Launch Configuration

Create `.vscode/launch.json` in your extension directory:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "🚀 Launch Extension",
      "type": "extensionHost",
      "request": "launch",
      "args": [
        "--extensionDevelopmentPath=${workspaceFolder}/src/capture/cursor/extension"
      ],
      "outFiles": [
        "${workspaceFolder}/src/capture/cursor/extension/out/**/*.js"
      ],
      "preLaunchTask": "npm: compile",
      "sourceMaps": true,
      "skipFiles": [
        "<node_internals>/**"
      ],
      "internalConsoleOptions": "neverOpen"
    },
    {
      "name": "🚀 Launch Extension (No Compile)",
      "type": "extensionHost",
      "request": "launch",
      "args": [
        "--extensionDevelopmentPath=${workspaceFolder}/src/capture/cursor/extension"
      ],
      "outFiles": [
        "${workspaceFolder}/src/capture/cursor/extension/out/**/*.js"
      ],
      "sourceMaps": true,
      "skipFiles": [
        "<node_internals>/**"
      ],
      "internalConsoleOptions": "neverOpen"
    }
  ]
}
```

### Build Tasks

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "type": "npm",
      "script": "compile",
      "path": "src/capture/cursor/extension",
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "label": "npm: compile",
      "problemMatcher": "$tsc",
      "presentation": {
        "reveal": "silent",
        "panel": "shared"
      }
    },
    {
      "type": "npm",
      "script": "watch",
      "path": "src/capture/cursor/extension",
      "group": "build",
      "label": "npm: watch",
      "problemMatcher": "$tsc-watch",
      "isBackground": true,
      "presentation": {
        "reveal": "silent",
        "panel": "shared"
      }
    }
  ]
}
```

### Quick Start

1. **Select Launch Configuration**: Press `Ctrl+Shift+D` (or `Cmd+Shift+D`), select "🚀 Launch Extension"
2. **Press F5**: Launches Extension Development Host (compiles first)
3. **Set Breakpoints**: In TypeScript files (`src/`)
4. **Debug**: Use VS Code debugger controls

---

## Extension Development Workflow

### Recommended Workflow

**Terminal 1: Watch Mode** (Auto-compile on changes)
```bash
cd src/capture/cursor/extension
npm run watch
```

**VS Code: Extension Development Host**
- Press `F5` to launch
- New window opens with your extension loaded
- Make changes → Save → Press `Ctrl+R` (Cmd+R) in Extension Host window to reload

### Hot Reload Behavior

**What Reloads Automatically (Ctrl+R)**:
- ✅ TypeScript code changes (after compilation)
- ✅ Command implementations
- ✅ Extension activation logic
- ✅ Configuration changes
- ✅ Most extension functionality

**What Requires Full Restart (F5 again)**:
- ❌ `package.json` changes (commands, configuration, views)
- ❌ Extension manifest changes
- ❌ New files added to `contributes`
- ❌ Changes to activation events

### Keyboard Shortcuts

- **F5**: Start/Launch Extension Development Host
- **Shift+F5**: Stop Extension Development Host
- **Ctrl+R** (Cmd+R): Reload Extension Development Host window (fast reload)
- **Ctrl+Shift+P** → "Developer: Reload Window": Alternative reload method

### Debugging Tips

1. **Breakpoints**: Set in TypeScript files (`src/`), they'll hit when code executes
2. **Console Output**: `console.log()` appears in **Debug Console** in VS Code
3. **Extension Host Output**: Check Output panel → "Blueplane Telemetry" channel
4. **Debug Console**: Evaluate expressions, access extension variables

---

## Cursor Instrumentation Strategies

### Three-Layer Approach

Cursor instrumentation requires a **multi-pronged approach** because no single method captures everything:

1. **Python Hooks** (Real-time events)
2. **TypeScript Extension** (Workspace storage access)
3. **Database Monitoring** (On-disk data)

---

### Layer 1: Python Hooks (Real-Time Events)

**Location**: `~/.cursor/hooks/`

**Available Hooks** (9 total):

1. **before_submit_prompt.py** - User prompt submission
2. **after_agent_response.py** - AI response completion
3. **before_file_edit.py** - Before file modifications
4. **after_file_edit.py** - After file modifications
5. **before_read_file.py** - Before file reads
6. **before_shell_execution.py** - Before shell commands
7. **after_shell_execution.py** - After shell commands
8. **before_mcp_execution.py** - Before MCP tool execution
9. **after_mcp_execution.py** - After MCP tool execution

**Hook Input Format**:
```json
{
  "conversation_id": "string",
  "generation_id": "string",
  "hook_event_name": "string",
  "workspace_roots": ["<path>"]
}
```

**Hook Output**: JSON events sent to Redis Streams

**Installation**:
```bash
cd src/capture/cursor
./install_global_hooks.sh
```

**What Hooks CAN Capture**:
- ✅ Tool usage (MCP execution hooks)
- ✅ File operations (read/edit hooks)
- ✅ Shell commands (execution hooks)
- ✅ User prompts (before_submit_prompt)
- ✅ Agent responses (after_agent_response)

**What Hooks CANNOT Capture**:
- ❌ Model information (not in hook input)
- ❌ Token usage (not available)
- ❌ Request duration (not available)
- ❌ Full conversation history (only current event)

---

### Layer 2: TypeScript Extension (Workspace Storage)

**Purpose**: Access Cursor's workspace storage for data hooks don't provide

**Key API**: `vscode.workspaceState.get(key)`

**Critical Storage Keys**:
- `composerData:{composerId}` - Full composer conversation data

**Implementation Pattern**:
```typescript
import * as vscode from "vscode";

export class WorkspaceStorageReader {
  constructor(
    private context: vscode.ExtensionContext,
    private queueWriter: QueueWriter
  ) {}

  async loadComposerData(composerId: string): Promise<ComposerStorage | null> {
    const workspaceState = this.context.workspaceState;
    const key = `composerData:${composerId}`;
    const data = workspaceState.get(key);
    return data ? { [composerId]: data } : null;
  }
}
```

**What Workspace Storage CAN Capture**:
- ✅ **Model Information**: `modelConfig.modelName` (composer-level), `modelInfo.modelName` (message-level)
- ✅ **Tool Usage**: `capabilities[type=15]`, `toolFormerData` (version >= 3)
- ✅ **Agent Mode**: `unifiedMode`, `forceMode`
- ✅ **Full Conversations**: `nativeComposers` structure with complete message history

**Discovery Pattern**:
```typescript
// 1. Read composer IDs from database
const composerIds = await this.discoverComposerIds();

// 2. Read workspace storage for each composer
for (const composerId of composerIds) {
  const data = await this.loadComposerData(composerId);
  // Process composer data...
}
```

---

### Layer 3: Database Monitoring (On-Disk Data)

**Purpose**: Read Cursor's SQLite database for metadata and generation history

**⚠️ CRITICAL DISCOVERY**: Full conversation data is stored in **GLOBAL storage**, not workspace storage!

#### Database Locations

**Workspace-Level Storage** (Per-Workspace):
- **macOS**: `~/Library/Application Support/Cursor/User/workspaceStorage/{hash}/state.vscdb`
- **Linux**: `~/.config/Cursor/User/workspaceStorage/{hash}/state.vscdb`
- **Windows**: `~/AppData/Roaming/Cursor/User/workspaceStorage/{hash}/state.vscdb`

**Global Storage** (User-Level, All Workspaces):
- **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`
- **Linux**: `~/.config/Cursor/User/globalStorage/state.vscdb`
- **Windows**: `~/AppData/Roaming/Cursor/User/globalStorage/state.vscdb`

#### Database Tables

**ItemTable** (Workspace & Global):
- Key-value storage for workspace-specific and global configuration
- **Workspace keys**: `composer.composerData` (metadata only), `aiService.generations`, `aiService.prompts`
- **Global keys**: Various configuration keys

**cursorDiskKV** (Global Storage - CRITICAL):
- **Primary storage for full composer conversations**
- Key pattern: `composerData:{composerId}`
- Contains: Full composer data WITH embedded bubbles (conversation array)
- **Key Finding**: Bubbles are embedded in `conversation` array, NOT stored as separate `bubbleData:{id}` entries

#### Data Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Workspace Storage (ItemTable)                               │
│ Key: composer.composerData                                  │
│ Contains: Metadata only (IDs, names, timestamps)           │
│                                                             │
│ Structure:                                                  │
│ {                                                           │
│   "allComposers": [                                         │
│     { composerId, name, createdAt, lastUpdatedAt }          │
│   ]                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ composerId references
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Global Storage (cursorDiskKV)                               │
│ Key: composerData:{composerId}                              │
│ Contains: Full composer data WITH embedded bubbles          │
│                                                             │
│ Structure:                                                  │
│ {                                                           │
│   composerId, name, createdAt, lastUpdatedAt,              │
│   conversation: [                                           │
│     { bubbleId, type, text, ... }  ← Bubbles embedded here  │
│   ]                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

#### Query Patterns

**Step 1: Get Composer Metadata (Workspace Storage)**
```typescript
// Query workspace storage ItemTable
const row = db
  .prepare('SELECT value FROM ItemTable WHERE key = ?')
  .get('composer.composerData');

const composerMetadata = JSON.parse(row.value.toString('utf-8'));
// Returns: { allComposers: [{ composerId, name, createdAt, ... }] }
```

**Step 2: Get Full Composer Data (Global Storage)**
```typescript
// Query global storage cursorDiskKV
const globalDb = new Database(globalStoragePath, { readonly: true });
const row = globalDb
  .prepare('SELECT value FROM cursorDiskKV WHERE key = ?')
  .get(`composerData:${composerId}`);

const fullComposerData = JSON.parse(row.value.toString('utf-8'));
// Returns: { composerId, name, conversation: [...], modelConfig: {...}, ... }
```

**Key Keys**:
- **Workspace ItemTable**: `composer.composerData` (metadata), `aiService.generations`, `aiService.prompts`
- **Global cursorDiskKV**: `composerData:{composerId}` (full conversations with embedded bubbles)

**Read-Only Access Pattern** (CRITICAL):
```typescript
// NEVER write to Cursor's database - only read!
const db = new Database(dbPath, { readonly: true });

// Configure for safe concurrent reads
db.pragma('journal_mode=WAL');        // Write-Ahead Logging
db.pragma('read_uncommitted=1');       // Read uncommitted data
db.pragma('query_only=1');             // Explicit read-only mode

// Read with retry logic (Cursor may be writing)
const row = db
  .prepare('SELECT value FROM ItemTable WHERE key = ?')
  .get('composer.composerData');

const composerData = JSON.parse(row.value.toString('utf-8'));
```

**Querying Global Storage (cursorDiskKV)**:
```typescript
// Open global storage database
const globalDbPath = path.join(
  os.homedir(),
  'Library/Application Support/Cursor/User/globalStorage/state.vscdb'
);
const globalDb = new Database(globalDbPath, { readonly: true });

// Configure for safe reads
globalDb.pragma('journal_mode=WAL');
globalDb.pragma('read_uncommitted=1');
globalDb.pragma('query_only=1');

// Query for composer data (use LIKE for pattern matching)
const rows = globalDb
  .prepare('SELECT key, value FROM cursorDiskKV WHERE key LIKE ?')
  .all('composerData:%');

// Or query specific composer
const row = globalDb
  .prepare('SELECT value FROM cursorDiskKV WHERE key = ?')
  .get(`composerData:${composerId}`);

const fullComposerData = JSON.parse(row.value.toString('utf-8'));
```

**Retry Logic** (Required):
```typescript
async function readWithRetry<T>(
  operation: () => T,
  maxRetries: number = 3,
  retryDelay: number = 500
): Promise<T | null> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return operation();
    } catch (error) {
      const errorMsg = error.message.toLowerCase();
      
      // Retry on lock/malformed errors
      if (errorMsg.includes('locked') || 
          errorMsg.includes('malformed') || 
          errorMsg.includes('disk image')) {
        
        if (attempt < maxRetries - 1) {
          await sleep(retryDelay * (attempt + 1)); // Exponential backoff
          continue;
        }
      }
      
      throw error;
    }
  }
  return null;
}
```

**What Workspace Database CAN Capture**:
- ✅ Generation metadata (UUIDs, timestamps, types)
- ✅ Composer IDs and session metadata (from `composer.composerData`)
- ✅ Prompt history (`aiService.prompts`)
- ✅ Generation history (`aiService.generations`)

**What Global Database CAN Capture**:
- ✅ **Full composer conversations** with embedded bubbles (`cursorDiskKV.composerData:{id}`)
- ✅ **Model configuration** (`modelConfig.modelName` at composer level)
- ✅ **Message-level model info** (`conversation[].modelInfo.modelName`)
- ✅ **Tool usage data** (`capabilitiesRan`, `capabilityStatuses`)
- ✅ **Agent mode** (`unifiedMode`, `forceMode`)
- ✅ **Timing information** (`timingInfo.clientStartTime`, etc.)

**What Database CANNOT Capture**:
- ❌ Token usage per message (only cumulative `tokenCountUpUntilHere` available)
- ❌ Request duration (timing info available but not duration calculation)
- ❌ Thinking/reasoning content (not reliably persisted, may be in `intermediateChunks`)

---

## Data Capture Capabilities

### Complete Data Availability Matrix

| Data Type | Python Hooks | Workspace Storage | Database | Status |
|-----------|-------------|------------------|----------|--------|
| **Model Name** | ❌ | ✅ `modelConfig.modelName`<br>`modelInfo.modelName` | ❌ | ✅ **AVAILABLE** |
| **Tool Usage** | ✅ `beforeMCPExecution`<br>`afterMCPExecution` | ✅ `capabilities[15]`<br>`toolFormerData` | ❌ | ✅ **AVAILABLE** |
| **Agent Mode** | ❌ | ✅ `unifiedMode`<br>`forceMode` | ✅ `composer.composerData` | ✅ **AVAILABLE** |
| **Token Usage** | ❌ | ❌ | ❌ | ❌ **NOT AVAILABLE** |
| **Duration** | ❌ | ⚠️ Partial (VS Code only) | ❌ | ❌ **NOT AVAILABLE** |
| **Full Conversations** | ⚠️ Partial (current event) | ✅ `nativeComposers`<br>✅ Global `cursorDiskKV` | ✅ Global `cursorDiskKV` | ✅ **AVAILABLE** |
| **File Edits** | ✅ `beforeFileEdit`<br>`afterFileEdit` | ❌ | ❌ | ✅ **AVAILABLE** |
| **Shell Commands** | ✅ `beforeShellExecution`<br>`afterShellExecution` | ❌ | ❌ | ✅ **AVAILABLE** |
| **User Prompts** | ✅ `beforeSubmitPrompt` | ✅ In conversations | ❌ | ✅ **AVAILABLE** |
| **Agent Responses** | ✅ `afterAgentResponse` | ✅ In conversations | ❌ | ✅ **AVAILABLE** |

---

### Model Information Extraction

**Source**: Global Storage (`cursorDiskKV.composerData:{composerId}`)

**⚠️ CRITICAL**: Model information is **NOT stored at bubble level** in database. Must extract from composer-level or message-level fields.

**Structure**:
```typescript
interface NativeComposer {
  modelConfig?: {
    modelName?: string;  // Composer-level (most recent model)
  };
  conversation: Array<{
    modelInfo?: {
      modelName?: string;  // Message-level (per message, not always present)
    };
    // Note: modelType and aiStreamingSettings are NOT persisted per bubble
  }>;
}
```

**Extraction Logic** (Enhanced):
```typescript
function extractModelName(composer: NativeComposer, message?: any): string {
  // Priority 1: Message-level model info (most accurate)
  if (message?.modelInfo?.modelName) {
    return message.modelInfo.modelName;
  }
  
  // Priority 2: Composer-level model config (fallback)
  if (composer.modelConfig?.modelName) {
    return composer.modelConfig.modelName;
  }
  
  // Priority 3: Check for model in other locations (if available)
  // Note: modelType is NOT persisted, only modelName
  
  return "";  // Not available
}
```

**Display Format** (for markdown/conversation output):
```typescript
function formatModelInfo(message: NormalizedMessage, composer: NativeComposer): string {
  const modelName = extractModelName(composer, message);
  if (!modelName) return "";
  
  // Format: "model claude-3-5-sonnet-20241022"
  return `model ${modelName}`;
}
```

**Limitations** (from Ben's research):
- Only **most recent model** per composer is stored at composer level
- Individual messages may have `modelInfo.modelName`, but not consistently populated
- `modelType` and `aiStreamingSettings` are **NOT persisted** (server-side only)
- Historical model usage is limited (see SpecStory changelog v0.20.0)
- Model information may be missing for older conversations

---

### Tool Usage Extraction

**Source**: Global Storage (`cursorDiskKV.composerData:{id}`)

**⚠️ IMPORTANT**: Tool usage structure differs from expected format!

**Actual Structure** (from Ben's research):
- **NOT**: `toolFormerdata.toolCalls[]` array (expected but not found)
- **ACTUAL**: `capabilitiesRan` dict with capability names as keys
- **ALSO**: `capabilityStatuses` dict (may serve similar purpose)
- **ALSO**: `codeBlocks` array (may contain tool execution results)

**Extraction Logic** (Corrected):
```typescript
function extractToolUsage(composer: NativeComposer): any[] {
  const tools: any[] = [];
  
  if (!composer.conversation) {
    return tools;
  }
  
  // Process each conversation message
  for (const message of composer.conversation) {
    // Check for tool usage (capabilityType 15)
    if (message.capabilityType === 15) {
      // Try multiple sources for tool data
      let toolData: any = null;
      
      // Method 1: capabilitiesRan dict (actual structure)
      if (message.capabilitiesRan) {
        toolData = message.capabilitiesRan;
      }
      // Method 2: capabilityStatuses (alternative structure)
      else if (message.capabilityStatuses) {
        toolData = message.capabilityStatuses;
      }
      // Method 3: codeBlocks (may contain execution results)
      else if (message.codeBlocks && message.codeBlocks.length > 0) {
        toolData = { codeBlocks: message.codeBlocks };
      }
      
      if (toolData) {
        tools.push({
          bubble_id: message.bubbleId,
          tool_data: toolData,
          capability_type: message.capabilityType,
          version: composer._v,
        });
      }
    }
  }
  
  return tools;
}
```

**Legacy Support** (if needed for older versions):
```typescript
// For version < 3, may need to check capabilities array
if (composer.capabilities) {
  const toolCapability = composer.capabilities.find(c => c.type === 15);
  if (toolCapability?.data?.bubbleDataMap) {
    try {
      const bubbleDataMap = JSON.parse(toolCapability.data.bubbleDataMap);
      toolData = bubbleDataMap[message.bubbleId];
    } catch (error) {
      console.error("Error parsing bubbleDataMap:", error);
    }
  }
}
```

---

### Agent Mode Extraction

**Source**: Workspace Storage or Database

**Priority**: `forceMode` > `unifiedMode`

**Extraction Logic**:
```typescript
function extractAgentMode(composer: NativeComposer): string {
  return composer.forceMode || composer.unifiedMode || "";
}
```

**Values**: `"agent"` | `"chat"` | `"edit"`

---

## Best Practices & Conventions

### 1. Privacy-First Design

**Never Capture**:
- ❌ Code content (unless explicitly opted-in)
- ❌ Environment variables
- ❌ File paths (hash if needed)
- ❌ Sensitive user data

**Always Redact**:
- Error messages → Error type only
- File paths → Hashed if privacy enabled
- User input → Sanitize before storage

### 2. Performance Optimization

**Database Access**:
- ✅ Read-only mode always
- ✅ Short timeouts (< 2 seconds)
- ✅ Retry with exponential backoff
- ✅ Don't hold locks
- ✅ Use WAL mode for concurrent reads

**Workspace Storage**:
- ✅ Poll at reasonable intervals (5 seconds)
- ✅ Cache composer data
- ✅ Background processing only
- ✅ Never block extension activation

**Hooks**:
- ✅ Silent failure mode
- ✅ Fast execution (< 100ms)
- ✅ Don't block Cursor operations
- ✅ Log errors to stderr only

### 3. Error Handling

**Pattern**:
```typescript
try {
  // Operation
} catch (error) {
  console.error("Error description:", error);
  // Graceful fallback
  return null; // or default value
}
```

**Never**:
- ❌ Throw unhandled exceptions
- ❌ Block Cursor operations
- ❌ Show error dialogs to users
- ❌ Crash the extension

### 4. Session Management

**Workspace-Specific Sessions**:
- Each workspace gets unique session ID
- Session file: `~/.blueplane/cursor-session/{workspace_hash}.json`
- Workspace hash = SHA256(workspace_path) truncated to 16 chars

**Session Lifecycle**:
1. Extension activated → `session_start` event
2. Hooks fire → Read session file → Send events
3. Extension deactivated → `session_end` event

### 5. Code Organization

**Extension Structure**:
```
extension/
├── src/
│   ├── extension.ts          # Main entry point
│   ├── workspaceStorageReader.ts  # Workspace storage access
│   ├── sessionManager.ts     # Session lifecycle
│   ├── queueWriter.ts        # Redis integration
│   └── types.ts              # TypeScript types
├── out/                      # Compiled JavaScript
├── package.json
└── tsconfig.json
```

**Python Hooks Structure**:
```
hooks/
├── hook_base.py              # Base class
├── before_submit_prompt.py
├── after_agent_response.py
├── before_file_edit.py
├── after_file_edit.py
├── before_read_file.py
├── before_shell_execution.py
├── after_shell_execution.py
├── before_mcp_execution.py
└── after_mcp_execution.py
```

---

## Troubleshooting

### Extension Not Loading

**Check**:
1. `npm run compile` succeeds
2. `out/extension.js` exists
3. `package.json` `main` field points to correct path
4. No TypeScript errors

**Solution**: Fix compilation errors, ensure `out/` directory exists

### Workspace Storage Not Reading

**Check**:
1. Extension is activated
2. Workspace has active composer
3. `composerData:{composerId}` keys exist
4. No errors in Debug Console

**Solution**: Check extension logs, verify workspace state API access

### Database Access Failing

**Check**:
1. Database path is correct
2. Database file exists
3. Read-only mode enabled
4. Retry logic implemented

**Solution**: 
- Verify database path (workspace hash may have changed)
- Check file permissions
- Implement retry logic with exponential backoff

### Hooks Not Firing

**Check**:
1. Hooks installed: `ls -la ~/.cursor/hooks/`
2. Hooks executable: `chmod +x ~/.cursor/hooks/*.py`
3. `hooks.json` configured correctly
4. Redis running: `redis-cli ping`

**Solution**: Reinstall hooks, verify Redis connection

### Model Information Missing

**Check**:
1. Workspace storage reader is running
2. Composer IDs discovered from database
3. `composerData:{composerId}` keys accessible
4. Model extraction logic correct

**Solution**: 
- Verify workspace storage polling
- Check composer ID discovery
- Verify model extraction from `modelConfig.modelName`

---

## Quick Reference

### Development Commands

```bash
# Compile TypeScript
cd src/capture/cursor/extension
npm run compile

# Watch mode (auto-compile)
npm run watch

# Install hooks
cd src/capture/cursor
./install_global_hooks.sh

# Run Python processing server (ingest pipeline)
cd ../../..
python scripts/start_server.py

# Check Redis
redis-cli ping
redis-cli XREAD COUNT 10 STREAMS telemetry:events 0

# Trace replay tools (SQLite raw_traces)

# Show recent traces for Cursor
python scripts/show_recent_traces.py --platform cursor --limit 50

# Interactive replay of longest Cursor session
python scripts/trace_replay.py --platform cursor --limit 200

# Generate an animated GIF of a replay (requires Pillow)
python scripts/trace_replay.py \
  --platform cursor \
  --limit 60 \
  --gif ./docs/assets/trace_replay/trace_replay_demo.gif
```

### Key File Paths

- **Extension**: `src/capture/cursor/extension/`
- **Hooks**: `src/capture/cursor/hooks/`
- **Workspace Database**: `~/Library/Application Support/Cursor/User/workspaceStorage/{hash}/state.vscdb`
- **Global Database**: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` ⚠️ **CRITICAL**
- **Session Files**: `~/.blueplane/cursor-session/{workspace_hash}.json`
- **Global Hooks**: `~/.cursor/hooks/`

### Debug Checklist

- [ ] Extension compiles without errors
- [ ] Launch configuration selected in VS Code
- [ ] F5 launches Extension Development Host
- [ ] Breakpoints hit in TypeScript files
- [ ] Console logs appear in Debug Console
- [ ] Workspace storage reader initialized
- [ ] Redis connection successful
- [ ] Hooks installed and executable
- [ ] Session files created

---

## Next Steps

1. **Set up development environment** (launch.json, tasks.json)
2. **Install hooks** (`./install_global_hooks.sh`)
3. **Start Redis** (`redis-server`)
4. **Launch extension** (F5)
5. **Test instrumentation** (verify data capture)
6. **Iterate** (make changes, reload, test)

---

**Remember**: Cursor instrumentation requires all three layers (hooks, extension, database) to capture complete telemetry. No single method provides everything!

---

## Key Learnings from Research

### Global vs Workspace Storage

**Critical Discovery**: Full conversation data with embedded bubbles is stored in **GLOBAL storage** (`cursorDiskKV` table), not workspace storage!

- **Workspace storage** (`ItemTable`): Contains metadata only (`composer.composerData` with `allComposers` list)
- **Global storage** (`cursorDiskKV`): Contains full composer data with `conversation` array and embedded bubbles

**Query Pattern**:
1. Query workspace `ItemTable` for composer IDs: `SELECT value FROM ItemTable WHERE key = 'composer.composerData'`
2. Extract `allComposers` array to get composer IDs
3. Query global `cursorDiskKV` for each composer: `SELECT value FROM cursorDiskKV WHERE key = 'composerData:{composerId}'`
4. Parse JSON to get full composer data with embedded bubbles

### Bubbles Are Embedded

**Key Finding**: Bubbles are **NOT** stored as separate `bubbleData:{bubbleId}` entries. They are embedded directly in the `conversation` array within `composerData:{composerId}` entries.

- ❌ **NOT**: `bubbleData:{bubbleId}` keys in cursorDiskKV
- ✅ **ACTUAL**: Bubbles embedded in `composerData:{composerId}.conversation[]` array

### Tool Usage Structure

**Actual Structure** (differs from expected):
- **Expected**: `toolFormerdata.toolCalls[]` array
- **Actual**: `capabilitiesRan` dict with capability names as keys
- **Also**: `capabilityStatuses` dict and `codeBlocks` array may contain tool data

### Model Information

**Availability**:
- ✅ Available at composer level: `modelConfig.modelName`
- ⚠️ Partially available at message level: `conversation[].modelInfo.modelName` (not always present)
- ❌ **NOT** available: `modelType`, `aiStreamingSettings` (server-side only)

### Missing Fields

**Not Persisted** (server-side only or removed):
- `usageData` (composer-level)
- `modelType` (bubble-level)
- `aiStreamingSettings` (bubble-level)
- `thinking` (may be in `intermediateChunks`, needs investigation)
- Per-message token counts (only cumulative `tokenCountUpUntilHere` available)

### Best Practices from Research

1. **Always query both tables**: Workspace `ItemTable` for metadata, global `cursorDiskKV` for full conversations
2. **Handle schema versions**: Check `_v` field for version-specific logic
3. **Retry on errors**: Database may be locked while Cursor is writing
4. **Parse JSON carefully**: Values stored as BLOB/text JSON strings
5. **Check field existence**: Many fields are optional and may not be present

---

## Related Documentation

- **[CURSOR_DATA_LOCATION_MASTER_README.md](./docs/CURSOR_DATA_LOCATION_MASTER_README.md)** - Comprehensive guide to data locations (Ben's research)
- **[MISSING_MARKDOWN_FEATURES.md](./docs/MISSING_MARKDOWN_FEATURES.md)** - What's missing vs reference implementation
- **[example_cursor_capture/](./docs/example_cursor_capture/)** - Reference JavaScript implementations

