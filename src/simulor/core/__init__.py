"""Core package for the Simulor framework."""

from __future__ import annotations

from simulor.core.connectors import Broker, Connector, SubmitOrderResult
from simulor.core.events import (
    DataEvent,
    EndOfStreamEvent,
    Event,
    EventBus,
    EventHandler,
    EventType,
    SystemEvent,
)
from simulor.core.protocols import (
    AllocationModel,
    AlphaModel,
    Context,
    ExecutionModel,
    Feed,
    Model,
    PortfolioConstructionModel,
    RiskModel,
    UniverseSelectionModel,
)

__all__ = [
    "Broker",
    "Connector",
    "SubmitOrderResult",
    "Event",
    "DataEvent",
    "EndOfStreamEvent",
    "SystemEvent",
    "EventBus",
    "EventHandler",
    "EventType",
    "Context",
    "Model",
    "Feed",
    "UniverseSelectionModel",
    "AlphaModel",
    "PortfolioConstructionModel",
    "RiskModel",
    "ExecutionModel",
    "AllocationModel",
]
