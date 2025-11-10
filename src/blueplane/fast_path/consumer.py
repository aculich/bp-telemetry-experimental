"""
Fast path consumer that reads from Redis Streams and batches events.
"""

import asyncio
import json
import redis
from typing import Dict, List, Optional
from datetime import datetime

from ..config import config
from .writer import SQLiteBatchWriter
from .cdc import CDCPublisher


class FastPathConsumer:
    """
    High-throughput consumer that writes raw events with zero blocking.
    Target: <10ms per batch at P95.
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        writer: Optional[SQLiteBatchWriter] = None,
        cdc_publisher: Optional[CDCPublisher] = None,
    ):
        """Initialize fast path consumer."""
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                decode_responses=True,
            )
        
        self.writer = writer or SQLiteBatchWriter()
        self.cdc_publisher = cdc_publisher or CDCPublisher(redis_client=self.redis)
        
        self.batch_size = config.fast_path_batch_size
        self.batch_timeout = config.fast_path_batch_timeout_ms / 1000.0  # Convert to seconds
        self.stream_name = config.mq_stream_name
        self.consumer_group = config.mq_consumer_group
        self.consumer_name = "fast-path-1"
        
        self.running = False
        self._initialize_consumer_group()

    def _initialize_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
        except redis.exceptions.ResponseError as e:
            # Group already exists, that's fine
            if "BUSYGROUP" not in str(e):
                raise

    def calculate_priority(self, event: Dict) -> int:
        """
        Assign priority for async processing.
        
        Priority levels (1=highest):
        1 - user_prompt, acceptance_decision
        2 - tool_use, completion
        3 - performance, latency
        4 - session_start, session_end
        5 - debug/trace events
        """
        event_type = event.get("event_type", "")
        hook_type = event.get("hook_type", "")
        
        if event_type in ("user_prompt", "acceptance_decision") or hook_type in (
            "UserPromptSubmit",
            "BeforeSubmitPrompt",
        ):
            return 1
        elif event_type in ("tool_use", "completion") or hook_type in (
            "PostToolUse",
            "AfterMCPExecution",
        ):
            return 2
        elif event_type in ("performance", "latency"):
            return 3
        elif event_type in ("session_start", "session_end") or hook_type in ("SessionStart", "Stop"):
            return 4
        else:
            return 5

    async def run(self) -> None:
        """
        Main consumer loop using Redis Streams XREADGROUP.
        
        While True:
        - Read from Redis Streams (blocking 1 second if no messages)
        - Use XREADGROUP for consumer group pattern
        - For each message:
          - Parse event data from stream entry
          - Add _sequence (auto-increment via SQLite) and _ingested_at
          - Append to batch
          - Track message ID for later XACK
          - Flush if batch_size reached
        - Time-based flush if batch_timeout exceeded
        - On successful flush: XACK all processed message IDs
        - On error: Don't XACK (messages will retry via PEL)
        """
        self.running = True
        batch = []
        message_ids = []
        last_flush = asyncio.get_event_loop().time()
        
        while self.running:
            try:
                # Read from stream with blocking
                messages = self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},  # Read new messages
                    count=self.batch_size,
                    block=1000,  # Block for 1 second
                )
                
                if not messages:
                    # Check if we need to flush based on timeout
                    now = asyncio.get_event_loop().time()
                    if batch and (now - last_flush) >= self.batch_timeout:
                        await self._flush_batch(batch, message_ids)
                        batch = []
                        message_ids = []
                        last_flush = now
                    continue
                
                # Parse messages
                stream_name, message_list = messages[0]
                for message_id, fields in message_list:
                    # Parse event from stream entry
                    event_data = fields.get("data", "{}")
                    try:
                        event = json.loads(event_data)
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        continue
                    
                    # Add ingestion metadata
                    event["_ingested_at"] = datetime.utcnow().isoformat()
                    
                    # Append to batch
                    batch.append(event)
                    message_ids.append(message_id)
                    
                    # Flush if batch size reached
                    if len(batch) >= self.batch_size:
                        await self._flush_batch(batch, message_ids)
                        batch = []
                        message_ids = []
                        last_flush = asyncio.get_event_loop().time()
                
                # Check timeout-based flush
                now = asyncio.get_event_loop().time()
                if batch and (now - last_flush) >= self.batch_timeout:
                    await self._flush_batch(batch, message_ids)
                    batch = []
                    message_ids = []
                    last_flush = now
                    
            except Exception as e:
                # Log error but continue
                print(f"Error in fast path consumer: {e}")
                await asyncio.sleep(1)  # Wait before retrying

    async def _flush_batch(self, batch: List[Dict], message_ids: List[str]) -> None:
        """
        Write batch to SQLite (compressed) and publish CDC events.
        
        - writer.write_batch(batch)  # SQLite insert with zlib compression
        - For each event: cdc.publish(...)  # Fire-and-forget to CDC stream
        - XACK all message IDs in batch (mark as processed)
        - Clear batch and message_ids list
        - On error: Log but don't XACK (automatic retry via PEL)
        - Handle DLQ: if retry_count >= 3, XADD to telemetry:dlq and XACK
        """
        if not batch:
            return
        
        try:
            # Write to SQLite (synchronous, but fast)
            self.writer.write_batch(batch)
            
            # Publish CDC events (fire-and-forget)
            for event in batch:
                priority = self.calculate_priority(event)
                cdc_event = {
                    "sequence": event.get("_sequence"),  # Set by writer
                    "event_id": event.get("event_id"),
                    "session_id": event.get("session_id"),
                    "event_type": event.get("event_type"),
                    "platform": event.get("platform"),
                    "priority": priority,
                    "timestamp": event.get("timestamp"),
                }
                self.cdc_publisher.publish(cdc_event)
            
            # Acknowledge all messages
            if message_ids:
                self.redis.xack(self.stream_name, self.consumer_group, *message_ids)
                
        except Exception as e:
            # Log error but don't XACK - messages will retry via PEL
            print(f"Error flushing batch: {e}")
            # TODO: Implement DLQ logic for messages with retry_count >= 3

    def stop(self) -> None:
        """Stop the consumer."""
        self.running = False

    def close(self) -> None:
        """Close connections."""
        self.writer.close()
        self.redis.close()

