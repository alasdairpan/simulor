from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from simulor.core.events import EventBus
from simulor.logging import get_logger
from simulor.types.orders import OrderSpec

if TYPE_CHECKING:
    from simulor.portfolio.manager import Portfolio

logger = get_logger(__name__)


class Connector(ABC):
    """Base class for connectors between components.

    Connectors facilitate communication and data flow between different
    parts of the system, such as data feeds, models, and execution engines.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish the connection between components."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down the connection between components."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the connection is currently established.

        Returns:
            True if connected, False otherwise
        """
        ...


@dataclass(slots=True)
class SubmitOrderResult:
    """Result of submitting an order to a broker connector."""

    order_id: str


class Broker(Connector):
    """Protocol for broker connectors.

    Broker connectors facilitate communication with execution engines to route orders
    and manage trade executions.
    """

    _event_bus: EventBus
    _global_portfolio: Portfolio
    _strategy_portfolios: dict[str, Portfolio]

    def initialize(
        self, event_bus: EventBus, global_portfolio: Portfolio, strategy_portfolios: dict[str, Portfolio]
    ) -> None:
        """Set the event bus for this broker connector."""
        self._event_bus = event_bus
        self._global_portfolio = global_portfolio
        self._strategy_portfolios = strategy_portfolios

    @property
    def event_bus(self) -> EventBus:
        """Get the event bus from the connector."""
        return self._event_bus

    @property
    def global_portfolio(self) -> Portfolio:
        """Get the global portfolio from the connector."""
        return self._global_portfolio

    @property
    def strategy_portfolios(self) -> dict[str, Portfolio]:
        """Get the strategy-specific portfolios from the connector."""
        return self._strategy_portfolios

    def register_strategy(self, strategy_name: str, capital: Decimal) -> None:
        """Register a new strategy and allocate capital from global portfolio.

        Args:
            strategy_name: Unique name for the strategy
            capital: Capital allocation for this strategy

        Raises:
            ValueError: If strategy already registered or insufficient capital
        """
        if strategy_name in self._strategy_portfolios:
            logger.error("Strategy '%s' is already registered", strategy_name)
            raise ValueError(f"Strategy '{strategy_name}' is already registered")

        if capital > self._global_portfolio.cash:
            logger.error(
                "Insufficient capital for strategy '%s': requested $%s, available $%s",
                strategy_name,
                capital,
                self._global_portfolio.cash,
            )
            raise ValueError(f"Insufficient capital: requested {capital}, available {self.global_portfolio.cash}")

        logger.debug("Registering strategy '%s' with capital=$%s", strategy_name, capital)

        # Create strategy portfolio
        self._strategy_portfolios[strategy_name] = Portfolio(starting_cash=capital)

        # Deduct from global cash (capital is now allocated to strategy)
        self._global_portfolio.update_cash(-capital)

        logger.info("Strategy '%s' registered with capital=$%s", strategy_name, capital)

    @abstractmethod
    def submit_order(self, strategy_name: str, order_spec: OrderSpec) -> SubmitOrderResult:
        """Submit an order to the execution engine.

        Args:
            strategy_name: Name of the strategy submitting the order
            order_spec: The order specification to submit
        """
        ...

    @abstractmethod
    def cancel_order(self, strategy_name: str, order_id: str) -> None:
        """Cancel an existing order by its ID.

        Args:
            strategy_name: Name of the strategy requesting the cancellation
            order_id: The unique identifier of the order to cancel
        """
        ...

    @abstractmethod
    def register_order_update_callback(self) -> None:
        """Register a callback for order updates from the broker."""
        ...
