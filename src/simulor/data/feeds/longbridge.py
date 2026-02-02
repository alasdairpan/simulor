"""Longbridge broker live data feed implementation.

This module provides real-time market data from Longbridge. Supports multiple
markets (US, HK, CN, SG) and various data types including quotes, trades,
order books, and candlestick data.

The feed uses a shared LongbridgeConnector to avoid duplicate connections
when used together with the Longbridge broker for trading.

Longbridge API Documentation: https://open.longportapp.com/docs/quote/overview

Requirements:
    pip install longport

Setup:
    1. Register for Longbridge OpenAPI account
    2. Set environment variables:
        - LONGPORT_APP_KEY
        - LONGPORT_APP_SECRET
        - LONGPORT_ACCESS_TOKEN
    3. Create broker and use broker.live_feed() to get the feed
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from simulor.core.events import EndOfStreamEvent, MarketEvent
from simulor.core.protocols import Feed
from simulor.data.feeds.live import DataType
from simulor.logging import get_logger
from simulor.types import AssetType, Instrument, MarketData, QuoteTick, Resolution, TickDirection, TradeBar, TradeTick

if TYPE_CHECKING:
    from longport.openapi import (
        AdjustType,
        Candlestick,
        Period,
        PushBrokers,
        PushDepth,
        PushQuote,
        PushTrades,
        TradeDirection,
    )

    from simulor.execution.live.connectors import LongbridgeConnector

# Import AdjustType at runtime for use in default parameter values
try:
    from longport.openapi import AdjustType
except ImportError:
    AdjustType = None  # type: ignore[assignment,misc]

logger = get_logger(__name__)

__all__ = ["LongbridgeLiveFeed", "LongbridgeCandlestickFeed"]


class LongbridgeLiveFeed(Feed):
    """Longbridge broker real-time data feed.

    Connects to Longbridge API to receive real-time market data for
    US, HK, CN, and SG markets. Supports tick data, quotes, order books,
    and candlestick bars.

    Uses a shared LongbridgeConnector to avoid duplicate connections when
    used together with the Longbridge broker.

    Example:
        >>> from simulor.types import Instrument
        >>> from simulor.execution.live.longbridge import LongbridgeConnector
        >>> from simulor.data.feeds import DataType
        >>> from longport.openapi import Config
        >>>
        >>> # Create shared connector
        >>> connector = LongbridgeConnector(Config.from_env())
        >>> connector.connect()
        >>>
        >>> # Create feed and broker using same connector
        >>> feed = LongbridgeLiveFeed(connector=connector)
        >>> broker = Longbridge(connector=connector, order_update_callback=...)
        >>>
        >>> # Subscribe to instruments
        >>> instruments = [Instrument.stock('700.HK'), Instrument.stock('AAPL.US')]
        >>> feed.subscribe(instruments, [DataType.QUOTE, DataType.TRADE])
        >>>
        >>> # Both use the same connection
        >>> feed.stream()
    """

    def __init__(
        self,
        connector: LongbridgeConnector,
    ):
        """Initialize Longbridge feed with shared connector.

        Args:
            connector: Shared LongbridgeConnector instance (also used by Longbridge broker)
        """
        super().__init__(connector=connector)
        self._subscriptions: dict[Instrument, set[DataType]] = {}
        self._stop_event = threading.Event()

        # Longbridge subscription type mapping
        self._sub_type_map: dict[DataType, type] = {}
        self._init_sub_type_map()

    @property
    def connector(self) -> LongbridgeConnector:
        """Get the typed Longbridge connector.

        Returns:
            LongbridgeConnector instance

        Raises:
            RuntimeError: If connector is None (should not happen)
        """
        if self._connector is None:
            raise RuntimeError("Connector not set")
        return self._connector  # type: ignore[return-value]

    def _init_sub_type_map(self) -> None:
        """Initialize subscription type mapping lazily."""
        try:
            from longport.openapi import SubType

            self._sub_type_map = {
                DataType.QUOTE: SubType.Quote,  # Real-time quote
                DataType.TRADE: SubType.Trade,  # Trade ticks
                DataType.DEPTH: SubType.Depth,  # Order book depth
                DataType.BROKER: SubType.Brokers,  # Broker queue
            }
        except ImportError:
            logger.warning("longport package not installed, subscription types unavailable")

    def connect(self) -> None:
        """Connect to Longport API via shared connector.

        Uses the shared connector's QuoteContext for market data subscriptions.

        Raises:
            RuntimeError: If connector is not initialized or connection fails
        """
        try:
            # Get quote context from shared connector (auto-initializes on first access)
            quote_ctx = self.connector.quote_context

            # Set up callbacks
            quote_ctx.set_on_quote(self._on_quote_callback)
            quote_ctx.set_on_depth(self._on_depth_callback)
            quote_ctx.set_on_trades(self._on_trades_callback)
            quote_ctx.set_on_brokers(self._on_brokers_callback)

            logger.info("LongbridgeLiveFeed connected via shared connector")

        except Exception as exc:
            raise RuntimeError(f"Failed to connect LongportFeed: {exc}") from exc

    def disconnect(self) -> None:
        """Disconnect from Longport API.

        Unsubscribes from all feeds. Connector cleanup happens automatically
        when no longer referenced.
        """
        try:
            # Unsubscribe all
            if self._subscriptions:
                instruments = list(self._subscriptions.keys())
                # Get all unique data types across all instruments
                all_data_types: set[DataType] = set()
                for data_types in self._subscriptions.values():
                    all_data_types.update(data_types)
                if all_data_types:
                    self.unsubscribe(instruments, list(all_data_types))

            logger.info("LongbridgeLiveFeed disconnected")

        except Exception as e:
            logger.warning(f"Error during LongportFeed disconnect: {e}")

    def subscribe(self, instruments: list[Instrument], data_types: list[DataType]) -> None:
        """Subscribe to Longbridge data feeds.

        Args:
            instruments: List of instruments to subscribe to
            data_types: List of DataType enum values
        """
        quote_ctx = self.connector.quote_context
        data_types_set = set(data_types)

        for instrument in instruments:
            symbol = self._to_longport_symbol(instrument)

            # Track subscriptions
            if instrument not in self._subscriptions:
                self._subscriptions[instrument] = set()
            self._subscriptions[instrument].update(data_types_set)

            for data_type in data_types_set:
                sub_type = self._sub_type_map.get(data_type)
                if not sub_type:
                    logger.warning(f"Unknown data type: {data_type}")
                    continue

                try:
                    quote_ctx.subscribe([symbol], [sub_type])
                    logger.info(f"Subscribed {symbol} to {data_type}")
                except Exception as e:
                    logger.error(f"Failed to subscribe {symbol} to {data_type}: {e}")

    def unsubscribe(self, instruments: list[Instrument], data_types: list[DataType]) -> None:
        """Unsubscribe from Longbridge data feeds.

        Args:
            instruments: List of instruments to unsubscribe from
            data_types: List of DataType enum values to unsubscribe
        """
        quote_ctx = self.connector.quote_context
        data_types_set = set(data_types)
        sub_types = [self._sub_type_map[dt] for dt in data_types_set if dt in self._sub_type_map]

        if not sub_types:
            return

        for instrument in instruments:
            symbol = self._to_longport_symbol(instrument)

            # Update tracked subscriptions
            if instrument in self._subscriptions:
                self._subscriptions[instrument] -= data_types_set
                if not self._subscriptions[instrument]:
                    del self._subscriptions[instrument]

            try:
                quote_ctx.unsubscribe([symbol], sub_types)
                logger.info(f"Unsubscribed {symbol} from {len(sub_types)} data types")
            except Exception as e:
                logger.warning(f"Error unsubscribing {symbol}: {e}")

    def _to_longport_symbol(self, instrument: Instrument) -> str:
        """Convert Simulor instrument to Longbridge symbol format.

        Format examples: 700.HK, AAPL.US, 600519.SH

        Args:
            instrument: Simulor instrument

        Returns:
            Longbridge-formatted security code
        """
        exchange_map = {
            "HKEX": "HK",
            "HK": "HK",
            "NYSE": "US",
            "NASDAQ": "US",
            "US": "US",
            "SSE": "SH",  # Shanghai Stock Exchange
            "SH": "SH",
            "SZSE": "SZ",  # Shenzhen Stock Exchange
            "SZ": "SZ",
            "SGX": "SG",  # Singapore Exchange
            "SG": "SG",
        }

        exchange = instrument.exchange or "US"
        region = exchange_map.get(exchange, exchange)
        return f"{instrument.symbol}.{region}"

    def _from_longport_symbol(self, symbol: str) -> Instrument:
        """Convert Longbridge symbol to Simulor instrument.

        Args:
            symbol: Longbridge security code (e.g., '700.HK')

        Returns:
            Simulor Instrument object
        """
        ticker, region = symbol.split(".")

        exchange_map = {
            "HK": "HKEX",
            "US": "NASDAQ",  # Default to NASDAQ for US stocks
            "SH": "SSE",
            "SZ": "SZSE",
            "SG": "SGX",
        }

        return Instrument(
            symbol=ticker,
            exchange=exchange_map.get(region, region),
            asset_type=AssetType.STOCK,
        )

    def publish_market_data(self, data: Sequence[MarketData], timestamp: datetime) -> None:
        """Publish market data as a MarketEvent.

        Args:
            data: Market data to publish (TradeTick, QuoteTick, TradeBar, QuoteBar)
        """
        event = MarketEvent(time=timestamp)
        for market_data in data:
            event.add(market_data)
        self.publish_event(event)

    def stream(self) -> None:
        """Stream live data from Longbridge.

        Connects to Longbridge and waits for stop signal.
        Callbacks run in background threads automatically.
        """
        if not self.is_connected():
            self.connect()

        # Wait for stop signal (callbacks run in background)
        self._stop_event.wait()

        # Cleanup
        self._cleanup()

    def stop(self) -> None:
        """Stop the feed gracefully."""
        logger.info("Received stop signal")
        self._stop_event.set()

    def is_running(self) -> bool:
        """Check if feed is currently running.

        Returns:
            True if running, False otherwise
        """
        return not self._stop_event.is_set()

    def _cleanup(self) -> None:
        """Disconnect and publish end event."""
        logger.info("Stopping Longbridge feed")
        self.disconnect()

        # Publish end of stream
        self.publish_event(
            EndOfStreamEvent(
                time=datetime.now(tz=ZoneInfo("UTC")),
                reason="Longbridge feed stopped",
            )
        )

    def _on_quote_callback(self, symbol: str, quote: PushQuote) -> None:
        """Handle real-time quote push from Longbridge.

        Args:
            symbol: Security symbol (e.g., '700.HK')
            quote: Quote data
        """
        # Currently, we do not publish quote updates as separate ticks.
        # Quote data is used in depth updates for best bid/ask.
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Received PushQuote for {symbol}: {quote}")

    # TODO: Introduce a proper order-book data type and publish it here.
    # - Define `BookLevel` and `OrderBook` dataclasses in `simulor.types.market_data`.
    # - Convert `depth.bids`/`depth.asks` into `BookLevel(price, size, orders?)` using
    #   `level.price` and `level.volume` (do NOT use `position`).
    # - Publish an `OrderBook` (multi-level) first, then a derived `QuoteTick`
    #   (top-of-book) for backward compatibility.
    # - Include sequence/timestamp from `depth` if provided to preserve ordering.
    def _on_depth_callback(self, symbol: str, depth: PushDepth) -> None:
        """Handle order book depth update from Longport.

        Args:
            symbol: Security symbol
            depth: Depth data
        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Received PushDepth for {symbol}: {depth}")

        try:
            instrument = self._from_longport_symbol(symbol)

            # Extract best bid/ask from depth
            if depth.asks and depth.bids:
                best_bid = depth.bids[0]  # First bid (highest price)
                best_ask = depth.asks[0]  # First ask (lowest price)

                timestamp = datetime.now(tz=ZoneInfo("UTC"))
                tick = QuoteTick(
                    timestamp=timestamp,
                    instrument=instrument,
                    resolution=Resolution.TICK,
                    bid_price=Decimal(str(best_bid.position)),
                    ask_price=Decimal(str(best_ask.position)),
                    bid_size=Decimal(str(best_bid.volume)),
                    ask_size=Decimal(str(best_ask.volume)),
                )

                self.publish_market_data(data=[tick], timestamp=timestamp)

        except Exception as e:
            logger.exception(f"Error processing depth for {symbol}: {e}")

    def _on_trades_callback(self, symbol: str, trades: PushTrades) -> None:
        """Handle real-time trade push from Longport.

        Args:
            symbol: Security symbol
            trades: Trade data from Longport (can be PushTrades or list[Trade])
        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Received PushTrades for {symbol}: {trades}")

        try:
            instrument = self._from_longport_symbol(symbol)
            tick_map: dict[datetime, list[TradeTick]] = {}

            for trade in trades.trades:
                tick = TradeTick(
                    timestamp=trade.timestamp,
                    instrument=instrument,
                    resolution=Resolution.TICK,
                    price=trade.price,
                    size=Decimal(trade.volume),
                    direction=self._parse_trade_direction(trade.direction),  # type: ignore[arg-type]
                )
                # Group ticks by timestamp
                tick_map.setdefault(trade.timestamp, []).append(tick)

            # Publish grouped ticks
            for timestamp, ticks in sorted(tick_map.items()):
                self.publish_market_data(data=ticks, timestamp=timestamp)

        except Exception as e:
            logger.exception(f"Error processing trades for {symbol}: {e}")

    def _on_brokers_callback(self, symbol: str, brokers: PushBrokers) -> None:
        """Handle broker queue update from Longport.

        Args:
            symbol: Security symbol
            brokers: Broker data
        """
        # Broker queue data could be used for additional analysis
        # Not implemented in this basic version
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Received PushBrokers for {symbol}: {brokers}")

    def _parse_trade_direction(self, trade_direction: TradeDirection) -> TickDirection:
        """Parse trade direction enum.

        Args:
            trade_direction: TradeDirection enum value
        Returns:
            TickDirection enum
        """
        if trade_direction == TradeDirection.Up:  # type: ignore[comparison-overlap]
            return TickDirection.BUY
        elif trade_direction == TradeDirection.Down:  # type: ignore[comparison-overlap]
            return TickDirection.SELL
        else:
            return TickDirection.NEUTRAL


class LongbridgeCandlestickFeed(Feed):
    """Longbridge historical candlestick data feed.

    Fetches historical OHLCV bars from Longbridge API for backtesting or
    near-real-time bar updates. Supports multiple instruments with chronological
    interleaving and configurable price adjustments.

    Two operating modes:
    1. **Historical Bulk Mode** (update_interval=None):
       Fetches all bars in date range, publishes chronologically, then completes.
       Use for backtesting.

    2. **Periodic Update Mode** (update_interval=timedelta):
       Fetches initial history, then periodically polls for new bars.
       Use for near-real-time bar-based strategies.

    Supports markets: US, HK, CN, SG
    Resolutions: MINUTE (1-min), HOUR (60-min), DAILY

    Rate Limits:
        - 60 requests per 30 seconds
        - Monthly quota varies by account level

    Historical Data Availability:
        - HK Stocks: Daily since 2004-06-01, Minute since 2022-09-28
        - US Stocks: Daily since 2010-06-01, Minute since 2023-12-04
        - A Shares: Daily since 1999-11-01, Minute since 2022-08-25

    Example (Historical Bulk):
        >>> from datetime import date
        >>> from simulor.types import Instrument, Resolution
        >>> from simulor.execution.live.longbridge import Longbridge
        >>> from longport.openapi import AdjustType, Config
        >>>
        >>> broker = Longbridge(config=Config.from_env())
        >>> broker.connect()
        >>>
        >>> instruments = [Instrument.stock('700', exchange='HK')]
        >>> feed = broker.candlestick_feed(
        ...     instruments=instruments,
        ...     resolution=Resolution.DAILY,
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31),
        ...     adjust_type=AdjustType.NoAdjust,
        ... )
        >>> feed.stream()  # Publishes all 2024 daily bars

    Example (Periodic Update):
        >>> from datetime import date, timedelta
        >>> from longport.openapi import AdjustType
        >>> feed = broker.candlestick_feed(
        ...     instruments=instruments,
        ...     resolution=Resolution.MINUTE,
        ...     start_date=date.today(),
        ...     end_date=None,  # Open-ended
        ...     update_interval=timedelta(minutes=1),  # Poll every minute
        ...     adjust_type=AdjustType.NoAdjust,
        ... )
        >>> feed.stream()  # Runs continuously until stop()

    Price Adjustment Types:
        - AdjustType.NoAdjust: Raw prices (actual)
        - AdjustType.ForwardAdjust: Adjust historical prices forward for splits/dividends
    """

    # Market timezone mapping
    _MARKET_TIMEZONES = {
        "HK": "Asia/Hong_Kong",
        "US": "America/New_York",
        "SH": "Asia/Shanghai",
        "SZ": "Asia/Shanghai",
        "SG": "Asia/Singapore",
    }

    def __init__(
        self,
        connector: LongbridgeConnector,
        instruments: list[Instrument],
        resolution: Resolution,
        start_date: date,
        end_date: date | None = None,
        adjust_type: AdjustType = AdjustType.NoAdjust,  # type: ignore[assignment]
        update_interval: timedelta | None = None,
    ):
        """Initialize Longbridge candlestick feed.

        Args:
            connector: Shared LongbridgeConnector instance
            instruments: List of instruments to fetch data for
            resolution: Bar resolution (MINUTE, HOUR, or DAILY)
            start_date: Start date for historical data
            end_date: End date for historical data (None = open-ended for periodic mode)
            adjust_type: Price adjustment type (AdjustType.NoAdjust or AdjustType.ForwardAdjust)
            update_interval: If set, enables periodic update mode (e.g., timedelta(minutes=1))

        Raises:
            ValueError: If resolution is unsupported or parameters are invalid
        """
        super().__init__(connector=connector)
        self._instruments = instruments
        self._resolution = resolution
        self._start_date = start_date
        self._end_date = end_date
        self._adjust_type = adjust_type
        self._update_interval = update_interval
        self._stop_event = threading.Event()
        self._fetched_until: datetime | None = None
        self._request_times: list[float] = []  # Track request timestamps for rate limiting

        # Validate resolution
        if resolution not in {Resolution.MINUTE, Resolution.HOUR, Resolution.DAILY}:
            raise ValueError(
                f"Unsupported resolution: {resolution}. LongbridgeCandlestickFeed supports MINUTE, HOUR, or DAILY only."
            )

        # Validate instruments
        if not instruments:
            raise ValueError("At least one instrument must be provided")

    @property
    def connector(self) -> LongbridgeConnector:
        """Get the typed Longbridge connector.

        Returns:
            LongbridgeConnector instance

        Raises:
            RuntimeError: If connector is None (should not happen)
        """
        if self._connector is None:
            raise RuntimeError("Connector not set")
        return self._connector  # type: ignore[return-value]

    def _resolution_to_period(self) -> Period:
        """Convert Simulor Resolution to Longbridge Period.

        Returns:
            Longbridge Period enum value

        Raises:
            ValueError: If resolution is unsupported
        """
        from longport.openapi import Period

        mapping = {
            Resolution.MINUTE: Period.Min_1,  # 1-minute bars
            Resolution.HOUR: Period.Min_60,  # 60-minute bars (closest to hourly)
            Resolution.DAILY: Period.Day,  # Daily bars
        }

        if self._resolution not in mapping:
            raise ValueError(f"Unsupported resolution: {self._resolution}")

        return mapping[self._resolution]  # type: ignore[return-value]

    def _convert_to_trade_bar(self, candlestick: Candlestick, instrument: Instrument) -> TradeBar:
        """Convert Longbridge Candlestick to Simulor TradeBar.

        Args:
            candlestick: Longbridge candlestick data
            instrument: Simulor instrument

        Returns:
            TradeBar with UTC timestamp and Decimal values
        """
        # Convert timestamp to UTC datetime
        # Longbridge Candlestick.timestamp is a datetime object, convert to UTC
        timestamp_utc = candlestick.timestamp.astimezone(ZoneInfo("UTC"))

        return TradeBar(
            timestamp=timestamp_utc,
            instrument=instrument,
            resolution=self._resolution,
            open=Decimal(str(candlestick.open)),
            high=Decimal(str(candlestick.high)),
            low=Decimal(str(candlestick.low)),
            close=Decimal(str(candlestick.close)),
            volume=Decimal(str(candlestick.volume)),
        )

    def _to_longport_symbol(self, instrument: Instrument) -> str:
        """Convert Simulor instrument to Longbridge symbol format.

        Format examples: 700.HK, AAPL.US, 600519.SH

        Args:
            instrument: Simulor instrument

        Returns:
            Longbridge-formatted security code
        """
        exchange_map = {
            "HKEX": "HK",
            "HK": "HK",
            "NYSE": "US",
            "NASDAQ": "US",
            "US": "US",
            "SSE": "SH",
            "SH": "SH",
            "SZSE": "SZ",
            "SZ": "SZ",
            "SGX": "SG",
            "SG": "SG",
        }

        exchange = instrument.exchange or "US"
        region = exchange_map.get(exchange, exchange)
        return f"{instrument.symbol}.{region}"

    def _respect_rate_limit(self) -> None:
        """Ensure we don't exceed 60 requests per 30 seconds.

        Sleeps if necessary to stay within rate limits.
        """
        now = time.time()
        # Remove timestamps older than 30 seconds
        self._request_times = [t for t in self._request_times if now - t < 30]

        # If we've made 60 requests in last 30 seconds, wait
        if len(self._request_times) >= 60:
            oldest = self._request_times[0]
            sleep_time = 30 - (now - oldest) + 0.5  # Add 0.5s buffer
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
                # Clear old timestamps after sleep
                now = time.time()
                self._request_times = [t for t in self._request_times if now - t < 30]

        # Record this request
        self._request_times.append(now)

    def _fetch_candlesticks_for_instrument(
        self,
        instrument: Instrument,
        start_date: date,
        end_date: date,
    ) -> list[TradeBar]:
        """Fetch candlesticks for a single instrument with pagination.

        Args:
            instrument: Instrument to fetch data for
            start_date: Start date
            end_date: End date

        Returns:
            List of TradeBar objects in chronological order
        """
        symbol = self._to_longport_symbol(instrument)
        period = self._resolution_to_period()
        quote_ctx = self.connector.quote_context
        all_bars: list[TradeBar] = []

        # Calculate expected bars to determine if pagination needed
        days_diff = (end_date - start_date).days + 1
        bars_per_day = {
            Resolution.MINUTE: 390,  # ~6.5 trading hours
            Resolution.HOUR: 7,  # ~6.5 hours
            Resolution.DAILY: 1,
        }
        expected_bars = days_diff * bars_per_day.get(self._resolution, 1)

        if expected_bars <= 1000:
            # Single request sufficient
            self._respect_rate_limit()
            logger.debug(f"Fetching {symbol} bars from {start_date} to {end_date}")

            try:
                candlesticks = quote_ctx.history_candlesticks_by_date(
                    symbol=symbol,
                    period=period,  # type: ignore[arg-type]
                    adjust_type=self._adjust_type, # type: ignore[arg-type]
                    start=start_date,
                    end=end_date,
                )

                for candle in candlesticks:
                    bar = self._convert_to_trade_bar(candle, instrument)
                    all_bars.append(bar)

            except Exception as e:
                logger.error(f"Failed to fetch candlesticks for {symbol}: {e}")
                raise

        else:
            # Pagination needed - split into chunks
            logger.info(f"Fetching {symbol}: estimated {expected_bars} bars, using pagination")
            chunk_days = 250  # ~250 days = ~1000 bars for daily
            current_start = start_date

            while current_start <= end_date:
                # Calculate chunk end date
                chunk_end = min(
                    date.fromordinal(current_start.toordinal() + chunk_days - 1),
                    end_date,
                )

                self._respect_rate_limit()
                logger.debug(f"Fetching chunk: {current_start} to {chunk_end}")

                try:
                    candlesticks = quote_ctx.history_candlesticks_by_date(
                        symbol=symbol,
                        period=period,  # type: ignore[arg-type]
                        adjust_type=self._adjust_type, # type: ignore[arg-type]
                        start=current_start,
                        end=chunk_end,
                    )

                    for candle in candlesticks:
                        bar = self._convert_to_trade_bar(candle, instrument)
                        all_bars.append(bar)

                except Exception as e:
                    logger.error(f"Failed to fetch chunk {current_start}-{chunk_end} for {symbol}: {e}")
                    # Continue with next chunk

                # Move to next chunk
                current_start = date.fromordinal(chunk_end.toordinal() + 1)

        # Sort chronologically (API may return in reverse order)
        all_bars.sort(key=lambda bar: bar.timestamp)

        logger.info(f"Fetched {len(all_bars)} bars for {symbol}")
        return all_bars

    def _merge_multi_instrument_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[MarketEvent]:
        """Fetch and merge data for multiple instruments chronologically.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of MarketEvent objects in chronological order
        """
        # Fetch bars for all instruments
        timestamp_to_bars: dict[datetime, list[TradeBar]] = {}

        for instrument in self._instruments:
            logger.info(f"Fetching candlesticks for {instrument.symbol}")
            try:
                bars = self._fetch_candlesticks_for_instrument(
                    instrument,
                    start_date,
                    end_date,
                )

                # Group by timestamp
                for bar in bars:
                    if bar.timestamp not in timestamp_to_bars:
                        timestamp_to_bars[bar.timestamp] = []
                    timestamp_to_bars[bar.timestamp].append(bar)

            except Exception as e:
                logger.error(f"Skipping {instrument.symbol} due to error: {e}")

        # Create MarketEvents in chronological order
        market_events: list[MarketEvent] = []
        for timestamp in sorted(timestamp_to_bars.keys()):
            event = MarketEvent(time=timestamp)
            for bar in timestamp_to_bars[timestamp]:
                event.add(bar)
            market_events.append(event)

        logger.info(
            f"Created {len(market_events)} market events from "
            f"{start_date} to {end_date} for {len(self._instruments)} instruments"
        )
        return market_events

    def stream(self) -> None:
        """Stream candlestick data.

        Behavior depends on update_interval:
        - None: Historical bulk mode (fetch all, publish, complete)
        - timedelta: Periodic update mode (fetch history + poll for updates)
        """
        if not self.is_connected():
            self.connect()

        try:
            if self._update_interval is None:
                # Historical bulk mode
                self._stream_historical_bulk()
            else:
                # Periodic update mode
                self._stream_periodic_updates()
        finally:
            self._cleanup()

    def _stream_historical_bulk(self) -> None:
        """Stream all historical data and complete."""
        logger.info(f"Starting historical bulk fetch: {self._start_date} to {self._end_date or 'now'}")

        # Determine end date
        end_date = self._end_date or date.today()

        # Fetch and merge data
        market_events = self._merge_multi_instrument_data(self._start_date, end_date)

        # Publish all events
        logger.info(f"Publishing {len(market_events)} market events")
        for event in market_events:
            if self._stop_event.is_set():
                logger.info("Stop requested, halting publication")
                break
            self.publish_event(event)

        logger.info("Historical bulk fetch complete")

    def _stream_periodic_updates(self) -> None:
        """Stream historical data then periodically poll for updates."""
        if self._update_interval is None:
            raise RuntimeError("update_interval must be set for periodic update mode")

        logger.info(f"Starting periodic update mode: {self._start_date}, update every {self._update_interval}")

        # Fetch initial historical data
        initial_end = date.today()
        market_events = self._merge_multi_instrument_data(self._start_date, initial_end)

        # Publish initial events
        logger.info(f"Publishing {len(market_events)} initial market events")
        for event in market_events:
            if self._stop_event.is_set():
                return
            self.publish_event(event)

        # Track last fetched timestamp
        if market_events:
            self._fetched_until = market_events[-1].time
        else:
            self._fetched_until = datetime.now(tz=ZoneInfo("UTC"))

        logger.info(f"Initial fetch complete, last bar at {self._fetched_until}")

        # Periodic update loop
        while not self._stop_event.is_set():
            # Check if we've reached end_date
            if self._end_date and date.today() > self._end_date:
                logger.info(f"Reached end date {self._end_date}, stopping")
                break

            # Wait for next update interval
            logger.debug(f"Sleeping for {self._update_interval}")
            if self._stop_event.wait(timeout=self._update_interval.total_seconds()):
                break  # Stop requested

            # Fetch new bars
            logger.info("Polling for new bars")
            try:
                new_events = self._fetch_new_bars()
                if new_events:
                    logger.info(f"Publishing {len(new_events)} new market events")
                    for event in new_events:
                        if self._stop_event.is_set():
                            return
                        self.publish_event(event)
                    # Update _fetched_until to the latest event timestamp
                    self._fetched_until = new_events[-1].time
                    logger.debug(f"Updated last fetched timestamp to {self._fetched_until}")
                else:
                    logger.debug("No new bars available")
            except Exception as e:
                logger.error(f"Error fetching new bars: {e}")

        logger.info("Periodic update mode stopped")

    def _fetch_new_bars(self) -> list[MarketEvent]:
        """Fetch bars newer than _fetched_until using offset-based query.

        Uses history_candlesticks_by_offset for efficient incremental fetching.

        Returns:
            List of new MarketEvent objects
        """
        if self._fetched_until is None:
            return []

        period = self._resolution_to_period()
        quote_ctx = self.connector.quote_context
        timestamp_to_bars: dict[datetime, list[TradeBar]] = {}

        # Fetch new bars for each instrument using offset method
        for instrument in self._instruments:
            symbol = self._to_longport_symbol(instrument)

            try:
                self._respect_rate_limit()

                # Fetch bars forward from last fetched timestamp
                # count=100 should be sufficient for most periodic update intervals
                candlesticks = quote_ctx.history_candlesticks_by_offset(
                    symbol=symbol,
                    period=period,  # type: ignore[arg-type]
                    adjust_type=self._adjust_type,  # type: ignore[arg-type]
                    forward=True,  # Get bars after the specified time
                    count=100,  # Fetch up to 100 new bars
                    time=self._fetched_until,  # Start from last fetched timestamp
                )

                # Convert and filter bars that are strictly newer than _fetched_until
                for candle in candlesticks:
                    bar = self._convert_to_trade_bar(candle, instrument)
                    # Only include bars with timestamps after _fetched_until to avoid duplicates
                    if bar.timestamp > self._fetched_until:
                        if bar.timestamp not in timestamp_to_bars:
                            timestamp_to_bars[bar.timestamp] = []
                        timestamp_to_bars[bar.timestamp].append(bar)

            except Exception as e:
                logger.error(f"Failed to fetch new bars for {symbol}: {e}")
                # Continue with other instruments

        # Create MarketEvents in chronological order
        market_events: list[MarketEvent] = []
        for timestamp in sorted(timestamp_to_bars.keys()):
            event = MarketEvent(time=timestamp)
            for bar in timestamp_to_bars[timestamp]:
                event.add(bar)
            market_events.append(event)

        return market_events

    def connect(self) -> None:
        """Connect to Longbridge API via shared connector.

        Uses connector's QuoteContext (auto-initializes on access).
        """
        try:
            # Access quote context to ensure it's initialized
            _ = self.connector.quote_context
            logger.info("LongbridgeCandlestickFeed connected via shared connector")
        except Exception as exc:
            raise RuntimeError(f"Failed to connect LongbridgeCandlestickFeed: {exc}") from exc

    def disconnect(self) -> None:
        """Disconnect from Longbridge API.

        No subscriptions to clean up (unlike live feed).
        """
        logger.info("LongbridgeCandlestickFeed disconnected")

    def stop(self) -> None:
        """Stop the feed gracefully."""
        logger.info("Received stop signal")
        self._stop_event.set()

    def is_running(self) -> bool:
        """Check if feed is currently running.

        Returns:
            True if running, False otherwise
        """
        return not self._stop_event.is_set()

    def _cleanup(self) -> None:
        """Disconnect and publish end event."""
        logger.info("Stopping Longbridge candlestick feed")
        self.disconnect()

        # Publish end of stream
        self.publish_event(
            EndOfStreamEvent(
                time=datetime.now(tz=ZoneInfo("UTC")),
                reason="Longbridge candlestick feed stopped",
            )
        )
