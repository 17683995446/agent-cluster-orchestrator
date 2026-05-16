"""
Agent Cluster Orchestrator - Events Package

Provides comprehensive event-driven architecture with:
- Event definitions and types
- Central event bus with publish-subscribe
- Event emitter with convenience methods
- Real-time stream processing
- Event persistence capabilities
- Backward compatibility maintained

Usage:
```python
from app.core.events import (
    initialize_event_system,
    get_event_bus,
    get_event_emitter,
    EventType,
    Event
)

# Initialize the event system
initialize_event_system()

# Get event emitter and emit events
emitter = get_event_emitter("my_component")
await emitter.emit_task_created("task_123")
```
"""
from app.core.events.event_definitions import (
    Event,
    EventType,
    EventPriority
)
from app.core.events.event_bus_core import EventBus
from app.core.events.event_emitter import EventEmitter
from app.core.events.stream_processing import StreamProcessor
from app.core.events.event_persistence import EventPersister

# Global instances for backward compatibility and easy access
_event_bus_instance: Optional[EventBus] = None
_stream_processor_instance: Optional[StreamProcessor] = None
_event_persister_instance: Optional[EventPersister] = None


def initialize_event_system() -> None:
    """
    Initialize all components of the event system.
    
    Creates and connects event bus, stream processor, and event persister.
    Idempotent - can safely be called multiple times.
    """
    global _event_bus_instance, _stream_processor_instance, _event_persister_instance
    
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
        _stream_processor_instance = StreamProcessor(_event_bus_instance)
        _event_persister_instance = EventPersister(_event_bus_instance)
        
        import structlog
        logger = structlog.get_logger(__name__)
        logger.info("event_system_initialized")


async def start_event_system() -> None:
    """
    Start the event system processing loops.
    
    Should be called after initialization and before emitting events.
    """
    if _event_bus_instance is None:
        initialize_event_system()
    
    await _event_bus_instance.start()
    await _event_persister_instance.start()


async def stop_event_system() -> None:
    """
    Stop the event system processing loops gracefully.
    """
    if _event_persister_instance:
        await _event_persister_instance.stop()
    if _event_bus_instance:
        await _event_bus_instance.stop()


def get_event_bus() -> EventBus:
    """
    Get the global event bus instance.
    
    Returns:
        The global EventBus instance
    """
    if _event_bus_instance is None:
        initialize_event_system()
    return _event_bus_instance


def get_event_emitter(source_identifier: str) -> EventEmitter:
    """
    Get an event emitter for the specified source.
    
    Args:
        source_identifier: Identifier for the component emitting events
        
    Returns:
        EventEmitter instance configured for the specified source
    """
    return EventEmitter(get_event_bus(), source_identifier)


def get_stream_processor() -> StreamProcessor:
    """
    Get the global stream processor instance.
    
    Returns:
        The global StreamProcessor instance
    """
    if _stream_processor_instance is None:
        initialize_event_system()
    return _stream_processor_instance


def get_event_persister() -> EventPersister:
    """
    Get the global event persister instance.
    
    Returns:
        The global EventPersister instance
    """
    if _event_persister_instance is None:
        initialize_event_system()
    return _event_persister_instance


__all__ = [
    # Event definitions
    "Event",
    "EventType",
    "EventPriority",
    # Core components
    "EventBus",
    "EventEmitter",
    "StreamProcessor",
    "EventPersister",
    # System management
    "initialize_event_system",
    "start_event_system",
    "stop_event_system",
    # Instance accessors
    "get_event_bus",
    "get_event_emitter",
    "get_stream_processor",
    "get_event_persister",
]
