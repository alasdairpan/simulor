"""Common enums and types used across Simulor.

This module contains simple enums with NO imports from simulor packages.
"""

from __future__ import annotations

from enum import Enum, IntEnum

__all__ = [
    "OrderSide",
    "TimeInForce",
    "AssetType",
    "OptionType",
    "TickDirection",
    "Resolution",
    "ColumnName",
]


class OrderSide(Enum):
    """Order side."""

    BUY = "buy"  # Opening a long or closing a short
    SELL = "sell"  # Closing a long or opening a short


class TimeInForce(Enum):
    """Order time-in-force."""

    GTC = "gtc"  # Good-till-canceled
    DAY = "day"  # Day order
    IOC = "ioc"  # Immediate-or-cancel
    FOK = "fok"  # Fill-or-kill
    GTD = "gtd"  # Good-till-date


class AssetType(Enum):
    """Type of financial asset."""

    STOCK = "stock"
    FUTURE = "future"
    OPTION = "option"
    CRYPTO = "crypto"
    FOREX = "forex"
    BOND = "bond"


class OptionType(Enum):
    """Type of option contract."""

    CALL = "call"
    PUT = "put"


class TickDirection(Enum):
    """Direction of a trade tick."""

    # The Taker was the Buyer (Price traded at Ask)
    BUY = "buy"

    # The Taker was the Seller (Price traded at Bid)
    SELL = "sell"

    # Unidentifiable (Auction crosses, Dark pool mid-points)
    NEUTRAL = "neutral"


class Resolution(IntEnum):
    """Time resolution of data."""

    TICK = 0
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAILY = 86400


class ColumnName(str, Enum):
    """CSV column names for market data types."""

    # Trade bar columns
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"

    # Trade tick columns
    PRICE = "price"
    SIZE = "size"

    # Quote tick columns
    BID_PRICE = "bid_price"
    BID_SIZE = "bid_size"
    ASK_PRICE = "ask_price"
    ASK_SIZE = "ask_size"

    # Quote bar columns
    BID_OPEN = "bid_open"
    BID_HIGH = "bid_high"
    BID_LOW = "bid_low"
    BID_CLOSE = "bid_close"
    ASK_OPEN = "ask_open"
    ASK_HIGH = "ask_high"
    ASK_LOW = "ask_low"
    ASK_CLOSE = "ask_close"
