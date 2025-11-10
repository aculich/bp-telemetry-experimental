"""
Fast path components for low-latency event ingestion.
"""

from .consumer import FastPathConsumer
from .writer import SQLiteBatchWriter
from .cdc import CDCPublisher

__all__ = [
    "FastPathConsumer",
    "SQLiteBatchWriter",
    "CDCPublisher",
]
