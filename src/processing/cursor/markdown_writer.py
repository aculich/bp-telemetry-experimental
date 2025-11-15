# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Markdown Writer for Cursor Database Traces.

Generates markdown files from Cursor database data, similar to the example extension.
Queries all relevant ItemTable keys and writes formatted markdown output to .history/ directory.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiosqlite

logger = logging.getLogger(__name__)

# Markdown version
MARKDOWN_VERSION = "2.0.0"

# Trace-relevant keys from ItemTable (from CURSOR_DISK_KV_AUDIT.md)
TRACE_RELEVANT_KEYS = [
    "aiService.generations",
    "aiService.prompts",
    "composer.composerData",
    "workbench.backgroundComposer.workspacePersistentData",
    "workbench.agentMode.exitInfo",
    "interactive.sessions",
    "history.entries",
    "cursorAuth/workspaceOpenedDate",
]


class CursorMarkdownWriter:
    """
    Write Cursor database traces to markdown files.
    
    Similar to the example extension, this:
    1. Queries ItemTable for all trace-relevant keys
    2. Normalizes composer/conversation data
    3. Generates markdown output
    4. Writes to .history/ directory
    """

    def __init__(
        self,
        workspace_path: Path,
        output_dir: Optional[Path] = None,
        use_utc: bool = True,
    ):
        """
        Initialize markdown writer.

        Args:
            workspace_path: Path to workspace root
            output_dir: Output directory (defaults to workspace/.history)
            use_utc: Use UTC timezone for timestamps
        """
        self.workspace_path = Path(workspace_path)
        self.use_utc = use_utc
        
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.workspace_path / ".history"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Markdown writer initialized: {self.output_dir}")

    async def write_from_database(
        self,
        db_path: Path,
        workspace_hash: str,
    ) -> Optional[Path]:
        """
        Query database and write markdown file.

        Args:
            db_path: Path to state.vscdb file
            workspace_hash: Workspace hash identifier

        Returns:
            Path to written markdown file, or None if no data
        """
        try:
            # Load all trace-relevant data from ItemTable
            data = await self._load_database_data(db_path)
            
            if not data:
                logger.debug(f"No data found in database {db_path}")
                return None

            # Generate markdown from data
            markdown = await self._generate_markdown(data, workspace_hash)
            
            if not markdown:
                logger.debug(f"No markdown generated for {workspace_hash}")
                return None

            # Write to file
            output_path = await self._write_markdown_file(markdown, workspace_hash)
            
            logger.info(f"Wrote markdown to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error writing markdown from database: {e}")
            return None

    async def _load_database_data(self, db_path: Path) -> Dict[str, Any]:
        """
        Load all trace-relevant data from ItemTable.

        Args:
            db_path: Path to state.vscdb

        Returns:
            Dictionary mapping keys to parsed JSON values
        """
        data = {}
        
        try:
            async with aiosqlite.connect(str(db_path), timeout=2.0) as conn:
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA read_uncommitted=1")
                
                # Query all trace-relevant keys
                placeholders = ",".join("?" * len(TRACE_RELEVANT_KEYS))
                cursor = await conn.execute(
                    f"SELECT key, value FROM ItemTable WHERE key IN ({placeholders})",
                    TRACE_RELEVANT_KEYS
                )
                
                rows = await cursor.fetchall()
                
                for key, value in rows:
                    if not value:
                        continue
                    
                    try:
                        # Parse JSON from BLOB/text
                        value_str = value
                        if isinstance(value_str, bytes):
                            value_str = value_str.decode('utf-8')
                        
                        parsed_value = json.loads(value_str)
                        data[key] = parsed_value
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON for key {key}: {e}")
                        # Store as string if not JSON
                        data[key] = value_str if isinstance(value_str, str) else str(value)
                    except Exception as e:
                        logger.warning(f"Error processing key {key}: {e}")

        except Exception as e:
            logger.error(f"Error loading database data: {e}")
        
        return data

    async def _generate_markdown(
        self,
        data: Dict[str, Any],
        workspace_hash: str,
    ) -> str:
        """
        Generate markdown from database data.

        Args:
            data: Dictionary of key-value pairs from ItemTable
            workspace_hash: Workspace hash identifier

        Returns:
            Markdown string
        """
        markdown_parts = []
        
        # Header comment
        markdown_parts.append(f"<!-- Generated by Blueplane Telemetry, Markdown v{MARKDOWN_VERSION} -->\n")
        markdown_parts.append(f"<!-- Workspace: {workspace_hash} -->\n")
        markdown_parts.append(f"<!-- Generated: {self._format_timestamp(datetime.now(), self.use_utc)} -->\n\n")
        
        # Process composer data (main conversation source)
        composer_data = data.get("composer.composerData")
        if composer_data:
            composer_markdown = self._format_composer_data(composer_data)
            if composer_markdown:
                markdown_parts.append(composer_markdown)
                markdown_parts.append("\n\n")
        
        # Process AI service generations
        generations = data.get("aiService.generations", [])
        if generations:
            generations_markdown = self._format_generations(generations)
            if generations_markdown:
                markdown_parts.append("## AI Service Generations\n\n")
                markdown_parts.append(generations_markdown)
                markdown_parts.append("\n\n")
        
        # Process prompts
        prompts = data.get("aiService.prompts", [])
        if prompts:
            prompts_markdown = self._format_prompts(prompts)
            if prompts_markdown:
                markdown_parts.append("## AI Service Prompts\n\n")
                markdown_parts.append(prompts_markdown)
                markdown_parts.append("\n\n")
        
        # Process background composer
        bg_composer = data.get("workbench.backgroundComposer.workspacePersistentData")
        if bg_composer:
            bg_markdown = self._format_background_composer(bg_composer)
            if bg_markdown:
                markdown_parts.append("## Background Composer\n\n")
                markdown_parts.append(bg_markdown)
                markdown_parts.append("\n\n")
        
        # Process agent mode info
        agent_mode = data.get("workbench.agentMode.exitInfo")
        if agent_mode:
            agent_markdown = self._format_agent_mode(agent_mode)
            if agent_markdown:
                markdown_parts.append("## Agent Mode\n\n")
                markdown_parts.append(agent_markdown)
                markdown_parts.append("\n\n")
        
        # Process history entries
        history = data.get("history.entries", [])
        if history:
            history_markdown = self._format_history(history)
            if history_markdown:
                markdown_parts.append("## File History\n\n")
                markdown_parts.append(history_markdown)
                markdown_parts.append("\n\n")
        
        return "".join(markdown_parts)

    def _format_composer_data(self, composer_data: Dict[str, Any]) -> str:
        """
        Format composer.composerData to markdown.
        
        Note: composer.composerData contains metadata about composers.
        The actual conversation data is stored elsewhere and would need
        to be loaded separately (similar to how the example extension does it).
        """
        parts = []
        
        all_composers = composer_data.get("allComposers", [])
        if not all_composers:
            return ""
        
        parts.append("# Composer Sessions\n\n")
        
        # Sort composers by creation time
        sorted_composers = sorted(
            all_composers,
            key=lambda c: c.get("createdAt", 0)
        )
        
        for composer in sorted_composers:
            composer_id = composer.get("composerId", "unknown")
            created_at = composer.get("createdAt", 0)
            unified_mode = composer.get("unifiedMode", "unknown")
            force_mode = composer.get("forceMode")
            
            # Format timestamp
            if created_at:
                timestamp_str = self._format_timestamp_ms(created_at, self.use_utc)
            else:
                timestamp_str = "Unknown"
            
            parts.append(f"## Composer: {composer_id}\n\n")
            parts.append(f"**Created:** {timestamp_str}\n")
            parts.append(f"**Mode:** {unified_mode}")
            if force_mode:
                parts.append(f" (force: {force_mode})")
            parts.append("\n")
            
            # Add stats
            lines_added = composer.get("totalLinesAdded", 0)
            lines_removed = composer.get("totalLinesRemoved", 0)
            if lines_added or lines_removed:
                parts.append(f"**Code Changes:** +{lines_added} / -{lines_removed} lines\n")
            
            is_archived = composer.get("isArchived", False)
            if is_archived:
                parts.append("**Status:** Archived\n")
            
            has_unread = composer.get("hasUnreadMessages", False)
            if has_unread:
                parts.append("**Has Unread Messages:** Yes\n")
            
            parts.append("\n---\n\n")
        
        # Add selected/focused composer info
        selected_ids = composer_data.get("selectedComposerIds", [])
        if selected_ids:
            parts.append(f"**Selected Composers:** {', '.join(selected_ids)}\n\n")
        
        focused_ids = composer_data.get("lastFocusedComposerIds", [])
        if focused_ids:
            parts.append(f"**Last Focused:** {', '.join(focused_ids)}\n\n")
        
        return "".join(parts)

    def _format_generations(self, generations: List[Dict[str, Any]]) -> str:
        """Format aiService.generations to markdown."""
        if not isinstance(generations, list):
            return ""
        
        parts = []
        
        # Sort by timestamp
        sorted_gens = sorted(
            [g for g in generations if isinstance(g, dict)],
            key=lambda g: g.get("unixMs", 0)
        )
        
        for gen in sorted_gens:
            generation_uuid = gen.get("generationUUID", "unknown")
            unix_ms = gen.get("unixMs", 0)
            gen_type = gen.get("type", "unknown")
            description = gen.get("textDescription", "")
            
            timestamp_str = self._format_timestamp_ms(unix_ms, self.use_utc) if unix_ms else "Unknown"
            
            parts.append(f"### Generation: {generation_uuid}\n\n")
            parts.append(f"**Timestamp:** {timestamp_str}\n")
            parts.append(f"**Type:** {gen_type}\n")
            
            if description:
                parts.append(f"**Description:** {description}\n")
            
            parts.append("\n---\n\n")
        
        return "".join(parts)

    def _format_prompts(self, prompts: List[Dict[str, Any]]) -> str:
        """Format aiService.prompts to markdown."""
        if not isinstance(prompts, list):
            return ""
        
        parts = []
        
        for i, prompt in enumerate(prompts):
            if not isinstance(prompt, dict):
                continue
            
            text = prompt.get("text", "")
            command_type = prompt.get("commandType")
            
            parts.append(f"### Prompt {i + 1}\n\n")
            
            if command_type is not None:
                parts.append(f"**Command Type:** {command_type}\n")
            
            if text:
                parts.append(f"**Text:**\n\n```\n{text}\n```\n")
            
            parts.append("\n---\n\n")
        
        return "".join(parts)

    def _format_background_composer(self, bg_composer: Dict[str, Any]) -> str:
        """Format background composer data to markdown."""
        parts = []
        
        setup_step = bg_composer.get("setupStep")
        if setup_step is not None:
            parts.append(f"**Setup Step:** {setup_step}\n")
        
        terminals = bg_composer.get("terminals", [])
        if terminals:
            parts.append(f"**Terminals:** {len(terminals)}\n")
        
        ran_commands = bg_composer.get("ranTerminalCommands", [])
        if ran_commands:
            parts.append("**Terminal Commands:**\n\n")
            for cmd in ran_commands:
                parts.append(f"- {cmd}\n")
            parts.append("\n")
        
        git_state = bg_composer.get("gitState")
        if git_state:
            parts.append(f"**Git State:** {json.dumps(git_state, indent=2)}\n")
        
        return "".join(parts)

    def _format_agent_mode(self, agent_mode: Dict[str, Any]) -> str:
        """Format agent mode exit info to markdown."""
        parts = []
        
        was_visible = agent_mode.get("wasVisible", {})
        if was_visible:
            parts.append("**Visibility on Exit:**\n\n")
            for panel, visible in was_visible.items():
                parts.append(f"- {panel}: {'visible' if visible else 'hidden'}\n")
            parts.append("\n")
        
        return "".join(parts)

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """Format history.entries to markdown."""
        if not isinstance(history, list):
            return ""
        
        parts = []
        
        for entry in history:
            if not isinstance(entry, dict):
                continue
            
            editor = entry.get("editor", {})
            resource = editor.get("resource", "")
            
            if resource:
                parts.append(f"- `{resource}`\n")
        
        return "".join(parts)

    async def _write_markdown_file(
        self,
        markdown: str,
        workspace_hash: str,
    ) -> Path:
        """
        Write markdown to file.

        Args:
            markdown: Markdown content
            workspace_hash: Workspace hash for filename

        Returns:
            Path to written file
        """
        # Generate filename with timestamp
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{workspace_hash}_{timestamp_str}.md"
        
        output_path = self.output_dir / filename
        
        # Write file
        output_path.write_text(markdown, encoding="utf-8")
        
        return output_path

    def _format_timestamp(self, dt: datetime, use_utc: bool) -> str:
        """Format datetime to display string."""
        if use_utc:
            dt = dt.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None)
            dt = datetime.utcfromtimestamp(dt.timestamp())
        
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _format_timestamp_ms(self, unix_ms: int, use_utc: bool) -> str:
        """Format Unix timestamp (milliseconds) to display string."""
        dt = datetime.fromtimestamp(unix_ms / 1000.0)
        return self._format_timestamp(dt, use_utc)

