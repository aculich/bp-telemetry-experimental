"""
Cursor database monitor.
Watches Cursor's SQLite database for trace events.
"""

import sqlite3
import logging
import hashlib
from pathlib import Path
from typing import Dict, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .queue_writer import MessageQueueWriter

logger = logging.getLogger(__name__)


class CursorDatabaseMonitor(FileSystemEventHandler):
    """
    Monitors Cursor's SQLite database for trace events.
    
    Watches for changes in:
    - aiService.prompts
    - aiService.generations
    - composer.composerData
    """

    def __init__(self, db_path: Path, session_id: str):
        """
        Initialize database monitor.
        
        Args:
            db_path: Path to Cursor's state.vscdb file
            session_id: Session ID for this monitoring session
        """
        self.db_path = Path(db_path)
        self.session_id = session_id
        self.writer = MessageQueueWriter()
        
        # Track processed data_version values
        self.last_prompt_version: int = 0
        self.last_generation_version: int = 0
        self.last_composer_version: int = 0
        
        # Process existing data on startup
        if self.db_path.exists():
            self._process_existing_data()

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get read-only SQLite connection."""
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            return conn
        except Exception as e:
            logger.debug(f"Error connecting to database: {e}")
            return None

    def _process_existing_data(self):
        """Process existing data in database."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Get max data_version for each table
            try:
                cursor.execute("SELECT MAX(data_version) FROM aiService.prompts")
                result = cursor.fetchone()
                if result and result[0]:
                    self.last_prompt_version = result[0]
            except sqlite3.OperationalError:
                pass  # Table might not exist
            
            try:
                cursor.execute("SELECT MAX(data_version) FROM aiService.generations")
                result = cursor.fetchone()
                if result and result[0]:
                    self.last_generation_version = result[0]
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("SELECT MAX(data_version) FROM composer.composerData")
                result = cursor.fetchone()
                if result and result[0]:
                    self.last_composer_version = result[0]
            except sqlite3.OperationalError:
                pass
                
        except Exception as e:
            logger.debug(f"Error processing existing data: {e}")
        finally:
            conn.close()

    def _capture_changes(self):
        """Capture new changes from database."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Check for new prompts
            try:
                cursor.execute(
                    "SELECT key, value, data_version FROM aiService.prompts WHERE data_version > ?",
                    (self.last_prompt_version,)
                )
                for row in cursor.fetchall():
                    self._process_prompt(row[0], row[1], row[2])
                    self.last_prompt_version = max(self.last_prompt_version, row[2])
            except sqlite3.OperationalError:
                pass  # Table might not exist
            
            # Check for new generations
            try:
                cursor.execute(
                    "SELECT key, value, data_version FROM aiService.generations WHERE data_version > ?",
                    (self.last_generation_version,)
                )
                for row in cursor.fetchall():
                    self._process_generation(row[0], row[1], row[2])
                    self.last_generation_version = max(self.last_generation_version, row[2])
            except sqlite3.OperationalError:
                pass
            
            # Check for new composer data
            try:
                cursor.execute(
                    "SELECT key, value, data_version FROM composer.composerData WHERE data_version > ?",
                    (self.last_composer_version,)
                )
                for row in cursor.fetchall():
                    self._process_composer_data(row[0], row[1], row[2])
                    self.last_composer_version = max(self.last_composer_version, row[2])
            except sqlite3.OperationalError:
                pass
                
        except Exception as e:
            logger.debug(f"Error capturing database changes: {e}")
        finally:
            conn.close()

    def _process_prompt(self, key: str, value: str, data_version: int):
        """Process a prompt entry."""
        try:
            import json
            prompt_data = json.loads(value) if isinstance(value, str) else value
            
            event = {
                "hook_type": "DatabasePrompt",
                "payload": {
                    "prompt_id": key,
                    "data_version": data_version,
                    "prompt_length": len(prompt_data.get("text", "")) if isinstance(prompt_data, dict) else 0,
                },
            }
            
            self.writer.enqueue(
                event=event,
                platform="cursor",
                session_id=self.session_id,
                hook_type="DatabasePrompt",
            )
        except Exception as e:
            logger.debug(f"Error processing prompt: {e}")

    def _process_generation(self, key: str, value: str, data_version: int):
        """Process a generation entry."""
        try:
            import json
            gen_data = json.loads(value) if isinstance(value, str) else value
            
            event = {
                "hook_type": "DatabaseGeneration",
                "payload": {
                    "generation_id": key,
                    "data_version": data_version,
                    "model": gen_data.get("model") if isinstance(gen_data, dict) else None,
                },
            }
            
            self.writer.enqueue(
                event=event,
                platform="cursor",
                session_id=self.session_id,
                hook_type="DatabaseGeneration",
            )
        except Exception as e:
            logger.debug(f"Error processing generation: {e}")

    def _process_composer_data(self, key: str, value: str, data_version: int):
        """Process composer data entry."""
        try:
            import json
            composer_data = json.loads(value) if isinstance(value, str) else value
            
            event = {
                "hook_type": "DatabaseComposerData",
                "payload": {
                    "composer_id": key,
                    "data_version": data_version,
                },
            }
            
            self.writer.enqueue(
                event=event,
                platform="cursor",
                session_id=self.session_id,
                hook_type="DatabaseComposerData",
            )
        except Exception as e:
            logger.debug(f"Error processing composer data: {e}")

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        if Path(event.src_path) != self.db_path:
            return
        
        # Database file was modified, check for changes
        self._capture_changes()


def start_database_monitor(db_path: str, session_id: str) -> Observer:
    """
    Start monitoring Cursor's database.
    
    Args:
        db_path: Path to Cursor's state.vscdb file
        session_id: Session ID for this monitoring session
    
    Returns:
        Observer instance (call observer.stop() to stop monitoring)
    """
    monitor = CursorDatabaseMonitor(Path(db_path), session_id)
    observer = Observer()
    observer.schedule(monitor, path=str(Path(db_path).parent), recursive=False)
    observer.start()
    return observer

