#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Workspace History Server.

Lightweight server focused on:
- Reading the global Blueplane telemetry SQLite database.
- Running the Cursor session/markdown monitors.
- Writing per-workspace Markdown histories, with optional global output
  directory (`~/.blueplane/history/<workspace_hash>`).

This is intentionally separate from the main TelemetryServer so that
Markdown/aggregation paths can evolve independently of the ingest pipeline.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

import redis

from .database.sqlite_client import SQLiteClient
from .database.schema import create_schema
from .database.duckdb_adapter import DuckDBAdapter
from .cursor.session_monitor import SessionMonitor
from .cursor.markdown_monitor import CursorMarkdownMonitor
from ..capture.shared.config import Config

logger = logging.getLogger(__name__)


class WorkspaceHistoryServer:
    """
    Dedicated server for workspace history / Markdown generation.

    Responsibilities:
    - Ensure the global telemetry SQLite DB exists and is initialized.
    - Maintain a Redis connection for session monitoring.
    - Run SessionMonitor + CursorMarkdownMonitor in background threads.
    - Optionally initialize a DuckDB adapter for future aggregation.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        sqlite_db_path: Optional[str] = None,
        duckdb_path: Optional[str] = None,
    ):
        self.config = config or Config()
        self.sqlite_db_path = sqlite_db_path or str(Path.home() / ".blueplane" / "telemetry.db")
        self.duckdb_path = duckdb_path or str(Path.home() / ".blueplane" / "history.duckdb")

        self.sqlite_client: Optional[SQLiteClient] = None
        self.redis_client: Optional[redis.Redis] = None
        self.session_monitor: Optional[SessionMonitor] = None
        self.markdown_monitor: Optional[CursorMarkdownMonitor] = None
        self.duckdb_adapter: Optional[DuckDBAdapter] = None

        self.running = False
        self.monitor_threads: list[threading.Thread] = []

    # --- Initialization helpers -------------------------------------------------

    def _initialize_sqlite(self) -> None:
        """Initialize the global telemetry SQLite database."""
        logger.info(f"[WorkspaceHistory] Initializing SQLite database: {self.sqlite_db_path}")

        self.sqlite_client = SQLiteClient(self.sqlite_db_path)
        self.sqlite_client.initialize_database()
        create_schema(self.sqlite_client)

        logger.info("[WorkspaceHistory] SQLite database initialized")

    def _initialize_redis(self) -> None:
        """Initialize Redis connection used by SessionMonitor."""
        logger.info("[WorkspaceHistory] Initializing Redis connection")

        redis_config = self.config.redis
        self.redis_client = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            socket_timeout=redis_config.socket_timeout,
            socket_connect_timeout=redis_config.socket_connect_timeout,
            decode_responses=False,
        )

        try:
            self.redis_client.ping()
            logger.info("[WorkspaceHistory] Redis connection established")
        except redis.ConnectionError as e:
            raise RuntimeError(f"[WorkspaceHistory] Failed to connect to Redis: {e}") from e

    def _initialize_monitors(self) -> None:
        """Initialize session and markdown monitors."""
        if not self.redis_client:
            raise RuntimeError("[WorkspaceHistory] Redis client not initialized")

        logger.info("[WorkspaceHistory] Initializing SessionMonitor and CursorMarkdownMonitor")

        self.session_monitor = SessionMonitor(self.redis_client)

        global_output_dir = Path.home() / ".blueplane" / "history"
        self.markdown_monitor = CursorMarkdownMonitor(
            session_monitor=self.session_monitor,
            poll_interval=120.0,
            use_utc=True,
            global_output_dir=global_output_dir,
            prefer_global_output=True,
            duckdb_adapter=self.duckdb_adapter,
        )

        logger.info(
            "[WorkspaceHistory] Markdown monitor configured with global output dir: %s",
            global_output_dir,
        )

    def _initialize_duckdb_if_enabled(self) -> None:
        """
        Optionally initialize DuckDB adapter.

        Controlled by environment variable:
            BLUEPLANE_HISTORY_USE_DUCKDB=1

        If DuckDB is not installed or initialization fails, the server will
        continue running without a DuckDB sink.
        """
        use_duckdb = os.getenv("BLUEPLANE_HISTORY_USE_DUCKDB", "0") == "1"
        if not use_duckdb:
            logger.info("[WorkspaceHistory] DuckDB sink disabled (feature flag off)")
            return

        try:
            self.duckdb_adapter = DuckDBAdapter(Path(self.duckdb_path))
            logger.info("[WorkspaceHistory] DuckDB adapter initialized at %s", self.duckdb_path)
        except Exception as e:
            logger.warning("[WorkspaceHistory] Failed to initialize DuckDB adapter: %s", e)
            self.duckdb_adapter = None

    # --- Lifecycle --------------------------------------------------------------

    def start(self) -> None:
        """Start the workspace history server."""
        if self.running:
            logger.warning("[WorkspaceHistory] Server already running")
            return

        logger.info("Starting Workspace History Server...")

        try:
            self._initialize_sqlite()
            self._initialize_redis()
            self._initialize_monitors()
            self._initialize_duckdb_if_enabled()

            # Start monitors in background threads
            if self.session_monitor:

                def run_session_monitor() -> None:
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.session_monitor.start())

                session_thread = threading.Thread(target=run_session_monitor, daemon=True)
                session_thread.start()
                self.monitor_threads.append(session_thread)

            if self.markdown_monitor:

                def run_markdown_monitor() -> None:
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.markdown_monitor.start())
                    try:
                        loop.run_forever()
                    except KeyboardInterrupt:
                        pass
                    finally:
                        loop.run_until_complete(self.markdown_monitor.stop())
                        loop.close()

                markdown_thread = threading.Thread(target=run_markdown_monitor, daemon=True)
                markdown_thread.start()
                self.monitor_threads.append(markdown_thread)

            self.running = True
            logger.info("Workspace History Server started (Markdown + Session monitors active)")

            # Block main thread until interrupted
            self._wait_for_shutdown()

        except Exception as e:
            logger.error("[WorkspaceHistory] Failed to start server: %s", e)
            raise

    def _wait_for_shutdown(self) -> None:
        """Block the main thread until a termination signal is received."""
        try:
            while self.running:
                signal.pause()
        except (KeyboardInterrupt, AttributeError):
            # AttributeError: signal.pause may not be available on all platforms
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the server and all monitors."""
        if not self.running:
            return

        logger.info("Stopping Workspace History Server...")
        self.running = False

        # Stop async monitors
        if self.markdown_monitor:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.markdown_monitor.stop())

        if self.session_monitor:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.session_monitor.stop())

        # Close Redis
        if self.redis_client:
            self.redis_client.close()

        # Close DuckDB if used
        if self.duckdb_adapter:
            self.duckdb_adapter.close()

        logger.info("Workspace History Server stopped")

    def run(self) -> None:
        """Alias for start()."""
        self.start()


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Main entry point for the workspace history server."""
    setup_logging()

    server = WorkspaceHistoryServer()

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal for Workspace History Server")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Workspace History Server interrupted by user")
    except Exception as e:
        logger.error("Workspace History Server error: %s", e)
        sys.exit(1)
    finally:
        server.stop()


if __name__ == "__main__":
    main()


