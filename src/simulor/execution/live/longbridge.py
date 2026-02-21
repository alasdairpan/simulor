"""Longbridge broker integration for Simulor.

This module provides the Longbridge broker implementation for order execution.
The broker uses a shared connector to avoid duplicate connections when used
together with LongbridgeLiveFeed and LongbridgeCandlestickFeed.

Architecture:
    LongbridgeConnector (shared, from connectors.py)
        ├── QuoteContext (market data)
        └── TradeContext (order execution)
                ↓                    ↓                           ↓
          LongbridgeLiveFeed    LongbridgeCandlestickFeed   Longbridge (Broker)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from simulor.core.assets import AccountBalance, CashInfo, RiskLevel, StockPosition
from simulor.core.connectors import Broker, SubmitOrderResult
from simulor.data.feeds import DataType
from simulor.execution.live.connectors import LongbridgeConnector
from simulor.execution.live.symbols import instrument_to_longbridge_symbol, longbridge_symbol_to_instrument
from simulor.logging import get_logger
from simulor.types import Instrument, OrderSpec, Resolution
from simulor.types import OrderSide as SimulorOrderSide
from simulor.types import OrderType as SimulorOrderType
from simulor.types import TimeInForce as SimulorTimeInForce

# Import longport types - required for this module
try:
    from longport.openapi import AdjustType, Config
    from longport.openapi import OrderSide as LongportOrderSide
    from longport.openapi import OrderType as LongportOrderType
    from longport.openapi import TimeInForceType as LongportTimeInForce
except ImportError as e:
    raise ImportError(
        "Longbridge integration requires the 'longport' package. Install it with: pip install 'simulor[longport]'"
    ) from e

if TYPE_CHECKING:
    from simulor.data.feeds.longbridge import LongbridgeCandlestickFeed, LongbridgeLiveFeed

logger = get_logger(__name__)

__all__ = ["Longbridge"]


class Longbridge(Broker):
    """Broker implementation for Longbridge.

    Translates Simulor OrderSpec objects to Longbridge API calls and exposes
    submit_order and cancel_order functionality.

    The broker uses a shared LongbridgeConnector internally.

    Example:
        >>> from longport.openapi import Config
        >>> from datetime import date
        >>> # Create broker (connector is created internally)
        >>> broker = Longbridge(config=Config.from_env())
        >>> broker.connect()
        >>>
        >>> # Create live tick feed using broker's connector
        >>> live_feed = broker.live_feed(instruments=[...], data_types=[...])
        >>>
        >>> # Create candlestick feed using broker's connector
        >>> candlestick_feed = broker.candlestick_feed(
        ...     instruments=[...],
        ...     resolution=Resolution.DAILY,
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31),
        ... )
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
            symbol=instrument_to_longbridge_symbol(order_spec.instrument),
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

    def get_account_balance(self) -> AccountBalance:
        """Fetch account balance from the Longbridge API.

        Calls /v1/asset/account and maps the first returned AccountBalance
        entry to Simulor's AccountBalance model.

        Returns:
            AccountBalance snapshot for the primary account.

        Raises:
            RuntimeError: If the broker is not connected or the API call fails.
        """
        resp = self._connector.trade_context.account_balance()
        if not resp:
            raise RuntimeError("No account balance returned from Longbridge API.")
        lb = resp[0]  # Primary account

        cash_infos = tuple(
            CashInfo(
                currency=cash_info.currency,
                available_cash=cash_info.available_cash,
                frozen_cash=cash_info.frozen_cash,
                settling_cash=cash_info.settling_cash,
                withdrawable_cash=cash_info.withdraw_cash,
            )
            for cash_info in (lb.cash_infos or [])
        )

        return AccountBalance(
            currency=lb.currency,
            net_assets=lb.net_assets,
            total_cash=lb.total_cash,
            buying_power=lb.buy_power,
            init_margin=lb.init_margin,
            maintenance_margin=lb.maintenance_margin,
            margin_call=lb.margin_call,
            risk_level=RiskLevel(lb.risk_level),
            cash_infos=cash_infos,
        )

    def get_stock_positions(self, instruments: list[Instrument] | None = None) -> list[StockPosition]:
        """Fetch stock positions from the Longbridge API.

        Calls /v1/asset/stock. When ``instruments`` is provided, only those
        symbols are queried.

        Args:
            instruments: Optional filter; when provided, only positions for
                the specified instruments are returned.

        Returns:
            List of StockPosition snapshots.
            ``current_price`` is always ``None`` — the stock positions endpoint
            does not include live pricing; use a quote feed for market prices.

        Raises:
            RuntimeError: If the broker is not connected or the API call fails.
        """
        symbols: list[str] | None = None
        if instruments is not None:
            symbols = [instrument_to_longbridge_symbol(i) for i in instruments]

        resp = self._connector.trade_context.stock_positions(symbols=symbols)
        if not resp.channels:
            return []

        positions = []
        for channel in resp.channels:
            for item in channel.positions:
                instrument = longbridge_symbol_to_instrument(item.symbol, currency=item.currency)
                positions.append(
                    StockPosition(
                        instrument=instrument,
                        currency=item.currency,
                        quantity=item.quantity,
                        # available_quantity can be negative in Longbridge when
                        # shares are sold but settlement has not yet completed.
                        available_quantity=item.available_quantity,
                        cost_price=item.cost_price,
                        current_price=None,  # Not provided by this endpoint
                    )
                )
        return positions

    def live_feed(
        self,
        instruments: list[Instrument],
        data_types: list[DataType],
    ) -> LongbridgeLiveFeed:
        """Create a LongbridgeLiveFeed using the shared connector.

        Args:
            instruments: List of instruments to subscribe to
            data_types: List of DataType enum values to subscribe

        Returns:
            LongbridgeLiveFeed instance using this broker's connector.
        """
        # Import here to avoid circular dependency
        from simulor.data.feeds.longbridge import LongbridgeLiveFeed

        # Create feed
        feed = LongbridgeLiveFeed(connector=self._connector)

        # Subscribe to instruments
        feed.subscribe(instruments, data_types)

        return feed

    def candlestick_feed(
        self,
        instruments: list[Instrument],
        resolution: Resolution,
        start_date: date,
        end_date: date | None = None,
        adjust_type: type[AdjustType] = AdjustType.NoAdjust,
        update_interval: timedelta | None = None,
    ) -> LongbridgeCandlestickFeed:
        """Create a LongbridgeCandlestickFeed using the shared connector.

        Args:
            instruments: List of instruments to fetch data for
            resolution: Bar resolution (MINUTE, HOUR, or DAILY)
            start_date: Start date for historical data
            end_date: End date for historical data (None = open-ended for periodic mode)
            adjust_type: Price adjustment type (AdjustType.NoAdjust or AdjustType.ForwardAdjust)
            update_interval: If set, enables periodic update mode (e.g., timedelta(minutes=1))

        Returns:
            LongbridgeCandlestickFeed instance using this broker's connector.

        Example (Historical Bulk):
            >>> from datetime import date
            >>> from longport.openapi import AdjustType
            >>> feed = broker.candlestick_feed(
            ...     instruments=[Instrument.stock('700', exchange='HK')],
            ...     resolution=Resolution.DAILY,
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 12, 31),
            ...     adjust_type=AdjustType.NoAdjust,
            ... )

        Example (Periodic Updates):
            >>> from datetime import date, timedelta
            >>> from longport.openapi import AdjustType
            >>> feed = broker.candlestick_feed(
            ...     instruments=[Instrument.stock('700', exchange='HK')],
            ...     resolution=Resolution.MINUTE,
            ...     start_date=date.today(),
            ...     update_interval=timedelta(minutes=1),
            ...     adjust_type=AdjustType.NoAdjust,
            ... )
        """
        # Import here to avoid circular dependency
        from simulor.data.feeds.longbridge import LongbridgeCandlestickFeed

        # Create and return feed
        return LongbridgeCandlestickFeed(
            connector=self._connector,
            instruments=instruments,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust_type,  # type: ignore[arg-type]
            update_interval=update_interval,
        )
