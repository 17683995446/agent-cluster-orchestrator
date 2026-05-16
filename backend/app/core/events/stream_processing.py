"""
Agent Cluster Orchestrator - Stream Processing Module

Provides real-time data stream processing capabilities.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

import structlog

from app.core.events.event_bus_core import EventBus

logger = structlog.get_logger(__name__)


class StreamProcessor:
    """
    Real-time data stream processor for event-driven architectures.
    
    Key Features:
    - Multiple named data streams
    - Processor registration for streams
    - Backpressure management
    - Async-safe operations
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._active_streams: Dict[str, asyncio.Queue[Any]] = {}
        self._registered_processors: Dict[str, Callable[[Any], Any]] = {}
    
    def create_stream(
        self,
        stream_identifier: str,
        max_queue_size: int = 1000
    ) -> None:
        """
        Create a new named data stream.
        
        Args:
            stream_identifier: Unique identifier for the stream
            max_queue_size: Maximum number of items the stream can hold
        """
        if stream_identifier not in self._active_streams:
            self._active_streams[stream_identifier] = asyncio.Queue(
                maxsize=max_queue_size
            )
            logger.info(
                "data_stream_created",
                stream_id=stream_identifier,
                max_size=max_queue_size
            )
    
    def register_processor(
        self,
        stream_identifier: str,
        processor_function: Callable[[Any], Any]
    ) -> None:
        """
        Register a processor function for a specific stream.
        
        Args:
            stream_identifier: Stream to register the processor for
            processor_function: Function to process stream data
        """
        self._registered_processors[stream_identifier] = processor_function
        logger.debug(
            "stream_processor_registered",
            stream_id=stream_identifier
        )
    
    async def push_data_to_stream(
        self,
        stream_identifier: str,
        data_item: Any
    ) -> None:
        """
        Push a data item to a stream for processing.
        
        Args:
            stream_identifier: Stream to push data to
            data_item: Data item to add to the stream
        """
        if stream_identifier not in self._active_streams:
            self.create_stream(stream_identifier)
        
        try:
            await self._active_streams[stream_identifier].put(data_item)
            
            # Immediately process if processor is registered
            if stream_identifier in self._registered_processors:
                processor = self._registered_processors[stream_identifier]
                if asyncio.iscoroutinefunction(processor):
                    await processor(data_item)
                else:
                    processor(data_item)
            
        except asyncio.QueueFull:
            logger.warning(
                "data_stream_full_item_dropped",
                stream_id=stream_identifier
            )
    
    async def read_data_from_stream(
        self,
        stream_identifier: str,
        timeout_seconds: float = 1.0
    ) -> Optional[Any]:
        """
        Read the next available data item from a stream.
        
        Args:
            stream_identifier: Stream to read from
            timeout_seconds: Maximum time to wait for data
            
        Returns:
            Next data item from the stream, or None if timeout/empty
        """
        if stream_identifier not in self._active_streams:
            return None
        
        try:
            return await asyncio.wait_for(
                self._active_streams[stream_identifier].get(),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            return None
    
    def get_stream_size(self, stream_identifier: str) -> int:
        """
        Get current size of a stream queue.
        
        Args:
            stream_identifier: Stream to check size for
            
        Returns:
            Current number of items in the stream queue
        """
        if stream_identifier not in self._active_streams:
            return 0
        return self._active_streams[stream_identifier].qsize()
    
    def clear_stream(self, stream_identifier: str) -> None:
        """
        Clear all data from a stream queue.
        
        Args:
            stream_identifier: Stream to clear
        """
        if stream_identifier in self._active_streams:
            # Replace queue to clear it
            max_size = self._active_streams[stream_identifier].maxsize
            self._active_streams[stream_identifier] = asyncio.Queue(
                maxsize=max_size
            )
            logger.debug(
                "data_stream_cleared",
                stream_id=stream_identifier
            )
