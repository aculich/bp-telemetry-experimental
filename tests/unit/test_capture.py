"""
Unit tests for Layer 1 capture components.
"""

import pytest
import json
import redis
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from blueplane.capture.queue_writer import MessageQueueWriter
from blueplane.capture.claude_hooks import build_claude_event, run_claude_hook
from blueplane.capture.cursor_hooks import build_cursor_event, run_cursor_hook
from blueplane.config import config


class TestMessageQueueWriter:
    """Test MessageQueueWriter."""

    def test_enqueue_success(self):
        """Test successful event enqueue."""
        mock_redis = Mock()
        mock_redis.xadd = Mock(return_value="12345-0")
        
        writer = MessageQueueWriter(redis_client=mock_redis)
        
        event = {
            "hook_type": "SessionStart",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {"cwd": "/test"},
        }
        
        result = writer.enqueue(
            event=event,
            platform="claude_code",
            session_id="test-session-123",
            hook_type="SessionStart",
        )
        
        assert result is True
        assert mock_redis.xadd.called
        call_args = mock_redis.xadd.call_args
        assert call_args[1]["name"] == config.mq_stream_name
        assert "event_id" in call_args[1]["fields"]
        assert call_args[1]["fields"]["platform"] == "claude_code"
        assert call_args[1]["fields"]["external_session_id"] == "test-session-123"

    def test_enqueue_connection_error(self):
        """Test enqueue handles connection errors gracefully."""
        mock_redis = Mock()
        mock_redis.xadd = Mock(side_effect=redis.ConnectionError("Connection refused"))
        
        writer = MessageQueueWriter(redis_client=mock_redis)
        
        event = {
            "hook_type": "SessionStart",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {},
        }
        
        result = writer.enqueue(
            event=event,
            platform="claude_code",
            session_id="test-session",
        )
        
        assert result is False  # Silent failure

    def test_enqueue_timeout(self):
        """Test enqueue handles timeout errors gracefully."""
        mock_redis = Mock()
        mock_redis.xadd = Mock(side_effect=redis.TimeoutError("Timeout"))
        
        writer = MessageQueueWriter(redis_client=mock_redis)
        
        event = {
            "hook_type": "SessionStart",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {},
        }
        
        result = writer.enqueue(
            event=event,
            platform="claude_code",
            session_id="test-session",
        )
        
        assert result is False  # Silent failure

    def test_test_connection(self):
        """Test connection test."""
        mock_redis = Mock()
        mock_redis.ping = Mock(return_value=True)
        
        writer = MessageQueueWriter(redis_client=mock_redis)
        assert writer.test_connection() is True
        
        mock_redis.ping = Mock(side_effect=Exception("Connection failed"))
        assert writer.test_connection() is False


class TestClaudeHooks:
    """Test Claude Code hooks."""

    def test_build_claude_event(self):
        """Test building Claude event."""
        hook_data = {
            "session_id": "test-session",
            "cwd": "/test",
            "transcript_path": "/path/to/transcript.jsonl",
        }
        
        event = build_claude_event(
            hook_type="SessionStart",
            session_id="test-session",
            hook_data=hook_data,
            sequence_num=1,
        )
        
        assert event["hook_type"] == "SessionStart"
        assert event["sequence_num"] == 1
        assert event["payload"] == hook_data
        assert "timestamp" in event

    @patch("blueplane.capture.claude_hooks.MessageQueueWriter")
    @patch("sys.stdin")
    @patch("sys.exit")
    def test_run_claude_hook_success(self, mock_exit, mock_stdin, mock_writer_class):
        """Test running Claude hook successfully."""
        mock_stdin.read.return_value = json.dumps({
            "session_id": "test-session",
            "cwd": "/test",
        })
        
        mock_writer = Mock()
        mock_writer.enqueue = Mock(return_value=True)
        mock_writer_class.return_value = mock_writer
        
        run_claude_hook("SessionStart")
        
        assert mock_writer.enqueue.called
        mock_exit.assert_called_with(0)

    @patch("sys.stdin")
    @patch("sys.exit")
    def test_run_claude_hook_no_session_id(self, mock_exit, mock_stdin):
        """Test hook exits silently when no session_id."""
        mock_stdin.read.return_value = json.dumps({"cwd": "/test"})
        
        run_claude_hook("SessionStart")
        
        mock_exit.assert_called_with(0)

    @patch("sys.stdin")
    @patch("sys.exit")
    def test_run_claude_hook_invalid_json(self, mock_exit, mock_stdin):
        """Test hook exits silently on invalid JSON."""
        mock_stdin.read.return_value = "invalid json"
        
        run_claude_hook("SessionStart")
        
        mock_exit.assert_called_with(0)


class TestCursorHooks:
    """Test Cursor hooks."""

    def test_build_cursor_event(self):
        """Test building Cursor event."""
        hook_args = {
            "workspace_root": "/test",
            "generation_id": "gen-123",
            "prompt_length": 100,
        }
        
        event = build_cursor_event(
            hook_type="beforeSubmitPrompt",
            session_id="test-session",
            hook_args=hook_args,
            sequence_num=1,
        )
        
        assert event["hook_type"] == "beforeSubmitPrompt"
        assert event["sequence_num"] == 1
        assert event["payload"] == hook_args
        assert "timestamp" in event

    @patch("blueplane.capture.cursor_hooks.MessageQueueWriter")
    @patch("os.getenv")
    @patch("sys.exit")
    def test_run_cursor_hook_success(self, mock_exit, mock_getenv, mock_writer_class):
        """Test running Cursor hook successfully."""
        mock_getenv.return_value = "test-session"
        
        mock_writer = Mock()
        mock_writer.enqueue = Mock(return_value=True)
        mock_writer_class.return_value = mock_writer
        
        # Mock argparse
        with patch("sys.argv", ["script", "--workspace-root", "/test"]):
            run_cursor_hook("beforeSubmitPrompt")
        
        assert mock_writer.enqueue.called
        mock_exit.assert_called_with(0)

    @patch("os.getenv")
    @patch("sys.exit")
    def test_run_cursor_hook_no_session_id(self, mock_exit, mock_getenv):
        """Test hook exits silently when no session_id."""
        mock_getenv.return_value = None
        
        run_cursor_hook("beforeSubmitPrompt")
        
        mock_exit.assert_called_with(0)

