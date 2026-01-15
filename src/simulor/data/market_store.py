"""Historical market data storage and retrieval API.

Provides type-safe access to historical market data for strategy components.
All data is retained in memory with typed lists for efficient queries.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from simulor.base.collections import ReadOnlySequence

if TYPE_CHECKING:
    from simulor.core.events import MarketEvent

from simulor.types import (
    Instrument,
    MarketData,
    QuoteBar,
    QuoteTick,
    Resolution,
    TradeBar,
    TradeTick,
)

__all__ = ["MarketStore"]


class MarketStore:
    """Historical market data storage and retrieval.

    Maintains all historical market data in memory, organized by instrument,
    resolution, and data type. Provides efficient lookback queries for strategy
    components to access historical prices, bars, and ticks.

    Design decisions:
    - Type-specific storage: Separate lists for TradeTick, QuoteTick, TradeBar, QuoteBar
    - All data retained in memory
    - Returns read-only sequence views (zero-copy, immutable)
    - O(1) access by instrument and data type

    Examples:
        >>> store = MarketStore()
        >>> # Access data by type
        >>> ticks = store.get_trade_ticks(instrument)
        >>> bars = store.get_trade_bars(instrument, Resolution.MINUTE)
        >>> latest = ticks[-1] if ticks else None
        >>> last_10 = ticks[-10:]  # Slice returns immutable view
    """

    def __init__(self) -> None:
        """Initialize empty market data storage."""
        # Separate storage for each data type
        self._trade_ticks: dict[Instrument, list[TradeTick]] = {}
        self._quote_ticks: dict[Instrument, list[QuoteTick]] = {}
        self._trade_bars: dict[Instrument, dict[Resolution, list[TradeBar]]] = {}
        self._quote_bars: dict[Instrument, dict[Resolution, list[QuoteBar]]] = {}
        # Cache for latest market data per instrument
        self._latest_market_data_cache: dict[Instrument, MarketData] = {}

    def get_trade_ticks(self, instrument: Instrument) -> Sequence[TradeTick]:
        """Get trade tick data for an instrument.

        Args:
            instrument: The instrument to get data for

        Returns:
            Read-only sequence of trade ticks, empty sequence if no data exists
        """
        data = self._trade_ticks.get(instrument)
        return ReadOnlySequence(data if data else [])

    def get_quote_ticks(self, instrument: Instrument) -> Sequence[QuoteTick]:
        """Get quote tick data for an instrument.

        Args:
            instrument: The instrument to get data for

        Returns:
            Read-only sequence of quote ticks, empty sequence if no data exists
        """
        data = self._quote_ticks.get(instrument)
        return ReadOnlySequence(data if data else [])

    def get_trade_bars(self, instrument: Instrument, resolution: Resolution) -> Sequence[TradeBar]:
        """Get trade bar data for an instrument.

        Args:
            instrument: The instrument to get data for
            resolution: The resolution to get data for (SECOND, MINUTE, HOUR, DAILY)

        Returns:
            Read-only sequence of trade bars, empty sequence if no data exists
        """
        data = self._trade_bars.get(instrument, {}).get(resolution)
        return ReadOnlySequence(data if data else [])

    def get_quote_bars(self, instrument: Instrument, resolution: Resolution) -> Sequence[QuoteBar]:
        """Get quote bar data for an instrument.

        Args:
            instrument: The instrument to get data for
            resolution: The resolution to get data for (SECOND, MINUTE, HOUR, DAILY)

        Returns:
            Read-only sequence of quote bars, empty sequence if no data exists
        """
        data = self._quote_bars.get(instrument, {}).get(resolution)
        return ReadOnlySequence(data if data else [])

    def get_latest_price(self, instrument: Instrument) -> Decimal:
        """Get the most recent price for an instrument.

        Searches across all resolutions and data types for the latest price.

        Args:
            instrument: The instrument to get price for

        Returns:
            The most recent price as Decimal

        Raises:
            ValueError: If no price data exists for the instrument
        """

        latest_price: Decimal
        latest_data = self._latest_market_data_cache.get(instrument)

        if latest_data is None:
            raise ValueError(f"No price data available for instrument: {instrument}")
        if isinstance(latest_data, TradeTick):
            latest_price = latest_data.price
        elif isinstance(latest_data, QuoteTick):
            latest_price = latest_data.mid_price
        elif isinstance(latest_data, TradeBar):
            latest_price = latest_data.close
        elif isinstance(latest_data, QuoteBar):
            latest_price = latest_data.mid_close
        else:
            raise TypeError(f"Unknown market data type: {type(latest_data)}")

        return latest_price

    def all_instruments(self) -> set[Instrument]:
        """Get all instruments with stored market data.

        Returns:
            Set of all instruments in the store
        """
        return {*self._latest_market_data_cache.keys()}

    def get_latest_prices(self, instruments: Sequence[Instrument]) -> dict[Instrument, Decimal]:
        """Get the most recent prices for multiple instruments.

        Args:
            instruments: Sequence of instruments to get prices for
        Returns:
            Dictionary mapping instruments to their most recent prices
        """
        latest_prices: dict[Instrument, Decimal] = {}
        for instrument in instruments:
            try:
                latest_prices[instrument] = self.get_latest_price(instrument)
            except ValueError:
                continue
        return latest_prices

    def _update_latest_market_data_cache(self, market_data: MarketData) -> None:
        """Update the latest market data cache with new data.

        Args:
            market_data: MarketData instance (TradeTick, QuoteTick, TradeBar, or QuoteBar)
        """
        instrument = market_data.instrument
        timestamp = market_data.timestamp

        if (
            instrument not in self._latest_market_data_cache
            or timestamp > self._latest_market_data_cache[instrument].timestamp
        ):
            self._latest_market_data_cache[instrument] = market_data

    def update(self, market_event: MarketEvent) -> None:
        """Update store with new market data.

        Dispatches to appropriate storage based on data type.
        Data is appended to maintain chronological order.

        Args:
            market_event: MarketEvent instance containing new market data
        """

        for market_data in market_event.flatten():
            if isinstance(market_data, TradeTick):
                self._trade_ticks.setdefault(market_data.instrument, []).append(market_data)
                self._update_latest_market_data_cache(market_data)
            elif isinstance(market_data, QuoteTick):
                self._quote_ticks.setdefault(market_data.instrument, []).append(market_data)
                self._update_latest_market_data_cache(market_data)
            elif isinstance(market_data, TradeBar):
                self._trade_bars.setdefault(market_data.instrument, {}).setdefault(market_data.resolution, []).append(
                    market_data
                )
                self._update_latest_market_data_cache(market_data)
            elif isinstance(market_data, QuoteBar):
                self._quote_bars.setdefault(market_data.instrument, {}).setdefault(market_data.resolution, []).append(
                    market_data
                )
                self._update_latest_market_data_cache(market_data)
            else:
                raise TypeError(f"Unknown data type: {type(market_data)}")
