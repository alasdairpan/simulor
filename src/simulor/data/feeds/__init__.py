"""Live broker data feeds.

This package provides real-time market data feeds from various broker APIs.
All feeds implement the unified Feed protocol, ensuring seamless switching
between backtesting (historical data) and live trading modes.

Architecture:
    The feeds use shared connectors to avoid duplicate connections when
    used together with brokers. For example, LongbridgeLiveFeed and
    LongbridgeCandlestickFeed share the same LongbridgeConnector instance
    with the Longbridge broker.

Available Feeds:
    - LongbridgeLiveFeed: Longbridge real-time tick data feed (quotes, trades, depth)
    - LongbridgeCandlestickFeed: Longbridge historical/near-real-time candlestick feed

Usage Example (Live Tick Feed):
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

Usage Example (Candlestick Feed):
    >>> from datetime import date
    >>> from simulor.types import Resolution
    >>> from longport.openapi import AdjustType
    >>>
    >>> # Create candlestick feed for historical data
    >>> feed = broker.candlestick_feed(
    ...     instruments=instruments,
    ...     resolution=Resolution.DAILY,
    ...     start_date=date(2024, 1, 1),
    ...     end_date=date(2024, 12, 31),
    ...     adjust_type=AdjustType.NoAdjust,
    ... )
    >>> engine = Engine(data=feed, fund=fund, broker=broker)
    >>> result = engine.run(mode='backtest')
"""

from simulor.data.feeds.live import DataType
from simulor.data.feeds.longbridge import LongbridgeCandlestickFeed, LongbridgeLiveFeed

__all__ = [
    "LongbridgeLiveFeed",
    "LongbridgeCandlestickFeed",
    "DataType",
]
