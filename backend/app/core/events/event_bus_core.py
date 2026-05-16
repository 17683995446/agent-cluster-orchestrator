"""
Agent Cluster Orchestrator - Event Bus Core Module

Provides the central event bus implementation with publish-subscribe pattern.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import structlog

from app.core.events.event_definitions import Event, EventType

logger = structlog.get_logger(__name__)


class EventBus:
    """
    Central event bus implementation providing publish-subscribe pattern.
    
    Key Features:
    - Async event processing
    - Type-specific event subscriptions
    - Event history tracking
    - Backpressure management
    """
    
    def __init__(
        self,
        max_queue_size: int = 10000,
        max_history_size: int = 10000
    ):
        self._subscribers: Dict[EventType, List[Callable[[Event], Any]]] = {}
        self._all_subscribers: List[Callable[[Event], Any]] = []
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._is_running = False
        self._process_task: Optional[asyncio.Task] = None
        self._event_history: List[Event] = []
        self._max_history = max_history_size
        logger.debug("event_bus_initialized")
    
    async def start(self) -> None:
        """
        Start the event bus processing loop.
        
        Does nothing if the bus is already running.
        """
        if self._is_running:
            return
        
        self._is_running = True
        self._process_task = asyncio.create_task(self._process_event_queue())
        logger.info("event_bus_started")
    
    async def stop(self) -> None:
        """
        Stop the event bus processing loop.
        
        Gracefully cancels the processing task and waits for completion.
        """
        self._is_running = False
        
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        logger.info("event_bus_stopped")
    
    def subscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """
        Subscribe a callback function to receive events.
        
        Args:
            callback: Function to call when events occur
            event_types: Optional list of event types to subscribe to;
                         if None, subscribes to all events
        """
        if event_types is None:
            self._all_subscribers.append(callback)
            logger.debug("subscribed_to_all_events")
        else:
            for event_type in event_types:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                self._subscribers[event_type].append(callback)
                logger.debug(
                    "subscribed_to_event",
                    event_type=event_type
                )
    
    def unsubscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """
        Unsubscribe a callback function from receiving events.
        
        Args:
            callback: Function to remove from subscriptions
            event_types: Optional list of event types to unsubscribe from;
                         if None, unsubscribes from all events
        """
        if event_types is None:
            if callback in self._all_subscribers:
                self._all_subscribers.remove(callback)
        else:
            for event_type in event_types:
                if event_type in self._subscribers:
                    if callback in self._subscribers[event_type]:
                        self._subscribers[event_type].remove(callback)
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus for distribution.
        
        Args:
            event: Event instance to publish
        """
        try:
            await self._event_queue.put(event)
            logger.debug(
                "event_published",
                event_id=event.event_id,
                event_type=event.event_type
            )
        except asyncio.QueueFull:
            logger.warning(
                "event_queue_full_event_dropped",
                event_id=event.event_id
            )
    
    async def _process_event_queue(self) -> None:
        """Internal method to process events from the queue."""
        while self._is_running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                
                # Save event to history
                self._event_history.append(event)
                if len(self._event_history) > self._max_history:
                    self._event_history = self._event_history[-self._max_history:]
                
                # Dispatch event to subscribers
                await self._dispatch_event_to_subscribers(event)
                
                self._event_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_processing_error", error=str(e))
    
    async def _dispatch_event_to_subscribers(self, event: Event) -> None:
        """
        Internal method to dispatch a single event to all subscribers.
        
        Args:
            event: Event to dispatch
        """
        # Send to global subscribers
        for callback in self._all_subscribers:
            await self._safe_invoke_callback(callback, event)
        
        # Send to type-specific subscribers
        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                await self._safe_invoke_callback(callback, event)
    
    async def _safe_invoke_callback(
        self,
        callback: Callable[[Event], Any],
        event: Event
    ) -> None:
        """
        Safely invoke a callback, handling both sync and async functions.
        
        Args:
            callback: Function to invoke
            event: Event to pass to the callback
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            logger.error(
                "subscriber_callback_error",
                error=str(e),
                event_id=event.event_id
            )
    
    def get_event_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Retrieve historical events from the bus.
        
        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events to return
            
        Returns:
            List of historical events, newest first
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
