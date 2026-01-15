"""Longport integration for Simulor.

This module provides a `LongportConnector` that lazily initializes the
`longport.openapi` client contexts and a `Longport` broker that adapts
Simulor order specifications to Longport's API. The implementation keeps
connections lightweight and raises clear errors when the `longport` package
is not available or when methods are called while disconnected.

Note: the `longport` package is only imported at runtime and only when
`connect()` is invoked to allow the rest of Simulor to be imported without
requiring Longport to be installed.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from simulor.core.connectors import Broker, Connector, SubmitOrderResult
from simulor.types import OrderSide as SimulorOrderSide
from simulor.types import OrderSpec
from simulor.types import OrderType as SimulorOrderType
from simulor.types import TimeInForce as SimulorTimeInForce

if TYPE_CHECKING:
    from longport.openapi import Config, PushOrderChanged, QuoteContext, TradeContext
    from longport.openapi import OrderSide as LongportOrderSide
    from longport.openapi import OrderType as LongportOrderType
    from longport.openapi import TimeInForceType as LongportTimeInForce


class LongportConnector(Connector):
    """Connector for the Longport exchange.

    Responsibilities:
    - Lazy import and validation of the `longport.openapi` package.
    - Creation and exposure of `TradeContext` and `QuoteContext` instances.
    - Simple connected state tracking.
    """

    def __init__(self) -> None:
        self._config: Config | None = None
        self._trade_context: TradeContext | None = None
        self._quote_context: QuoteContext | None = None
        self._connected = False

    @property
    def trade_context(self) -> TradeContext:
        """Return the initialized `TradeContext`.

        Raises:
            RuntimeError: if the trade context has not been initialized.
        """
        if not self._trade_context:
            raise RuntimeError("Longport TradeContext is not initialized.")
        return self._trade_context

    @property
    def quote_context(self) -> QuoteContext:
        """Return the initialized `QuoteContext`.

        Raises:
            RuntimeError: if the quote context has not been initialized.
        """
        if not self._quote_context:
            raise RuntimeError("Longport QuoteContext is not initialized.")
        return self._quote_context

    def _ensure_longport(self) -> None:
        """Ensure the `longport.openapi` package can be imported.

        Raises:
            RuntimeError: if the `longport` package is not installed.
        """
        try:
            _ = importlib.import_module("longport.openapi")
        except ImportError as exc:
            raise RuntimeError("longport package is not installed.") from exc

    def connect(self) -> None:
        """Initialize the Longport API contexts and mark connector connected.

        This will import `longport.openapi`, create `Config` from environment
        if needed, and initialize `TradeContext` and `QuoteContext`.
        """
        self._ensure_longport()

        from longport.openapi import Config, QuoteContext, TradeContext

        self._config = self._config or Config.from_env()
        self._trade_context = self._trade_context or TradeContext(self._config)
        self._quote_context = self._quote_context or QuoteContext(self._config)

        self._connected = True

    def disconnect(self) -> None:
        """Mark the connector as disconnected.

        Note: this implementation only updates local state; underlying
        longport client cleanup is handled by the library if necessary.
        """
        self._connected = False

    def is_connected(self) -> bool:
        """Return whether the connector is currently connected."""
        return self._connected


class Longport(Broker):
    """Broker implementation using Longport's API.

    Translates Simulor `OrderSpec` objects to Longport API calls and exposes
    `submit_order`, `cancel_order`, and an order update registration hook.
    """

    def __init__(self, order_update_callback: Callable[[PushOrderChanged], None]) -> None:
        super().__init__()
        self._connector = LongportConnector()
        self._on_order_update = order_update_callback

    def connect(self) -> None:
        self._connector.connect()

    def disconnect(self) -> None:
        self._connector.disconnect()

    def is_connected(self) -> bool:
        return self._connector.is_connected()

    def _to_longport_order_type(self, order_type: SimulorOrderType) -> type[LongportOrderType]:
        """Map Simulor `OrderType` to Longport's `OrderType`.

        Raises:
            ValueError: if the given `order_type` has no Longport mapping.
        """
        from longport.openapi import OrderType as LongportOrderType

        mapping = {
            SimulorOrderType.MARKET: LongportOrderType.MO,
            SimulorOrderType.LIMIT: LongportOrderType.LO,
            SimulorOrderType.MARKET_IF_TOUCHED: LongportOrderType.MIT,
            SimulorOrderType.LIMIT_IF_TOUCHED: LongportOrderType.LIT,
            # Unsupported order types mapped to Unknown
            # SimulorOrderType.STOP: LongportOrderType.Unknown,
            # SimulorOrderType.STOP_LIMIT: LongportOrderType.Unknown,
            # SimulorOrderType.TRAILING_STOP: LongportOrderType.Unknown,
            # SimulorOrderType.TRAILING_STOP_LIMIT: LongportOrderType.Unknown,
        }
        try:
            return mapping[order_type]  # type: ignore[no-any-return]
        except KeyError as e:
            raise ValueError(f"Unsupported order type for Longport: {order_type}") from e

    def _to_longport_order_side(self, order_side: SimulorOrderSide) -> type[LongportOrderSide]:
        """Map Simulor `OrderSide` to Longport's `OrderSide`.

        Raises:
            ValueError: if the given `order_side` has no Longport mapping.
        """
        from longport.openapi import OrderSide as LongportOrderSide

        mapping = {
            SimulorOrderSide.BUY: LongportOrderSide.Buy,
            SimulorOrderSide.SELL: LongportOrderSide.Sell,
        }
        try:
            return mapping[order_side]  # type: ignore[no-any-return]
        except KeyError as e:
            raise ValueError(f"Unsupported order side for Longport: {order_side}") from e

    def _to_longport_time_in_force(self, time_in_force: SimulorTimeInForce) -> type[LongportTimeInForce]:
        """Map Simulor `TimeInForce` to Longport's `TimeInForceType`.

        Raises:
            ValueError: if the given `time_in_force` has no Longport mapping.
        """
        from longport.openapi import TimeInForceType as LongportTimeInForce

        mapping = {
            SimulorTimeInForce.GTC: LongportTimeInForce.GoodTilCanceled,
            SimulorTimeInForce.DAY: LongportTimeInForce.Day,
            SimulorTimeInForce.GTD: LongportTimeInForce.GoodTilDate,
            # Unsupported time in force mapped to Unknown
            # SimulorTimeInForce.IOC: LongportTimeInForce.Unknown,
            # SimulorTimeInForce.FOK: LongportTimeInForce.Unknown,
        }
        try:
            return mapping[time_in_force]  # type: ignore[no-any-return]
        except KeyError as e:
            raise ValueError(f"Unsupported time in force for Longport: {time_in_force}") from e

    def _ensure_connected(self) -> None:
        """Raise if the underlying connector is not connected."""
        if not self.is_connected():
            raise RuntimeError("Longport connector is not connected.")

    def submit_order(self, strategy_name: str, order_spec: OrderSpec) -> SubmitOrderResult:  # noqa: ARG002
        """Submit an `OrderSpec` to Longport and return the resulting order id."""
        self._ensure_connected()

        resp = self._connector.trade_context.submit_order(
            symbol=f"{order_spec.instrument.symbol}.{order_spec.instrument.exchange}",
            order_type=self._to_longport_order_type(order_spec.order_type),
            side=self._to_longport_order_side(order_spec.side),
            submitted_quantity=order_spec.quantity,
            time_in_force=self._to_longport_time_in_force(order_spec.time_in_force),
            submitted_price=order_spec.limit_price,
            trigger_price=order_spec.stop_price,
        )

        return SubmitOrderResult(order_id=resp.order_id)

    def cancel_order(self, strategy_name: str, order_id: str) -> None:  # noqa: ARG002
        """Cancel an existing order by its Longport `order_id`."""
        self._ensure_connected()
        self._connector.trade_context.cancel_order(order_id=order_id)

    def register_order_update_callback(self) -> None:
        """Register a callback to receive order update events from Longport."""
        self._ensure_connected()
        self._connector.trade_context.set_on_order_changed(self._on_order_update)
