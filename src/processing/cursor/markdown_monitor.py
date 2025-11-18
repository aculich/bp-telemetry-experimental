# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Markdown Monitor for Cursor Database.

Watches Cursor database files and writes markdown output when changes are detected.
Similar to the example extension's auto-save functionality.
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Dict, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

from .markdown_writer import CursorMarkdownWriter
from .workspace_mapper import WorkspaceMapper
from .session_monitor import SessionMonitor

logger = logging.getLogger(__name__)


class DatabaseFileHandler(FileSystemEventHandler):
    """File system event handler for database changes."""

    def __init__(self, monitor: "CursorMarkdownMonitor"):
        self.monitor = monitor
        self.debounce_seconds = 2.0  # Wait 2 seconds after last change
        self.pending_timers: Dict[str, threading.Timer] = {}
        self.lock = threading.Lock()

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        if not event.src_path.endswith("state.vscdb"):
            return

        db_path = Path(event.src_path)
        
        # Debounce: cancel existing timer and create new one
        db_path_str = str(db_path)
        
        with self.lock:
            if db_path_str in self.pending_timers:
                self.pending_timers[db_path_str].cancel()
            
            # Create new debounced timer
            timer = threading.Timer(
                self.debounce_seconds,
                self._debounced_write,
                args=(db_path,)
            )
            timer.start()
            self.pending_timers[db_path_str] = timer

    def _debounced_write(self, db_path: Path):
        """Write markdown after debounce period (runs in timer thread)."""
        # Schedule async task in the event loop
        if self.monitor.event_loop and self.monitor.event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.monitor.write_markdown_for_database(db_path),
                self.monitor.event_loop
            )
        else:
            logger.warning(f"Event loop not available, skipping markdown write for {db_path}")


