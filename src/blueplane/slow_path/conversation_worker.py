"""
Builds and updates conversation structure from events.
Implements detailed reconstruction algorithms.
"""

from typing import Dict, Optional
from datetime import datetime

from ..storage.sqlite_traces import SQLiteTraceStorage
from ..storage.sqlite_conversations import ConversationStorage
from ..storage.redis_cdc import CDCWorkQueue


class ConversationWorker:
    """
    Builds conversation structure from events.
    Implements detailed reconstruction algorithms from layer2_conversation_reconstruction.md
    """

    def __init__(
        self,
        cdc_queue: CDCWorkQueue,
        worker_name: str = "conversation-worker-1",
        trace_storage: Optional[SQLiteTraceStorage] = None,
        conversation_storage: Optional[ConversationStorage] = None,
    ):
        """Initialize conversation worker."""
        self.cdc_queue = cdc_queue
        self.worker_name = worker_name
        self.trace_storage = trace_storage or SQLiteTraceStorage()
        self.conversation_storage = conversation_storage or ConversationStorage()

    async def process(self, cdc_event: Dict) -> None:
        """
        Process event to update conversation structure.
        
        1. Read full event from sqlite.get_by_sequence(sequence) and decompress
        2. Get or create conversation in SQLite (same database, conversations table)
        3. Update based on event_type:
           - 'user_prompt': Add turn with content_hash
           - 'assistant_response': Add turn with tokens and latency
           - 'tool_use': Update tool_sequence and add turn
           - 'code_change': Track change in code_changes table and update metrics
        
        Benefits of single SQLite database:
        - Can use transactions across raw_traces and conversations tables
        - No cross-database joins needed
        - Simpler connection management
        
        For platform-specific reconstruction:
        - See layer2_conversation_reconstruction.md#cursor-platform-reconstruction
        - See layer2_conversation_reconstruction.md#claude-code-platform-reconstruction
        """
        sequence = cdc_event.get("sequence")
        if not sequence:
            return
        
        # Read full event from SQLite
        event = self.trace_storage.get_by_sequence(sequence)
        if not event:
            return
        
        event_type = event.get("event_type", "")
        hook_type = event.get("hook_type", "")
        session_id = event.get("session_id", "")
        platform = event.get("platform", "")
        metadata = event.get("metadata", {})
        payload = event.get("payload", {})
        
        # Use hook_type if event_type is empty (Claude Code events use hook_type)
        effective_type = event_type or hook_type
        
        # Get or create conversation
        external_session_id = event.get("external_session_id") or session_id
        workspace_hash = metadata.get("workspace_hash")
        
        conversation_id = self.conversation_storage.get_or_create_conversation(
            session_id=session_id,
            external_session_id=external_session_id,
            platform=platform,
            workspace_hash=workspace_hash,
        )
        
        # Process based on event type (check both event_type and hook_type)
        if effective_type in ("user_prompt", "UserPromptSubmit", "BeforeSubmitPrompt"):
            await self._process_user_prompt(conversation_id, event)
        elif effective_type in ("assistant_response", "AfterAgentResponse"):
            await self._process_assistant_response(conversation_id, event)
        elif effective_type in ("tool_use", "PostToolUse", "AfterMCPExecution"):
            await self._process_tool_use(conversation_id, event)
        elif effective_type in ("code_change", "AfterFileEdit"):
            await self._process_code_change(conversation_id, event)
        # Handle PostToolUse specifically - it contains acceptance info
        elif effective_type == "PostToolUse":
            await self._process_tool_use(conversation_id, event)
            # Also track as code change if it's an Edit tool
            if payload.get("tool") == "Edit" and payload.get("accepted") is not None:
                await self._process_code_change(conversation_id, event)

    async def _process_user_prompt(self, conversation_id: str, event: Dict) -> None:
        """Process user prompt event."""
        payload = event.get("payload", {})
        metadata = event.get("metadata", {})
        
        # Hash content for privacy (simplified - in production, use proper hashing)
        content_hash = self._hash_content(payload.get("content", ""))
        
        # Add turn
        self.conversation_storage.add_turn(
            conversation_id=conversation_id,
            turn_type="user_prompt",
            content_hash=content_hash,
            metadata=metadata,
        )

    async def _process_assistant_response(self, conversation_id: str, event: Dict) -> None:
        """Process assistant response event."""
        payload = event.get("payload", {})
        metadata = event.get("metadata", {})
        
        tokens_used = payload.get("tokens_used") or metadata.get("tokens_used")
        latency_ms = payload.get("latency_ms") or event.get("duration_ms")
        
        # Hash content
        content_hash = self._hash_content(payload.get("content", ""))
        
        # Extract tools called
        tools_called = payload.get("tools_called", [])
        
        # Add turn
        self.conversation_storage.add_turn(
            conversation_id=conversation_id,
            turn_type="assistant_response",
            content_hash=content_hash,
            metadata=metadata,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            tools_called=tools_called,
        )

    async def _process_tool_use(self, conversation_id: str, event: Dict) -> None:
        """Process tool use event."""
        payload = event.get("payload", {})
        tool_name = payload.get("tool") or event.get("tool_name")
        
        tokens_used = payload.get("tokens_used")
        latency_ms = payload.get("duration_ms") or payload.get("latency_ms")
        
        # Add turn
        self.conversation_storage.add_turn(
            conversation_id=conversation_id,
            turn_type="tool_use",
            metadata={"tool": tool_name, **payload},
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

    async def _process_code_change(self, conversation_id: str, event: Dict) -> None:
        """Process code change event."""
        payload = event.get("payload", {})
        
        # For PostToolUse events, extract from payload
        file_extension = payload.get("file_extension")
        operation = payload.get("operation", "edit")
        lines_added = payload.get("lines_added", 0)
        lines_removed = payload.get("lines_removed", 0)
        accepted = payload.get("accepted")
        acceptance_delay_ms = payload.get("acceptance_delay_ms")
        
        # Only track if we have meaningful data
        if lines_added > 0 or lines_removed > 0 or accepted is not None:
            # Track code change
            self.conversation_storage.track_code_change(
                conversation_id=conversation_id,
                turn_id=None,  # Could link to turn if available
                file_extension=file_extension,
                operation=operation,
                lines_added=lines_added,
                lines_removed=lines_removed,
                accepted=accepted,
                acceptance_delay_ms=acceptance_delay_ms,
            )

    def _hash_content(self, content: str) -> str:
        """Hash content for privacy (simplified)."""
        import hashlib
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def close(self) -> None:
        """Close storage connections."""
        self.trace_storage.close()
        self.conversation_storage.close()

