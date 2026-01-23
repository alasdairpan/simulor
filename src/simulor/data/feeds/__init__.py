"""Live broker data feeds.

This package provides real-time market data feeds from various broker APIs.
All feeds implement the unified Feed protocol, ensuring seamless switching
between backtesting (historical data) and live trading modes.

Architecture:
    The feeds use shared connectors to avoid duplicate connections when
    used together with brokers. For example, LongbridgeFeed and Longbridge broker
    share the same LongbridgeConnector instance.

Available Feeds:
    - LongbridgeFeed: Longbridge real-time data feed

Usage Example:
    >>> from simulor.data.feeds import DataType
    >>> from simulor.execution.live import Longbridge
    >>> from simulor.types import Instrument
    >>> from longport.openapi import Config
    >>>
    >>> # Create broker (connector is created internally)
    >>> broker = Longbridge(config=Config.from_env())
    >>>
    >>> # Subscribe to instruments
    >>> instruments = [Instrument.stock('700', exchange='HK')]
    >>> feed = broker.live_feed(instruments, [DataType.QUOTE, DataType.TRADE])
    >>>
    >>> # Use in engine
    >>> from simulor.engine import Engine
    >>> engine = Engine(data=feed, fund=fund, broker=broker)
    >>> result = engine.run(mode='live')
"""

from simulor.data.feeds.live import DataType
from simulor.data.feeds.longbridge import LongbridgeFeed

__all__ = [
    "LongbridgeFeed",
    "DataType",
]
