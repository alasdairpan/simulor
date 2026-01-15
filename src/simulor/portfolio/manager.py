"""Portfolio manager: Single source of truth for portfolio state.

Responsibilities:
- Position tracking with average cost basis
- Cash management
- Mark-to-market P&L calculation
- State provider for strategies
- Transaction logging
- Time-series recording of portfolio state
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from simulor.logging import get_logger
from simulor.portfolio.position import Position
from simulor.portfolio.recorder import TimeSeriesRecorder
from simulor.types import Instrument

if TYPE_CHECKING:
    from simulor.types.orders import Fill


# Create module logger
logger = get_logger(__name__)


class Portfolio:
    """Portfolio manager for tracking positions, cash, and portfolio value.

    Maintains portfolio state including cash balance and positions across
    instruments. Provides methods for updating positions from trade fills
    and marking positions to market.

    The portfolio owns a TimeSeriesRecorder that captures state evolution
    over time for analytics and performance measurement.
    """

    def __init__(self, starting_cash: Decimal) -> None:
        logger.debug("Initializing portfolio with starting cash=$%s", starting_cash)
        self._cash: Decimal = starting_cash
        self._positions: MutableMapping[Instrument, Position] = {}
        self.trades: list[Fill] = []
        self.recorder = TimeSeriesRecorder()

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def positions(self) -> Mapping[Instrument, Position]:
        return dict(self._positions)

    @property
    def total_value(self) -> Decimal:
        """Compute total portfolio value (Equity)."""
        total = Decimal(self._cash)
        for pos in self._positions.values():
            total += pos.market_value
        return total

    def update_cash(self, amount: Decimal) -> None:
        """Apply a cash delta (positive increases cash, negative reduces)."""
        self._cash += Decimal(amount)

    def update_position(self, fill: Fill) -> None:
        """Apply a trade fill to positions and cash.

        Cash is updated using simple T+0 settlement: cash -= quantity * price
        (quantity signed) and commissions are subtracted as well.

        Also records the trade in the trade history for tracking and captures
        a portfolio state snapshot for time-series analytics.

        Args:
            fill: Fill event to apply
        """

        logger.debug(
            "Updating position: %s qty=%s @ $%s, commission=$%s",
            fill.instrument.display_name,
            fill.quantity,
            fill.price,
            fill.commission,
        )

        # Ensure a Position object exists
        if fill.instrument not in self._positions:
            self._positions[fill.instrument] = Position(instrument=fill.instrument)

        pos = self._positions[fill.instrument]
        old_qty = pos.quantity
        pos.update_with_trade(fill.quantity, fill.price)

        # Update cash: buys reduce cash, sells increase cash
        # TODO: Should consider short sells and margin requirements
        cash_delta = -fill.quantity * fill.price - fill.commission
        self.update_cash(cash_delta)

        # Record the trade
        self.trades.append(fill)

        # Cleanup zero positions
        if pos.quantity == 0:
            logger.debug("Position closed: %s", fill.instrument.display_name)
            del self._positions[fill.instrument]
        else:
            logger.debug(
                "Position updated: %s quantity %s -> %s, avg_cost=$%s",
                fill.instrument.display_name,
                old_qty,
                pos.quantity,
                pos.average_cost,
            )

        logger.debug(
            "Portfolio state: cash=$%s, equity=$%s, positions=%d",
            self._cash,
            self.total_value,
            len(self._positions),
        )

    def mark_to_market(self, prices: Mapping[Instrument, Decimal]) -> None:
        """Update `current_price` for positions using provided price map.

        Also records a portfolio state snapshot for time-series analytics.

        Args:
            prices: Mapping of Instrument -> price
        """
        for instr, pos in list(self._positions.items()):
            if instr in prices:
                pos.current_price = Decimal(prices[instr])

    def record_state(self, timestamp: datetime) -> None:
        """Record current portfolio state snapshot."""
        self.recorder.record_snapshot(
            timestamp=timestamp,
            equity=self.total_value,
            cash=self._cash,
            positions=dict(self._positions),
        )
