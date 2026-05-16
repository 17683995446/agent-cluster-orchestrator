"""
Agent Cluster Orchestrator - Event Persistence Module

Provides event persistence and storage capabilities.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional

import structlog

from app.core.events.event_bus_core import EventBus
from app.core.events.event_definitions import Event

logger = structlog.get_logger(__name__)


class EventPersister:
    """
    Event persistence manager that saves events to durable storage.
    
    Key Features:
    - Async event persistence
    - Queue-based batching
    - Configurable storage backends
    - Graceful shutdown
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        persistence_queue_size: int = 1000
    ):
        self.event_bus = event_bus
        self._persistence_queue: asyncio.Queue[Event] = asyncio.Queue(
            maxsize=persistence_queue_size
        )
        self._persistence_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._storage_handlers: List[Callable[[Event], Any]] = []
        
        # Subscribe to all events from the bus
        self.event_bus.subscribe(self._handle_incoming_event)
    
    def register_storage_handler(
        self,
        storage_handler: Callable[[Event], Any]
    ) -> None:
        """
        Register a storage handler function for events.
        
        Storage handlers are responsible for actually persisting
        events to their chosen storage backend (database, file, etc.)
        
        Args:
            storage_handler: Function that receives events to persist
        """
        self._storage_handlers.append(storage_handler)
        logger.debug("event_storage_handler_registered")
    
    async def start(self) -> None:
        """
        Start the event persistence processing loop.
        
        Does nothing if already running.
        """
        if self._is_running:
            return
        
        self._is_running = True
        self._persistence_task = asyncio.create_task(
            self._process_persistence_queue()
        )
        logger.info("event_persister_started")
    
    async def stop(self) -> None:
        """
        Stop the event persistence processing loop.
        
        Gracefully cancels the processing task and waits for completion.
        """
        self._is_running = False
        
        if self._persistence_task:
            self._persistence_task.cancel()
            try:
                await self._persistence_task
            except asyncio.CancelledError:
                pass
        
        logger.info("event_persister_stopped")
    
    async def _handle_incoming_event(self, event: Event) -> None:
        """
        Internal callback for events from the event bus.
        
        Args:
            event: Event to persist
        """
        try:
            await self._persistence_queue.put(event)
        except asyncio.QueueFull:
            logger.warning(
                "persistence_queue_full_event_dropped",
                event_id=event.event_id
            )
    
    async def _process_persistence_queue(self) -> None:
        """Internal method to process the persistence queue."""
        while self._is_running:
            try:
                event = await asyncio.wait_for(
                    self._persistence_queue.get(),
                    timeout=1.0
                )
                
                # Dispatch to storage handlers
                for handler in self._storage_handlers:
                    await self._safe_invoke_storage_handler(handler, event)
                
                # Simple fallback logging if no handlers registered
                if not self._storage_handlers:
                    logger.debug(
                        "event_would_be_persisted",
                        event_id=event.event_id,
                        event_type=event.event_type
                    )
                
                self._persistence_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_persister_processing_error", error=str(e))
    
    async def _safe_invoke_storage_handler(
        self,
        handler: Callable[[Event], Any],
        event: Event
    ) -> None:
        """
        Safely invoke a storage handler, handling both sync and async.
        
        Args:
            handler: Storage handler function to invoke
            event: Event to pass to the handler
        """
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(
                "storage_handler_execution_error",
                error=str(e),
                event_id=event.event_id
            )
