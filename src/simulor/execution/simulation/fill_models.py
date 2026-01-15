"""Fill model implementations for order execution simulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

from simulor.types import Instrument, OrderSide, OrderType

if TYPE_CHECKING:
    from simulor.core.events import MarketEvent
    from simulor.types import OrderSpec

__all__ = [
    "FillModel",
    "InstantFillModel",
]


class FillModel(ABC):
    """Base class for fill models.

    Fill models determine how orders are executed given market data.
    They return the fill price for an order, or None if the order
    cannot be filled yet.
    """

    @abstractmethod
    def get_fill_price(self, order_spec: OrderSpec, market_event: MarketEvent) -> Decimal | None:
        """Determine fill price for an order given market data.

        Args:
            order_spec: Order specification to fill
            market_event: Current market data for the instrument

        Returns:
            Fill price if order can be filled, None otherwise
        """
        ...


class InstantFillModel(FillModel):
    """Instant fill with side-aware pricing and full order type support.

    Simulates instantaneous execution with realistic spread-aware pricing.
    Uses a data priority waterfall to select the best available price data:
    Quote Tick > Quote Bar > Trade Tick > Trade Bar

    Pricing logic:
    - BUY orders: Fill at ask price (or trade price if no quotes available)
    - SELL orders: Fill at bid price (or trade price if no quotes available)

    Supported order types:
    - MARKET: Fill immediately at current market price
    - LIMIT: Fill if limit price is favorable
    - STOP: Fill when stop price is triggered
    - STOP_LIMIT: Fill when stop triggers and limit is favorable

    Characteristics:
    - Spread-aware (uses bid/ask when available)
    - Deterministic (same data produces same fills)
    - Instant execution (no partial fills or queue simulation)
    - Best for: Tick-level strategies, realistic spread costs

    Example:
        fill_model = InstantFillModel()
        # BUY market orders fill at ask price
        # SELL market orders fill at bid price
        # Limit/stop orders respect trigger conditions
    """

    def get_fill_price(self, order_spec: OrderSpec, market_event: MarketEvent) -> Decimal | None:
        """Determine fill price based on order type and market conditions.

        Args:
            order_spec: Order specification
            market_event: Current market data

        Returns:
            Fill price if order can be filled, None otherwise
        """
        # Resolve the current market price using waterfall logic
        market_price = self._resolve_market_price(order_spec.instrument, order_spec.side, market_event)

        if market_price is None:
            return None

        # Check order logic against resolved market price

        # MARKET ORDER: Fill immediately
        if order_spec.order_type == OrderType.MARKET:
            return market_price

        # LIMIT ORDER: Fill if price is favorable
        elif order_spec.order_type == OrderType.LIMIT:
            if order_spec.limit_price is None:
                return None

            # Buy Limit: Fill if Market <= Limit
            if order_spec.side == OrderSide.BUY:
                if market_price <= order_spec.limit_price:
                    return market_price
            # Sell Limit: Fill if Market >= Limit
            elif order_spec.side == OrderSide.SELL and market_price >= order_spec.limit_price:
                return market_price

        # STOP ORDER: Trigger and fill at market price
        elif order_spec.order_type == OrderType.STOP:
            if order_spec.stop_price is None:
                return None

            # Stop Buy: Triggered if Price >= Stop
            if order_spec.side == OrderSide.BUY:
                if market_price >= order_spec.stop_price:
                    return market_price
            # Stop Sell: Triggered if Price <= Stop
            elif order_spec.side == OrderSide.SELL and market_price <= order_spec.stop_price:
                return market_price

        # STOP LIMIT ORDER: Trigger at stop, fill if limit is favorable
        elif order_spec.order_type == OrderType.STOP_LIMIT:
            if order_spec.stop_price is None or order_spec.limit_price is None:
                return None

            if order_spec.side == OrderSide.BUY:
                # Stop triggered if price >= stop, fill if price <= limit
                if market_price >= order_spec.stop_price and market_price <= order_spec.limit_price:
                    return market_price
            elif order_spec.side == OrderSide.SELL:  # noqa: SIM102
                # Stop triggered if price <= stop, fill if price >= limit
                if market_price <= order_spec.stop_price and market_price >= order_spec.limit_price:
                    return market_price

        # TODO: Support other order types

        return None

    def _resolve_market_price(
        self, instrument: Instrument, order_side: OrderSide, market_event: MarketEvent
    ) -> Decimal | None:
        """Calculate execution price using data priority waterfall.

        Priority: Quote Tick > Quote Bar > Trade Tick > Trade Bar

        Args:
            instrument: Instrument to get price for
            side: Order side (BUY uses ask, SELL uses bid)
            event: Market event with price data

        Returns:
            Execution price or None if no data available
        """
        # PRIORITY 1: QUOTE TICK (Highest fidelity)
        quote_tick = market_event.get_last_quote_tick(instrument)
        if quote_tick:
            # Use ask for BUY, bid for SELL
            if order_side == OrderSide.BUY and quote_tick.ask_price and quote_tick.ask_price > 0:
                return quote_tick.ask_price
            elif order_side == OrderSide.SELL and quote_tick.bid_price and quote_tick.bid_price > 0:
                return quote_tick.bid_price

        # PRIORITY 2: QUOTE BAR (Aggregated spread)
        quote_bar = market_event.get_min_res_quote_bar(instrument)
        if quote_bar:
            if order_side == OrderSide.BUY and quote_bar.ask_close and quote_bar.ask_close > 0:
                return quote_bar.ask_close
            elif order_side == OrderSide.SELL and quote_bar.bid_close and quote_bar.bid_close > 0:
                return quote_bar.bid_close

        # PRIORITY 3: TRADE TICK (Last traded price)
        trade_tick = market_event.get_last_trade_tick(instrument)
        if trade_tick and trade_tick.price and trade_tick.price > 0:
            return trade_tick.price

        # PRIORITY 4: TRADE BAR (Close price)
        trade_bar = market_event.get_min_res_trade_bar(instrument)
        if trade_bar and trade_bar and trade_bar.close and trade_bar.close > 0:
            return trade_bar.close

        return None
