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

import threading
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from simulor.core.events import EndOfStreamEvent, MarketEvent
from simulor.core.protocols import Feed
from simulor.data.feeds.live import DataType
from simulor.logging import get_logger
from simulor.types import AssetType, Instrument, MarketData, QuoteTick, Resolution, TickDirection, TradeTick

if TYPE_CHECKING:
    from longport.openapi import PushBrokers, PushDepth, PushQuote, PushTrades, TradeDirection

    from simulor.execution.live.connectors import LongbridgeConnector

logger = get_logger(__name__)

__all__ = ["LongbridgeFeed"]


class LongbridgeFeed(Feed):
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
        >>> feed = LongbridgeFeed(connector=connector)
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

            logger.info("LongbridgeFeed connected via shared connector")

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

            logger.info("LongbridgeFeed disconnected")

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
                    # Subscribe with initial push to get current state
                    quote_ctx.subscribe([symbol], [sub_type])
                    logger.info(f"Subscribed {symbol} to {data_type}")
                except TypeError:
                    # Fallback if is_first_push parameter is not supported
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

    def publish_market_data(self, data: MarketData) -> None:
        """Publish market data as a MarketEvent.

        Args:
            data: Market data to publish (TradeTick, QuoteTick, TradeBar, QuoteBar)
        """
        event = MarketEvent(time=data.timestamp)
        event.add(data)
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
        try:
            instrument = self._from_longport_symbol(symbol)

            # Get timestamp from quote
            ts = quote.timestamp

            # Skip publishing if we don't have proper bid/ask data
            # PushQuote from longport doesn't always have bid/ask prices
            # We need depth data for accurate bid/ask quotes
            # Only publish if quote has valid bid/ask attributes
            if not hasattr(quote, 'bid_price') or not hasattr(quote, 'ask_price'):
                logger.debug(f"Skipping quote for {symbol}: no bid/ask data available")
                return

            if quote.bid_price is None or quote.ask_price is None:
                logger.debug(f"Skipping quote for {symbol}: bid/ask prices are None")
                return

            tick = QuoteTick(
                timestamp=ts,
                instrument=instrument,
                resolution=Resolution.TICK,
                bid_price=Decimal(str(quote.bid_price)),
                ask_price=Decimal(str(quote.ask_price)),
                bid_size=Decimal(str(quote.bid_size)) if hasattr(quote, 'bid_size') and quote.bid_size else Decimal('0'),
                ask_size=Decimal(str(quote.ask_size)) if hasattr(quote, 'ask_size') and quote.ask_size else Decimal('0'),
            )

            self.publish_market_data(tick)

        except Exception as e:
            logger.exception(f"Error processing quote for {symbol}: {e}")

    def _on_depth_callback(self, symbol: str, depth: PushDepth) -> None:
        """Handle order book depth update from Longport.

        Args:
            symbol: Security symbol
            depth: Depth data
        """
        try:
            instrument = self._from_longport_symbol(symbol)

            # Extract best bid/ask from depth
            if depth.asks and depth.bids:
                best_bid = depth.bids[0]  # First bid (highest price)
                best_ask = depth.asks[0]  # First ask (lowest price)

                tick = QuoteTick(
                    timestamp=datetime.now(tz=ZoneInfo("UTC")),
                    instrument=instrument,
                    resolution=Resolution.TICK,
                    bid_price=Decimal(str(best_bid.position)),
                    ask_price=Decimal(str(best_ask.position)),
                    bid_size=Decimal(str(best_bid.volume)),
                    ask_size=Decimal(str(best_ask.volume)),
                )

                self.publish_market_data(tick)

        except Exception as e:
            logger.exception(f"Error processing depth for {symbol}: {e}")

    def _on_trades_callback(self, symbol: str, trades: PushTrades) -> None:
        """Handle real-time trade push from Longport.

        Args:
            symbol: Security symbol
            trades: Trade data from Longport (can be PushTrades or list[Trade])
        """
        try:
            instrument = self._from_longport_symbol(symbol)

            for trade in trades.trades:
                tick = TradeTick(
                    timestamp=trade.timestamp,
                    instrument=instrument,
                    resolution=Resolution.TICK,
                    price=trade.price,
                    size=Decimal(trade.volume),
                    direction=self._parse_trade_direction(trade.direction),  # type: ignore[arg-type]
                )

                self.publish_market_data(tick)

        except Exception as e:
            logger.exception(f"Error processing trades for {symbol}: {e}")

    def _on_brokers_callback(self, symbol: str, _brokers: PushBrokers) -> None:
        """Handle broker queue update from Longport.

        Args:
            symbol: Security symbol
            _brokers: Broker data (unused in base implementation)
        """
        # Broker queue data could be used for additional analysis
        # Not implemented in this basic version
        logger.debug(f"Received broker data for {symbol}")

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
