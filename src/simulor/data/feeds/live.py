"""Data type definitions for live broker data feeds.

This module provides common enums and types used by live broker feeds.
"""

from enum import Enum

__all__ = ["DataType"]


class DataType(Enum):
    """Data subscription types."""

    QUOTE = "quote"      # Real-time best bid/ask (QuoteTick)
    TRADE = "trade"      # Trade executions (TradeTick)
    DEPTH = "depth"      # Order book depth (Level 2)
    BROKER = "broker"    # Broker queue
    BAR_1M = "bar_1m"    # 1-minute bars (Resolution.MINUTE)
    BAR_1H = "bar_1h"    # 1-hour bars (Resolution.HOUR)
    BAR_DAY = "bar_day"  # Daily bars (Resolution.DAILY)


