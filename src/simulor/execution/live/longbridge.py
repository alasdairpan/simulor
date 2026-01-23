"""Longbridge broker integration for Simulor.

This module provides the Longbridge broker implementation for order execution.
The broker uses a shared connector to avoid duplicate connections when used
together with LongbridgeFeed.

Architecture:
    LongbridgeConnector (shared, from connectors.py)
        ├── QuoteContext (market data)
        └── TradeContext (order execution)
                ↓                    ↓
          LongbridgeFeed       Longbridge (Broker)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulor.core.connectors import Broker, SubmitOrderResult
from simulor.data.feeds import DataType
from simulor.execution.live.connectors import LongbridgeConnector
from simulor.logging import get_logger
from simulor.types import Instrument, OrderSpec
from simulor.types import OrderSide as SimulorOrderSide
from simulor.types import OrderType as SimulorOrderType
from simulor.types import TimeInForce as SimulorTimeInForce

if TYPE_CHECKING:
    from longport.openapi import Config
    from longport.openapi import OrderSide as LongportOrderSide
    from longport.openapi import OrderType as LongportOrderType
    from longport.openapi import TimeInForceType as LongportTimeInForce

    from simulor.data.feeds.longbridge import LongbridgeFeed

logger = get_logger(__name__)

__all__ = ["Longbridge"]


class Longbridge(Broker):
    """Broker implementation for Longbridge.

    Translates Simulor OrderSpec objects to Longbridge API calls and exposes
    submit_order and cancel_order functionality.

    The broker uses a shared LongbridgeConnector internally.

    Example:
        >>> from longport.openapi import Config
        >>> # Create broker (connector is created internally)
        >>> broker = Longbridge(config=Config.from_env())
        >>> broker.connect()
        >>>
        >>> # Create feed using broker's connector
        >>> feed = broker.live_feed(instruments=[...], data_types=[...])
    """

    def __init__(self, config: Config) -> None:
        """Initialize Longbridge broker.

        Args:
            config: Longport Config object
        """
        super().__init__()
        self._connector = LongbridgeConnector(config)

    def connect(self) -> None:
        """Explicitly initialize the connector.

        This allows users to establish the connection upfront and validate
        credentials before proceeding. Connection also happens automatically
        when methods are called if this is not invoked.

        Raises:
            RuntimeError: if the longport package is not installed or connection fails.
        """
        self._connector.connect()

    def disconnect(self) -> None:
        """No-op, cleanup happens automatically via garbage collection."""
        pass

    def is_connected(self) -> bool:
        """Check if the connector has initialized contexts.

        Returns:
            True if connector is initialized, False otherwise.
        """
        return self._connector.is_connected()

    def _to_longport_order_type(self, order_type: SimulorOrderType) -> LongportOrderType:
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
            return mapping[order_type]  # type: ignore[return-value]
        except KeyError as e:
            raise ValueError(f"Unsupported order type for Longport: {order_type}") from e

    def _to_longport_order_side(self, order_side: SimulorOrderSide) -> LongportOrderSide:
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
            return mapping[order_side]  # type: ignore[return-value]
        except KeyError as e:
            raise ValueError(f"Unsupported order side for Longport: {order_side}") from e

    def _to_longport_time_in_force(self, time_in_force: SimulorTimeInForce) -> LongportTimeInForce:
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
            return mapping[time_in_force]  # type: ignore[return-value]
        except KeyError as e:
            raise ValueError(f"Unsupported time in force for Longport: {time_in_force}") from e

    def submit_order(self, strategy_name: str, order_spec: OrderSpec) -> SubmitOrderResult:  # noqa: ARG002
        """Submit an `OrderSpec` to Longport and return the resulting order id."""
        resp = self._connector.trade_context.submit_order(
            symbol=f"{order_spec.instrument.symbol}.{order_spec.instrument.exchange}",
            order_type=self._to_longport_order_type(order_spec.order_type),  # type: ignore[arg-type]
            side=self._to_longport_order_side(order_spec.side),  # type: ignore[arg-type]
            submitted_quantity=order_spec.quantity,
            time_in_force=self._to_longport_time_in_force(order_spec.time_in_force),  # type: ignore[arg-type]
            submitted_price=order_spec.limit_price,
            trigger_price=order_spec.stop_price,
        )

        return SubmitOrderResult(order_id=resp.order_id)

    def cancel_order(self, strategy_name: str, order_id: str) -> None:  # noqa: ARG002
        """Cancel an existing order by its Longport `order_id`."""
        self._connector.trade_context.cancel_order(order_id=order_id)

    def live_feed(
        self,
        instruments: list[Instrument],
        data_types: list[DataType],
    ) -> LongbridgeFeed:
        """Create a LongbridgeFeed using the shared connector.

        Args:
            instruments: List of instruments to subscribe to
            data_types: List of DataType enum values to subscribe

        Returns:
            LongbridgeFeed instance using this broker's connector.
        """
        # Create feed
        feed = LongbridgeFeed(connector=self._connector)

        # Subscribe to instruments
        feed.subscribe(instruments, data_types)

        return feed
