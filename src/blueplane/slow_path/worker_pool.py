"""
Manages pools of async workers for different processing types.
Handles scaling, priority, and backpressure.
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime

from ..config import config
from ..storage.redis_cdc import CDCWorkQueue
from .metrics_worker import MetricsWorker
from .conversation_worker import ConversationWorker


class WorkerPoolManager:
    """
    Manages pools of async workers for different processing types.
    Handles scaling, priority, and backpressure.
    """

    def __init__(
        self,
        cdc_queue: Optional[CDCWorkQueue] = None,
        metrics_workers: int = None,
        conversation_workers: int = None,
        ai_insights_workers: int = None,
    ):
        """Initialize worker pool manager."""
        self.cdc_queue = cdc_queue or CDCWorkQueue()
        self.metrics_workers_count = metrics_workers or config.metrics_workers
        self.conversation_workers_count = conversation_workers or config.conversation_workers
        self.ai_insights_workers_count = ai_insights_workers or config.ai_insights_workers
        
        self.metrics_workers = []
        self.conversation_workers = []
        self.ai_insights_workers = []
        
        self.running = False
        self._backpressure_level = "green"
        self._monitor_task = None

    async def start(self) -> None:
        """
        Start all worker pools.
        
        - Create MetricsWorker instances (2x)
        - Create ConversationWorker instances (2x)
        - Create AIInsightsWorker instances (1x)
        - Start async task for each worker with _run_worker()
        - Start _monitor_backpressure() task
        """
        # Initialize CDC queue
        await self.cdc_queue.initialize()
        
        # Create metrics workers
        for i in range(self.metrics_workers_count):
            worker = MetricsWorker(
                cdc_queue=self.cdc_queue,
                worker_name=f"metrics-worker-{i+1}",
            )
            self.metrics_workers.append(worker)
            asyncio.create_task(self._run_worker(worker, "metrics"))
        
        # Create conversation workers
        for i in range(self.conversation_workers_count):
            worker = ConversationWorker(
                cdc_queue=self.cdc_queue,
                worker_name=f"conversation-worker-{i+1}",
            )
            self.conversation_workers.append(worker)
            asyncio.create_task(self._run_worker(worker, "conversation"))
        
        # TODO: Create AI insights workers (future)
        
        # Start backpressure monitoring
        self.running = True
        self._monitor_task = asyncio.create_task(self._monitor_backpressure())
        
        print(f"✅ Started {self.metrics_workers_count} metrics workers")
        print(f"✅ Started {self.conversation_workers_count} conversation workers")

    async def _run_worker(self, worker, worker_type: str) -> None:
        """
        Run single worker with error handling.
        
        While running:
        - XREADGROUP from 'cdc:events' (block 1000ms)
        - Check event priority matches worker type
        - Call worker.process(event)
        - XACK on success
        - Track stats (processed, failed)
        - On error: Log and XACK (prevent reprocessing)
        """
        worker_name = worker.worker_name
        processed = 0
        failed = 0
        
        while self.running:
            try:
                # Consume from CDC queue
                async for message_id, cdc_event in self.cdc_queue.consume(
                    consumer_name=worker_name, count=1, block=1000
                ):
                    # Check if worker should process this event based on priority
                    priority = cdc_event.get("priority", 5)
                    
                    # Route to appropriate worker based on priority
                    # Priority 1-2: metrics and conversation workers
                    # Priority 3-4: conversation workers
                    # Priority 5: all workers (low priority)
                    
                    should_process = False
                    if worker_type == "metrics":
                        # Metrics workers handle priority 1-3
                        should_process = priority <= 3
                    elif worker_type == "conversation":
                        # Conversation workers handle priority 1-4
                        should_process = priority <= 4
                    
                    if not should_process:
                        # Skip this event, acknowledge to prevent reprocessing
                        await self.cdc_queue.acknowledge(message_id)
                        continue
                    
                    try:
                        # Process event
                        await worker.process(cdc_event)
                        processed += 1
                        
                        # Acknowledge message
                        await self.cdc_queue.acknowledge(message_id)
                        
                    except Exception as e:
                        failed += 1
                        print(f"Error processing event in {worker_name}: {e}")
                        # Acknowledge anyway to prevent infinite retries
                        await self.cdc_queue.acknowledge(message_id)
                        
            except Exception as e:
                print(f"Error in worker {worker_name}: {e}")
                await asyncio.sleep(1)  # Wait before retrying
        
        print(f"Worker {worker_name} stopped. Processed: {processed}, Failed: {failed}")

    async def _monitor_backpressure(self) -> None:
        """
        Monitor queue depth and adjust workers.
        
        Every 5 seconds:
        - Check stream length with XINFO STREAM
        - Calculate lag from oldest message timestamp
        - Log warnings if length > 10000
        - Log critical if length > 50000
        - Could scale workers or pause AI workers
        """
        while self.running:
            try:
                stats = await self.cdc_queue.get_queue_stats()
                queue_length = stats.get("queue_length", 0)
                pending_count = stats.get("pending_count", 0)
                
                # Determine backpressure level
                if queue_length > 100000:
                    level = "red"
                elif queue_length > 50000:
                    level = "orange"
                elif queue_length > 10000:
                    level = "yellow"
                else:
                    level = "green"
                
                if level != self._backpressure_level:
                    self._backpressure_level = level
                    print(f"⚠️  Backpressure level: {level} (queue_length: {queue_length}, pending: {pending_count})")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Error monitoring backpressure: {e}")
                await asyncio.sleep(5)

    def stop(self) -> None:
        """Stop all workers."""
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()

    async def wait_for_completion(self) -> None:
        """Wait for all workers to complete."""
        # Wait for monitor task
        if self._monitor_task:
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    def close(self) -> None:
        """Close connections."""
        self.cdc_queue.close()

