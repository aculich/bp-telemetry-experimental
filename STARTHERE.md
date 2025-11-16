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

**Database Location**:
- **macOS**: `~/Library/Application Support/Cursor/User/workspaceStorage/{hash}/state.vscdb`
- **Linux**: `~/.config/Cursor/User/workspaceStorage/{hash}/state.vscdb`
- **Windows**: `~/AppData/Roaming/Cursor/User/workspaceStorage/{hash}/state.vscdb`

**Critical Table**: `ItemTable`

**Key Keys**:
- `composer.composerData` - Composer session metadata
- `aiService.generations` - AI generation history (JSON array)
- `aiService.prompts` - Prompt history (JSON array)

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

**What Database CAN Capture**:
- ✅ Generation metadata (UUIDs, timestamps, types)
- ✅ Composer IDs and session metadata
- ✅ Prompt history
- ✅ Generation history

**What Database CANNOT Capture**:
- ❌ Model information (not in ItemTable)
- ❌ Token usage (not stored)
- ❌ Request duration (not stored)
- ❌ Full conversation content (only in workspace storage)

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
| **Full Conversations** | ⚠️ Partial (current event) | ✅ `nativeComposers` | ❌ | ✅ **AVAILABLE** |
| **File Edits** | ✅ `beforeFileEdit`<br>`afterFileEdit` | ❌ | ❌ | ✅ **AVAILABLE** |
| **Shell Commands** | ✅ `beforeShellExecution`<br>`afterShellExecution` | ❌ | ❌ | ✅ **AVAILABLE** |
| **User Prompts** | ✅ `beforeSubmitPrompt` | ✅ In conversations | ❌ | ✅ **AVAILABLE** |
| **Agent Responses** | ✅ `afterAgentResponse` | ✅ In conversations | ❌ | ✅ **AVAILABLE** |

---

### Model Information Extraction

**Source**: Workspace Storage (`composerData:{composerId}`)

**Structure**:
```typescript
interface NativeComposer {
  modelConfig?: {
    modelName?: string;  // Composer-level (most recent model)
  };
  conversation: Array<{
    modelInfo?: {
      modelName?: string;  // Message-level (per message)
    };
  }>;
}
```

**Extraction Logic**:
```typescript
function extractModelName(composer: NativeComposer, message?: any): string {
  // Try message-level first (if available)
  if (message?.modelInfo?.modelName) {
    return message.modelInfo.modelName;
  }
  
  // Fall back to composer-level (most recent model)
  if (composer.modelConfig?.modelName) {
    return composer.modelConfig.modelName;
  }
  
  return "";  // Not available
}
```

**Limitations**:
- Only **most recent model** per composer is stored at composer level
- Individual messages may have `modelInfo.modelName`, but not consistently populated
- Historical model usage is limited (see SpecStory changelog v0.20.0)

---

### Tool Usage Extraction

**Source**: Workspace Storage

**Structure**:
- **Version < 3**: `capabilities[type=15].data.bubbleDataMap[bubbleId]`
- **Version >= 3**: `message.toolFormerData` (direct)

**Extraction Logic**:
```typescript
function extractToolUsage(composer: NativeComposer): any[] {
  const tools: any[] = [];
  
  if (!composer.conversation || !composer.capabilities) {
    return tools;
  }
  
  // Find capability type 15 (tool usage)
  const toolCapability = composer.capabilities.find(c => c.type === 15);
  if (!toolCapability) {
    return tools;
  }
  
  // Process each conversation message
  for (const message of composer.conversation) {
    if (message.capabilityType === 15) {
      let toolData: any = null;
      
      // Version >= 3: use toolFormerData directly
      if (composer._v && composer._v >= 3 && message.toolFormerData) {
        toolData = message.toolFormerData;
      }
      // Version < 3: extract from bubbleDataMap
      else if (toolCapability.data?.bubbleDataMap) {
        try {
          const bubbleDataMap = JSON.parse(toolCapability.data.bubbleDataMap);
          toolData = bubbleDataMap[message.bubbleId];
        } catch (error) {
          console.error("Error parsing bubbleDataMap:", error);
        }
      }
      
      if (toolData) {
        tools.push({
          bubble_id: message.bubbleId,
          tool_data: toolData,
          version: composer._v,
        });
      }
    }
  }
  
  return tools;
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

# Check Redis
redis-cli ping
redis-cli XREAD COUNT 10 STREAMS telemetry:events 0
```

### Key File Paths

- **Extension**: `src/capture/cursor/extension/`
- **Hooks**: `src/capture/cursor/hooks/`
- **Database**: `~/Library/Application Support/Cursor/User/workspaceStorage/{hash}/state.vscdb`
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

