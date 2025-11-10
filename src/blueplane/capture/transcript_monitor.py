"""
Claude Code transcript monitor.
Watches JSONL transcript files and extracts conversation events.
"""

import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .queue_writer import MessageQueueWriter

logger = logging.getLogger(__name__)


class TranscriptMonitor(FileSystemEventHandler):
    """
    Monitors Claude Code transcript JSONL files for new events.
    
    Watches for new lines in transcript files and extracts:
    - Conversation turns
    - Model usage
    - Token counts
    - Tool calls
    """

    def __init__(self, transcript_path: Path, session_id: str):
        """
        Initialize transcript monitor.
        
        Args:
            transcript_path: Path to JSONL transcript file
            session_id: Session ID for this transcript
        """
        self.transcript_path = Path(transcript_path)
        self.session_id = session_id
        self.writer = MessageQueueWriter()
        
        # Track processed line hashes to avoid duplicates
        self.processed_lines: Set[str] = set()
        
        # Process existing lines on startup
        if self.transcript_path.exists():
            self._process_existing_lines()

    def _hash_line(self, line: str) -> str:
        """Generate hash for a line to track if we've seen it."""
        return hashlib.md5(line.encode()).hexdigest()

    def _process_existing_lines(self):
        """Process all existing lines in transcript file."""
        try:
            with open(self.transcript_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        line_hash = self._hash_line(line)
                        self.processed_lines.add(line_hash)
        except Exception as e:
            logger.debug(f"Error reading existing transcript lines: {e}")

    def _process_line(self, line: str):
        """
        Process a single JSONL line and extract events.
        
        Args:
            line: JSON line from transcript file
        """
        try:
            line = line.strip()
            if not line:
                return
            
            # Check if we've already processed this line
            line_hash = self._hash_line(line)
            if line_hash in self.processed_lines:
                return
            
            self.processed_lines.add(line_hash)
            
            # Parse JSON line
            data = json.loads(line)
            
            # Extract event type from transcript structure
            # Claude Code transcripts have structure like:
            # {"role": "user", "content": "...", "timestamp": "..."}
            # or {"role": "assistant", "content": "...", "tool_calls": [...]}
            
            role = data.get("role")
            if role == "user":
                self._emit_user_message(data)
            elif role == "assistant":
                self._emit_assistant_message(data)
            
            # Extract tool calls if present
            tool_calls = data.get("tool_calls") or data.get("toolCalls") or []
            for tool_call in tool_calls:
                self._emit_tool_call(tool_call, data)
            
        except json.JSONDecodeError as e:
            logger.debug(f"Invalid JSON in transcript line: {e}")
        except Exception as e:
            logger.debug(f"Error processing transcript line: {e}", exc_info=True)

    def _emit_user_message(self, data: Dict):
        """Emit user message event."""
        event = {
            "hook_type": "TranscriptUserMessage",
            "timestamp": data.get("timestamp") or data.get("created_at"),
            "payload": {
                "content_length": len(data.get("content", "")),
                "message_id": data.get("id"),
            },
        }
        self.writer.enqueue(
            event=event,
            platform="claude_code",
            session_id=self.session_id,
            hook_type="TranscriptUserMessage",
        )

    def _emit_assistant_message(self, data: Dict):
        """Emit assistant message event."""
        event = {
            "hook_type": "TranscriptAssistantMessage",
            "timestamp": data.get("timestamp") or data.get("created_at"),
            "payload": {
                "content_length": len(data.get("content", "")),
                "message_id": data.get("id"),
                "model": data.get("model"),
                "tokens_used": data.get("usage", {}).get("total_tokens") or data.get("tokens"),
            },
        }
        self.writer.enqueue(
            event=event,
            platform="claude_code",
            session_id=self.session_id,
            hook_type="TranscriptAssistantMessage",
        )

    def _emit_tool_call(self, tool_call: Dict, parent_data: Dict):
        """Emit tool call event from transcript."""
        event = {
            "hook_type": "TranscriptToolCall",
            "timestamp": parent_data.get("timestamp") or parent_data.get("created_at"),
            "payload": {
                "tool_name": tool_call.get("name") or tool_call.get("function", {}).get("name"),
                "tool_id": tool_call.get("id"),
                "message_id": parent_data.get("id"),
            },
        }
        self.writer.enqueue(
            event=event,
            platform="claude_code",
            session_id=self.session_id,
            hook_type="TranscriptToolCall",
        )

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        if Path(event.src_path) != self.transcript_path:
            return
        
        # Read new lines
        try:
            with open(self.transcript_path, 'r') as f:
                lines = f.readlines()
                # Process only new lines (after what we've already seen)
                for line in lines:
                    self._process_line(line)
        except Exception as e:
            logger.debug(f"Error processing modified transcript file: {e}")


def start_transcript_monitor(transcript_path: str, session_id: str) -> Observer:
    """
    Start monitoring a transcript file.
    
    Args:
        transcript_path: Path to JSONL transcript file
        session_id: Session ID for this transcript
    
    Returns:
        Observer instance (call observer.stop() to stop monitoring)
    """
    monitor = TranscriptMonitor(Path(transcript_path), session_id)
    observer = Observer()
    observer.schedule(monitor, path=str(Path(transcript_path).parent), recursive=False)
    observer.start()
    return observer

