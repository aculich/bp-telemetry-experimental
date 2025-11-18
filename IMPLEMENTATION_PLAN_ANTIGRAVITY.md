# Implementation Plan: Antigravity IDE Instrumentation

## 1. Overview
This plan details the steps to instrument Google's new **Antigravity IDE** using the Blueplane Telemetry Core system. Antigravity is an Electron-based IDE derived from VS Code, similar to Cursor, which allows us to leverage existing VS Code instrumentation strategies.

## 2. Findings
- **Architecture**: Electron app, VS Code derivative.
- **Data Directory**: `~/Library/Application Support/Antigravity`
  - Global Storage: `User/globalStorage/state.vscdb`
  - Workspace Storage: `User/workspaceStorage/{hash}/state.vscdb`
- **Extensions Directory**: `~/.antigravity/extensions`
- **CLI Tool**: `Antigravity.app/Contents/Resources/app/bin/antigravity`
- **Hooks**: No native hook system (like `~/.cursor/hooks`) detected.

## 3. Instrumentation Strategy

### Layer 1: Capture
Since Antigravity lacks the custom Python hooks found in Cursor, we will rely on:
1.  **Database Monitoring**:
    - We will adapt the existing `DatabaseMonitor` to watch Antigravity's SQLite databases.
    - This will capture conversation history, metadata, and other persisted state.
    - **Path**: `~/Library/Application Support/Antigravity/User/...`
2.  **VS Code Extension**:
    - We will install the existing `bp-telemetry` VS Code extension into Antigravity.
    - This will provide session management (generating session IDs per workspace) and access to `workspaceState`.
    - **Installation**: via `antigravity --install-extension` CLI.

### Layer 2: Processing
- The existing Redis -> SQLite pipeline will be reused.
- We will add `antigravity` as a supported platform in the event schema and processing logic.

## 4. Implementation Steps

### Step 1: Create Antigravity Capture Module
- [x] Create `src/capture/antigravity/`
- [x] Implement `config.py` with Antigravity-specific paths.
- [x] Implement `db_monitor.py` (subclass/adapt from Cursor monitor).

### Step 2: Update Processing Server
- [x] Modify `src/processing/server.py` (or create a wrapper) to initialize the Antigravity monitor.
- [x] Ensure the server can run both Cursor and Antigravity monitors concurrently or selectively.

### Step 3: Extension Installation Script
- [x] Create `scripts/install_antigravity.py`.
- [x] This script will:
    1.  Build the extension (if not built).
    2.  Locate the `antigravity` CLI binary.
    3.  Run `antigravity --install-extension <vsix>`.

### Step 4: Verification
- [x] Verify that the extension loads in Antigravity.
- [x] Verify that the Python server detects Antigravity databases.
- [ ] Verify that events flow from DB -> Redis -> SQLite (telemetry.db).

## 5. Execution
We will start by creating the directory structure and the configuration module.

## 6. Running the System

A `Makefile` and helper scripts have been provided to ensure the correct virtual environment is used.

### Setup
```bash
make setup
```

### Running the Server
```bash
make run
# OR
./scripts/start_server.sh
```

### Verifying Installation
```bash
make verify
```

### Installing Extension
```bash
make install-extension
```
