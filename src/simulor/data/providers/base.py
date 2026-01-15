"""Abstract base classes and protocols for data providers.

This module defines the core interfaces that all data providers must implement
to ensure consistent behavior across different data sources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Protocol

from simulor.core.events import MarketEvent
from simulor.types import MarketData

__all__ = [
    "DataIterator",
    "DataProvider",
]


class DataIterator(Protocol):
    """Protocol for iterating through market data chronologically.

    All data iterators must yield MarketEvent events in chronological order,
    ensuring no look-ahead bias in backtesting.
    """

    def __iter__(self) -> Iterator[MarketData]:
        """Return iterator for MarketEvent events."""
        ...

    def __next__(self) -> MarketData:
        """Get next market data event in chronological order.

        Returns:
            Next MarketEvent event

        Raises:
            StopIteration: When no more data is available
        """
        ...


class DataProvider(ABC):
    """Abstract interface for market data providers.

    All data providers must implement this interface to ensure consistent
    behavior across different data sources (CSV, Parquet, databases, APIs, etc.).

    Providers are reusable iterables - each call to __iter__() returns a new
    iterator, allowing multiple passes over the data.

    Guarantees:
    - Point-in-time data delivery (no look-ahead bias)
    - Chronological ordering of events
    - Reusable - can be iterated multiple times

    Example:
        >>> provider = CSVDataProvider(path='data/')
        >>> # First pass - calculate statistics
        >>> for data in provider:
        ...     calculate_stats(data)
        >>> # Second pass - run backtest with calculated statistics
        >>> for data in provider:
        ...     run_backtest(data)
    """

    @abstractmethod
    def __iter__(self) -> Iterator[MarketEvent]:
        """Return a new iterator for MarketEvent events.

        Each call returns a fresh iterator, allowing the provider
        to be iterated multiple times.

        Returns:
            New iterator yielding MarketEvent events in chronological order
        """
        pass
