"""Broker connectors for live trading.

This module contains connector implementations that manage connections to
broker APIs. Connectors are designed to be shared between data feeds and
broker instances to avoid duplicate connections.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from simulor.core.connectors import Connector
from simulor.logging import get_logger
from simulor.types import Instrument

if TYPE_CHECKING:
    from longport.openapi import Config, QuoteContext, TradeContext

logger = get_logger(__name__)

__all__ = ["LongbridgeConnector", "instrument_to_longbridge_symbol", "longbridge_symbol_to_instrument"]


def instrument_to_longbridge_symbol(instrument: Instrument) -> str:
    """Convert a Simulor Instrument to a Longbridge symbol (e.g. ``700.HK``).

    Raises:
        ValueError: if the instrument has no exchange or the exchange is not supported.
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
    if not instrument.exchange:
        raise ValueError(f"Instrument {instrument.symbol!r} has no exchange set.")
    region = exchange_map.get(instrument.exchange)
    if region is None:
        raise ValueError(f"Unsupported exchange for Longbridge: {instrument.exchange!r}")
    return f"{instrument.symbol}.{region}"


def longbridge_symbol_to_instrument(symbol: str, currency: str = "USD") -> Instrument:
    """Convert a Longbridge symbol (e.g. ``700.HK``) to a Simulor Instrument.

    Raises:
        ValueError: if the symbol format is invalid or the region is not supported.
    """
    parts = symbol.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid Longbridge symbol format: {symbol!r}. Expected 'TICKER.REGION'.")
    ticker, region = parts
    exchange_map = {
        "HK": "HKEX",
        "US": "NASDAQ",
        "SH": "SSE",
        "SZ": "SZSE",
        "SG": "SGX",
    }
    exchange = exchange_map.get(region)
    if exchange is None:
        raise ValueError(f"Unsupported Longbridge region: {region!r} in symbol {symbol!r}")
    return Instrument.stock(
        symbol=ticker,
        exchange=exchange,
        currency=currency,
    )


class LongbridgeConnector(Connector):
    """Shared connector for Longbridge broker.

    Manages both QuoteContext (for market data) and TradeContext (for trading).
    This connector is designed to be shared between LongbridgeLiveFeed and Longbridge broker
    to avoid creating duplicate connections to the same broker API.

    Usage:
        >>> from longport.openapi import Config
        >>> # Share connector between feed and broker
        >>> connector = LongbridgeConnector(Config.from_env())
        >>> broker = Longbridge(connector=connector)
        >>> feed = broker.live_feed(instruments=[...])
        >>>
        >>> # Both use the same underlying connection
        >>> feed.start()
        >>> broker.submit_order(...)
    """

    def __init__(self, config: Config) -> None:
        """Initialize the connector with longport config.

        Args:
            config: Longport Config object (from longport.openapi package).
        """
        self._config: Config = config
        self._trade_context: TradeContext | None = None
        self._quote_context: QuoteContext | None = None

    @property
    def config(self) -> Config:
        """Return the longport config."""
        return self._config

    @property
    def trade_context(self) -> TradeContext:
        """Lazy-initialize and return the TradeContext.

        Automatically connects to Longbridge API on first access.

        Raises:
            RuntimeError: if the longport package is not installed or connection fails.
        """
        if self._trade_context is None:
            self._ensure_longport()
            from longport.openapi import TradeContext

            try:
                self._trade_context = TradeContext(self._config)
                logger.info("Longbridge TradeContext initialized")
            except Exception as exc:
                logger.error(f"Failed to initialize Longbridge TradeContext: {exc}")
                raise RuntimeError(f"Failed to connect to Longbridge: {exc}") from exc

        return self._trade_context

    @property
    def quote_context(self) -> QuoteContext:
        """Lazy-initialize and return the QuoteContext.

        Automatically connects to Longbridge API on first access.

        Raises:
            RuntimeError: if the longport package is not installed or connection fails.
        """
        if self._quote_context is None:
            self._ensure_longport()
            from longport.openapi import QuoteContext

            try:
                self._quote_context = QuoteContext(self._config)
                logger.info("Longbridge QuoteContext initialized")
            except Exception as exc:
                logger.error(f"Failed to initialize Longbridge QuoteContext: {exc}")
                raise RuntimeError(f"Failed to connect to Longbridge: {exc}") from exc

        return self._quote_context

    def _ensure_longport(self) -> None:
        """Ensure the longport.openapi package can be imported.

        Raises:
            RuntimeError: if the longport package is not installed.
        """
        try:
            _ = importlib.import_module("longport.openapi")
        except ImportError as exc:
            raise RuntimeError("longport package is not installed. Install with: pip install longport") from exc

    def connect(self) -> None:
        """Explicitly initialize both contexts.

        This allows users to establish the connection upfront and validate
        credentials before proceeding. Connection also happens automatically
        on first property access if this method is not called.

        Raises:
            RuntimeError: if the longport package is not installed or connection fails.
        """
        # Access both properties to trigger lazy initialization
        _ = self.trade_context
        _ = self.quote_context

    def disconnect(self) -> None:
        """No-op, cleanup happens automatically via garbage collection."""
        pass

    def is_connected(self) -> bool:
        """Check if contexts have been initialized.

        Returns:
            True if either context exists, False otherwise.
        """
        return self._trade_context is not None or self._quote_context is not None
