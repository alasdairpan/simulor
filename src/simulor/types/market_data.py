"""Market data type definitions.

This module defines MarketData and subclasses with NO imports from simulor packages except types.common.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from simulor.types.common import Resolution, TickDirection
from simulor.types.instruments import Instrument

__all__ = ["MarketData", "TradeTick", "QuoteTick", "TradeBar", "QuoteBar"]


@dataclass(frozen=True, slots=True)
class MarketData:
    """Base class for all market data types.

    Attributes:
        timestamp: Time of the market data point
        instrument: The financial instrument this data represents
        resolution: Time resolution of the data
    """

    timestamp: datetime
    instrument: Instrument
    resolution: Resolution


@dataclass(frozen=True, slots=True)
class TradeTick(MarketData):
    """Single trade execution (Level 1 data).

    Attributes:
        price: Execution price of the trade
        size: Quantity traded
        direction: Direction of the trade (optional)
    """

    price: Decimal
    size: Decimal
    direction: TickDirection | None = None

    def __post_init__(self) -> None:
        """Validate trade tick data."""
        if self.price <= 0:
            raise ValueError("Price must be positive")
        if self.size <= 0:
            raise ValueError("Size must be positive")
        if self.resolution != Resolution.TICK:
            raise ValueError("TradeTick resolution must be TICK")


@dataclass(frozen=True, slots=True)
class QuoteTick(MarketData):
    """Bid/ask quote snapshot (Level 1 data).

    Attributes:
        bid_price: Best bid price
        bid_size: Size available at the best bid
        ask_price: Best ask (offer) price
        ask_size: Size available at the best ask
    """

    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal

    def __post_init__(self) -> None:
        """Validate quote tick data."""
        if self.bid_price <= 0 or self.ask_price <= 0:
            raise ValueError("Prices must be positive")
        if self.bid_price >= self.ask_price:
            raise ValueError("Bid must be less than ask")
        if self.bid_size < 0 or self.ask_size < 0:
            raise ValueError("Sizes cannot be negative")
        if self.resolution != Resolution.TICK:
            raise ValueError("QuoteTick resolution must be TICK")

    @property
    def spread(self) -> Decimal:
        """Calculate bid-ask spread."""
        return self.ask_price - self.bid_price

    @property
    def mid_price(self) -> Decimal:
        """Calculate mid-point price."""
        return (self.bid_price + self.ask_price) / 2


@dataclass(frozen=True, slots=True)
class TradeBar(MarketData):
    """Aggregated trade data over a time period (OHLCV bar).

    Attributes:
        open: Opening price for the period
        high: Highest price during the period
        low: Lowest price during the period
        close: Closing price for the period
        volume: Total volume traded during the period
    """

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        """Validate OHLC data consistency."""
        if not (self.low <= self.open <= self.high):
            raise ValueError("Open must be between low and high")
        if not (self.low <= self.close <= self.high):
            raise ValueError("Close must be between low and high")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")


@dataclass(frozen=True, slots=True)
class QuoteBar(MarketData):
    """Aggregated quote data over a time period.

    Attributes:
        bid_open: Opening bid price
        bid_high: Highest bid price
        bid_low: Lowest bid price
        bid_close: Closing bid price
        ask_open: Opening ask price
        ask_high: Highest ask price
        ask_low: Lowest ask price
        ask_close: Closing ask price
    """

    bid_open: Decimal
    bid_high: Decimal
    bid_low: Decimal
    bid_close: Decimal
    ask_open: Decimal
    ask_high: Decimal
    ask_low: Decimal
    ask_close: Decimal

    def __post_init__(self) -> None:
        """Validate quote bar OHLC consistency."""
        if not (self.bid_low <= self.bid_open <= self.bid_high):
            raise ValueError("Bid open must be between bid low and high")
        if not (self.bid_low <= self.bid_close <= self.bid_high):
            raise ValueError("Bid close must be between bid low and high")
        if not (self.ask_low <= self.ask_open <= self.ask_high):
            raise ValueError("Ask open must be between ask low and high")
        if not (self.ask_low <= self.ask_close <= self.ask_high):
            raise ValueError("Ask close must be between ask low and high")

    @property
    def mid_close(self) -> Decimal:
        """Calculate mid-point close price."""
        return (self.bid_close + self.ask_close) / 2
