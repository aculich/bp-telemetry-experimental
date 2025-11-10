"""
Calculates metrics from raw events.
Can read from any store since it's async.
"""

from typing import Dict, Optional

from ..storage.sqlite_traces import SQLiteTraceStorage
from ..storage.redis_metrics import RedisMetricsStorage
from ..storage.redis_cdc import CDCWorkQueue


class MetricsWorker:
    """Calculates metrics from raw events. Can read from any store since it's async."""

    def __init__(
        self,
        cdc_queue: CDCWorkQueue,
        worker_name: str = "metrics-worker-1",
        trace_storage: Optional[SQLiteTraceStorage] = None,
        metrics_storage: Optional[RedisMetricsStorage] = None,
    ):
        """Initialize metrics worker."""
        self.cdc_queue = cdc_queue
        self.worker_name = worker_name
        self.trace_storage = trace_storage or SQLiteTraceStorage()
        self.metrics_storage = metrics_storage or RedisMetricsStorage()

    async def process(self, cdc_event: Dict) -> None:
        """
        Process single CDC event to calculate metrics.
        
        1. Read full event from sqlite.get_by_sequence(sequence) and decompress
        2. Get recent session stats from sqlite.get_session_stats(session_id, window=5min)
        3. Calculate metrics based on event_type:
           - 'tool_use': Calculate latency percentiles (p50, p95, p99)
           - 'acceptance_decision': Calculate acceptance rate (sliding window of 100)
           - 'session_start': Count active sessions in last 60 minutes
        4. Write all metrics to redis_metrics.record_metric()
        
        Note: SQLite queries on raw_traces require decompression (10-40ms for session queries)
        but this is acceptable in async slow path with eventual consistency.
        
        See layer2_metrics_derivation.md for detailed metric calculations
        """
        sequence = cdc_event.get("sequence")
        if not sequence:
            return
        
        # Read full event from SQLite
        event = self.trace_storage.get_by_sequence(sequence)
        if not event:
            return
        
        event_type = event.get("event_type", "")
        session_id = event.get("session_id", "")
        platform = event.get("platform", "")
        
        # Calculate metrics based on event type
        if event_type in ("tool_use", "PostToolUse", "AfterMCPExecution"):
            await self._process_tool_use(event)
        elif event_type in ("acceptance_decision", "code_change"):
            await self._process_acceptance(event)
        elif event_type in ("session_start", "SessionStart"):
            await self._process_session_start(event)
        
        # Update session-level metrics
        await self._update_session_metrics(session_id, platform)

    async def _process_tool_use(self, event: Dict) -> None:
        """Process tool use event to calculate latency metrics."""
        duration_ms = event.get("duration_ms") or event.get("payload", {}).get("duration_ms")
        tool_name = event.get("tool_name") or event.get("payload", {}).get("tool")
        
        if duration_ms:
            # Record tool latency
            self.metrics_storage.record_metric("tools", "tool_latency", duration_ms)
            
            if tool_name:
                # Record per-tool latency
                self.metrics_storage.record_metric(
                    f"tools:{tool_name}", "latency", duration_ms
                )
            
            # Calculate percentiles (simplified - in production, use proper percentile calculation)
            # For now, we'll track recent values and calculate percentiles periodically
            self.metrics_storage.increment_counter("tools", "tool_use_count")

    async def _process_acceptance(self, event: Dict) -> None:
        """Process acceptance decision to calculate acceptance rate."""
        accepted = event.get("accepted") or event.get("payload", {}).get("accepted")
        
        if accepted is not None:
            # Increment counters
            self.metrics_storage.increment_counter("session", "total_decisions")
            if accepted:
                self.metrics_storage.increment_counter("session", "accepted_decisions")
            
            # Calculate acceptance rate (simplified - in production, use sliding window)
            # For now, we'll calculate from counters
            total_key = "metric:session:total_decisions"
            accepted_key = "metric:session:accepted_decisions"
            
            total = int(self.metrics_storage.redis.get(total_key) or 0)
            accepted_count = int(self.metrics_storage.redis.get(accepted_key) or 0)
            
            if total > 0:
                acceptance_rate = accepted_count / total
                self.metrics_storage.set_gauge("session", "acceptance_rate", acceptance_rate)

    async def _process_session_start(self, event: Dict) -> None:
        """Process session start to count active sessions."""
        # Increment active sessions counter
        self.metrics_storage.increment_counter("realtime", "active_sessions")
        
        # Record session start metric
        self.metrics_storage.record_metric("realtime", "session_starts", 1)

    async def _update_session_metrics(self, session_id: str, platform: str) -> None:
        """Update session-level aggregated metrics."""
        # Get session metrics from SQLite
        metrics = self.trace_storage.calculate_session_metrics(session_id)
        
        if metrics:
            # Update Redis metrics
            if metrics.get("total_tokens"):
                self.metrics_storage.set_gauge(
                    f"session:{session_id}", "total_tokens", metrics["total_tokens"]
                )
            
            if metrics.get("avg_duration_ms"):
                self.metrics_storage.set_gauge(
                    f"session:{session_id}", "avg_latency_ms", metrics["avg_duration_ms"]
                )

    def close(self) -> None:
        """Close storage connections."""
        self.trace_storage.close()
        self.metrics_storage.close()

