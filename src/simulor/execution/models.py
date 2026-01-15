"""Execution models.

Defines the ExecutionModel protocol and reference implementations:
- ExecutionModel: Protocol for converting target positions to orders
- Immediate: Generate market orders for immediate execution
"""

from __future__ import annotations

from decimal import Decimal

from simulor.core.protocols import ExecutionModel
from simulor.logging import get_logger
from simulor.types import Instrument, OrderSide, OrderSpec, OrderType

# Create module logger
logger = get_logger(__name__)


class Immediate(ExecutionModel):
    """Immediate execution via market orders with rebalancing controls.

    Generates market orders to reach target positions immediately.
    Compares targets to current positions and creates orders for the delta.

    Supports multiple tolerance modes to prevent excessive trading:
    - min_shares: Minimum absolute share quantity to trade
    - min_notional: Minimum dollar value to trade
    - min_pct_change: Minimum percentage change in position

    Real-world constraints:
    - US stocks: Most brokers support fractional shares (0.000001 shares minimum)
    - Typical minimum notional: $1-5 per trade

    Example:
        Current: 100 shares AAPL @ $150
        Target: 150 shares AAPL
        With min_notional=$1000: Order BUY 50 shares ($7,500) ✓
        With min_notional=$10000: No order (delta only $7,500) ✗
    """

    def __init__(
        self,
        min_shares: Decimal | None = None,
        min_notional: Decimal | None = None,
        min_pct_change: Decimal | None = None,
    ) -> None:
        """Initialize immediate execution model with rebalancing controls.

        Args:
            min_shares: Minimum absolute share quantity to trade (e.g., 1.0 for whole shares)
            min_notional: Minimum dollar value to trade (e.g., 100 for $100 minimum)
            min_pct_change: Minimum percentage change to trade (e.g., 0.02 for 2%)
        """
        if min_shares is not None and min_shares < 0:
            raise ValueError("min_shares must be non-negative")
        if min_notional is not None and min_notional < 0:
            raise ValueError("min_notional must be non-negative")
        if min_pct_change is not None and (min_pct_change < 0 or min_pct_change >= 1):
            raise ValueError("min_pct_change must be in [0, 1)")

        self.min_shares = min_shares
        self.min_notional = min_notional
        self.min_pct_change = min_pct_change

    def generate_orders(self, targets: dict[Instrument, Decimal]) -> list[OrderSpec]:
        """Generate market orders for immediate execution with rebalancing controls.

        Args:
            targets: Dictionary mapping instruments to target quantities

        Returns:
            List of market orders to reach target positions, filtered by tolerance settings
        """
        orders: list[OrderSpec] = []

        if not targets:
            return orders

        # Get all instruments (current positions + targets)
        all_instruments = set(self.portfolio.positions.keys()) | set(targets.keys())

        for instrument in all_instruments:
            # Get current and target quantities
            current_position = self.portfolio.positions.get(instrument)
            current_qty = current_position.quantity if current_position else Decimal("0")
            target_qty = targets.get(instrument, Decimal("0"))

            # Calculate delta
            delta = target_qty - current_qty

            # Skip if no change needed
            if delta == 0:
                continue

            # Apply rebalancing tolerance filters
            abs_delta = abs(delta)

            # Filter 1: Minimum shares
            if self.min_shares is not None and abs_delta < self.min_shares:
                logger.debug(
                    "Immediate: skipping %s, delta %.2f < min_shares %.2f",
                    instrument,
                    abs_delta,
                    self.min_shares,
                )
                continue

            # Filter 2: Minimum notional value
            if self.min_notional is not None:
                current_price = self.market_store.get_latest_price(instrument)
                notional = abs_delta * current_price
                if notional < self.min_notional:
                    logger.debug(
                        "Immediate: skipping %s, notional $%.2f < min_notional $%.2f",
                        instrument,
                        notional,
                        self.min_notional,
                    )
                    continue

            # Filter 3: Minimum percentage change
            if self.min_pct_change is not None and current_qty != 0:
                pct_change = abs_delta / abs(current_qty)
                if pct_change < self.min_pct_change:
                    logger.debug(
                        "Immediate: skipping %s, pct_change %.2f%% < min %.2f%%",
                        instrument,
                        pct_change * 100,
                        self.min_pct_change * 100,
                    )
                    continue

            # Determine side and quantity
            if delta > 0:
                side = OrderSide.BUY
                quantity = delta
            else:
                side = OrderSide.SELL
                quantity = abs(delta)

            # Create market order
            order = OrderSpec(
                instrument=instrument,
                side=side,
                quantity=quantity,
                order_type=OrderType.MARKET,
                reason=f"Rebalance to target: {target_qty}",
            )
            orders.append(order)

        return orders
