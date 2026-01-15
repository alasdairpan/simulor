"""Position tracking and management.

Provides a `Position` dataclass used by the portfolio manager to track
positions with average-cost basis and methods to update positions when
trades are executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulor.types import Instrument


@dataclass
class Position:
    """Represents a position for a single instrument.

    Fields:
    - instrument: `Instrument` identifier
    - current_price: last known market price
    - quantity: signed quantity (positive = long, negative = short)
    - average_cost: average cost basis per unit
    """

    instrument: Instrument
    current_price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    average_cost: Decimal = Decimal("0")

    @property
    def market_value(self) -> Decimal:
        """Compute current market value (qty * price)."""
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Compute unrealized P&L"""
        return (self.current_price - self.average_cost) * self.quantity

    def update_with_trade(self, qty: Decimal, price: Decimal) -> None:
        """Update the position with an executed trade (fill).
        Args:
           qty: Signed quantity of the trade (positive = buy, negative = sell)
           price: Execution price per unit
        """
        if qty == 0:
            return

        old_qty = self.quantity
        new_qty = old_qty + qty

        # 1. Increasing position (Weighted Average Cost)
        if old_qty == 0 or (old_qty > 0 and qty > 0) or (old_qty < 0 and qty < 0):
            total_cost = (self.average_cost * abs(old_qty)) + (price * abs(qty))
            if new_qty == 0:
                self.average_cost = Decimal("0")
            else:
                self.average_cost = total_cost / abs(new_qty)
        # 2. Reducing, closing, or flipping
        else:
            # If flipping (e.g. Long 10 -> Short 10 via Sell 20),
            # the new cost basis is the price of the flip.
            if (old_qty > 0 and new_qty < 0) or (old_qty < 0 and new_qty > 0):
                self.average_cost = price
            # If just closing (New=0), reset cost
            elif new_qty == 0:
                self.average_cost = Decimal("0")

            # If just reducing (Long 10 -> Long 5), average_cost stays the same.

        self.quantity = new_qty