class CursorMarkdownMonitor:
    """
    Monitor Cursor database files and write markdown on changes.
    
    Similar to the example extension:
    - Watches database files for changes
    - Queries all trace-relevant ItemTable keys
    - Writes markdown files to .history/
    """

    def __init__(
        self,
        session_monitor: SessionMonitor,
        workspace_mapper: Optional[WorkspaceMapper] = None,
        poll_interval: float = 120.0,  # 2 minutes safety net (like example)
        use_utc: bool = True,
        global_output_dir: Optional[Path] = None,
        prefer_global_output: bool = False,
    ):
        """
        Initialize markdown monitor.

        Args:
            session_monitor: Session monitor for active workspaces
            workspace_mapper: Workspace mapper (creates if not provided)
            poll_interval: Polling interval in seconds (safety net)
            use_utc: Use UTC timezone for timestamps
        """
        self.session_monitor = session_monitor
        self.workspace_mapper = workspace_mapper or WorkspaceMapper(session_monitor)
        self.poll_interval = poll_interval
        self.use_utc = use_utc

        # Output configuration
        self.global_output_dir: Optional[Path] = global_output_dir
        self.prefer_global_output = prefer_global_output

        # Track which workspaces we've already logged mappings for
        self._logged_mappings: set[str] = set()
        
        # Track markdown writers per workspace
        self.writers: Dict[str, CursorMarkdownWriter] = {}
        
        # File watcher
        self.observer: Optional[Observer] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False

    async def start(self):
        """Start monitoring database files."""
        if self.running:
            logger.warning("Markdown monitor already running")
            return

        self.running = True
        self.event_loop = asyncio.get_event_loop()
        
        # Start file watcher (if available)
        if WATCHDOG_AVAILABLE:
            await self._start_file_watcher()
        else:
            logger.warning("watchdog not available, using polling only")
        
        # Start polling loop (safety net)
        asyncio.create_task(self._polling_loop())
        
        logger.info("Markdown monitor started")

    async def stop(self):
        """Stop monitoring."""
        self.running = False
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.observer = None
        
        logger.info("Markdown monitor stopped")

    async def _start_file_watcher(self):
        """Start file system watcher for database files."""
        if not WATCHDOG_AVAILABLE:
            return
        
        from .platform import get_cursor_database_paths
        
        # Get all database base paths
        base_paths = get_cursor_database_paths()
        
        if not base_paths:
            logger.warning("No Cursor database paths found")
            return
        
        # Create observer in a thread (watchdog requires thread)
        def start_observer():
            self.observer = Observer()
            handler = DatabaseFileHandler(self)
            
            # Watch each base path
            for base_path in base_paths:
                if base_path.exists():
                    self.observer.schedule(handler, str(base_path), recursive=True)
                    logger.info(f"Watching database directory: {base_path}")
            
            # Start observer
            self.observer.start()
        
        # Run observer in background thread
        observer_thread = threading.Thread(target=start_observer, daemon=True)
        observer_thread.start()

    async def _polling_loop(self):
        """Polling loop as safety net (every 2 minutes)."""
        while self.running:
            try:
                # Get active workspaces
                active_workspaces = self.session_monitor.get_active_workspaces()
                
                # Write markdown for each active workspace
                for workspace_hash, session_info in active_workspaces.items():
                    workspace_path = session_info.get("workspace_path")
                    if not workspace_path:
                        continue
                    
                    # Find database
                    db_path = await self.workspace_mapper.find_database(
                        workspace_hash,
                        workspace_path
                    )
                    
                    if db_path and db_path.exists():
                        await self.write_markdown_for_database(db_path, workspace_hash, workspace_path)
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(30)

    async def write_markdown_for_database(
        self,
        db_path: Path,
        workspace_hash: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ):
        """
        Write markdown for a database file.

        Args:
            db_path: Path to state.vscdb file
            workspace_hash: Workspace hash (looks up if not provided)
            workspace_path: Workspace path (looks up if not provided)
        """
        try:
            # Look up workspace info if not provided
            if not workspace_hash or not workspace_path:
                active_workspaces = self.session_monitor.get_active_workspaces()
                
                # Try to find matching workspace
                for hash_val, session_info in active_workspaces.items():
                    session_path = session_info.get("workspace_path")
                    found_db = await self.workspace_mapper.find_database(hash_val, session_path)
                    
                    if found_db == db_path:
                        workspace_hash = hash_val
                        workspace_path = session_path
                        break
                
                if not workspace_hash:
                    # Use database directory name as fallback
                    workspace_hash = db_path.parent.name
                    workspace_path = str(db_path.parent)
            
            # Get or create writer for workspace
            if workspace_hash not in self.writers:
                workspace_path_obj = Path(workspace_path) if workspace_path else db_path.parent.parent
                output_dir = self._get_output_dir(workspace_hash, workspace_path_obj)
                self.writers[workspace_hash] = CursorMarkdownWriter(
                    workspace_path_obj,
                    output_dir=output_dir,
                    use_utc=self.use_utc
                )

            writer = self.writers[workspace_hash]

            # Log the workspace/session/output mapping once per workspace for observability
            if workspace_hash not in self._logged_mappings:
                active_workspaces = self.session_monitor.get_active_workspaces()
                session_info = active_workspaces.get(workspace_hash, {})
                session_id = session_info.get("session_id")
                logger.info(
                    "Markdown history mapping: workspace_hash=%s, session_id=%s, workspace_path=%s, output_dir=%s",
                    workspace_hash,
                    session_id,
                    workspace_path,
                    writer.output_dir,
                )
                self._logged_mappings.add(workspace_hash)

            # Write markdown
            output_path = await writer.write_from_database(db_path, workspace_hash)
            
            if output_path:
                logger.info(f"Wrote markdown: {output_path}")
            else:
                logger.debug(f"No markdown written for {db_path} (no data)")

        except Exception as e:
            logger.error(f"Error writing markdown for {db_path}: {e}")

    def _get_output_dir(self, workspace_hash: str, workspace_path_obj: Path) -> Path:
        """
        Determine the output directory for a workspace's markdown files.

        If a global output directory is configured and preferred, use:
            <global_output_dir>/<workspace_hash>

        Otherwise, default to:
            <workspace_path>/.history
        """
        if self.global_output_dir and self.prefer_global_output:
            return self.global_output_dir / workspace_hash

        # Default: workspace-local .history directory
        return workspace_path_obj / ".history"

