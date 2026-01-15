"""Strategy component protocol definitions.

Defines protocols for all strategy components in the framework:
- UniverseSelectionModel: Determine which instruments to trade
- AlphaModel: Generate trading signals from market data
- PortfolioConstructionModel: Calculate target positions from signals
- RiskModel: Apply risk limits to position targets
- ExecutionModel: Convert position targets into orders
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from simulor.alpha.signal import Signal
    from simulor.core.events import DataEvent, EventBus, MarketEvent
    from simulor.data.market_store import MarketStore
    from simulor.portfolio.manager import Portfolio
    from simulor.types import Instrument, OrderSpec


class Context:
    """Execution context for all component models.

    Provides access to engine state for strategy components.
    """

    def __init__(self, market_store: MarketStore, portfolio: Portfolio, event_bus: EventBus) -> None:
        self.market_store = market_store
        self.portfolio = portfolio
        self.event_bus = event_bus


class Model:
    """Base class for strategy models with context access."""

    def set_context(self, context: Context) -> None:
        """Set the context for this model."""
        self._context = context

    @property
    def market_store(self) -> MarketStore:
        """Get the market store from the context."""
        return self._context.market_store

    @property
    def portfolio(self) -> Portfolio:
        """Get the portfolio from the context."""
        return self._context.portfolio

    @property
    def event_bus(self) -> EventBus:
        """Get the event bus from the context."""
        return self._context.event_bus


class Feed(ABC):
    _event_bus: EventBus

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for this feed."""
        self._event_bus = event_bus

    @abstractmethod
    def run(self) -> None:
        ...

    def start(self) -> None:
        """Start the feed in a separate thread."""
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

    def publish_event(self, event: DataEvent) -> None:
        """Publish a data event to the event bus."""
        self._event_bus.publish(event)


class UniverseSelectionModel(Model, ABC):
    """Protocol for universe selection.

    Universe selection models determine which instruments the strategy
    should consider trading at any point in time.

    Components have access to:
    - self.market_store: Historical market data
    - self.portfolio: Current portfolio state
    """

    @abstractmethod
    def select_universe(self) -> list[Instrument]:
        """Return list of instruments to trade.

        Returns:
            List of instruments in the current trading universe.
            This list can change over time (dynamic universe selection).
        """
        ...


class AlphaModel(Model, ABC):
    """Protocol for alpha signal generation.

    Alpha models analyze market data and generate trading signals
    indicating direction (buy/sell) and strength.

    Components have access to:
    - self.market_store: Historical market data
    - self.portfolio: Current portfolio state
    """

    @abstractmethod
    def generate_signals(self, market_event: MarketEvent) -> dict[Instrument, Signal]:
        """Generate trading signals from market data.

        Args:
            market_event: Current market data event
        Returns:
            Dictionary mapping instruments to signals.
            Only return signals for instruments you want to trade.
            Omit instruments with no signal.
        """
        ...


class PortfolioConstructionModel(Model, ABC):
    """Protocol for portfolio construction.

    Portfolio construction models convert trading signals into target
    positions, handling position sizing and portfolio weight allocation.

    Components have access to:
    - self.market_store: Historical market data
    - self.portfolio: Current portfolio state
    """

    @abstractmethod
    def calculate_targets(
        self,
        signals: dict[Instrument, Signal],
    ) -> dict[Instrument, Decimal]:
        """Calculate target positions from signals.

        Args:
            signals: Trading signals from alpha models

        Returns:
            Dictionary mapping instruments to target quantities.
            Positive = long, negative = short, zero = flat.
        """
        ...


class RiskModel(Model, ABC):
    """Protocol for risk management.

    Risk models apply constraints and limits to position targets,
    ensuring the strategy stays within defined risk parameters.

    Components have access to:
    - self.market_store: Historical market data
    - self.portfolio: Current portfolio state
    """

    @abstractmethod
    def apply_limits(
        self,
        targets: dict[Instrument, Decimal],
    ) -> dict[Instrument, Decimal]:
        """Apply risk limits to position targets.

        Args:
            targets: Target positions from portfolio construction

        Returns:
            Adjusted target positions after applying risk limits.
            Typically returns same or reduced positions.
        """
        ...


class ExecutionModel(Model, ABC):
    """Protocol for order execution.

    Execution models convert position targets into executable orders,
    handling order types, timing, and other execution details.

    Components have access to:
    - self.market_store: Historical market data
    - self.portfolio: Current portfolio state
    """

    @abstractmethod
    def generate_orders(
        self,
        targets: dict[Instrument, Decimal],
    ) -> list[OrderSpec]:
        """Generate orders to reach target positions.

        Args:
            targets: Target positions after risk management

        Returns:
            List of order specifications to execute.
        """
        ...


class AllocationModel(Model, ABC):
    """Protocol for portfolio-level capital allocation across strategies.

    Allocation models determine how total portfolio capital is distributed
    among multiple strategies. Examples include equal weight, risk parity,
    performance-based, or custom allocation schemes.
    """

    @abstractmethod
    def allocate(self, strategy_names: Iterable[str], total_capital: Decimal) -> dict[str, Decimal]:
        """Calculate capital allocation for each strategy.

        Args:
            strategy_names: Set of strategy names to allocate capital to
            total_capital: Total capital available for allocation

        Returns:
            Dictionary mapping strategy name to allocated capital amount
        """
        ...
