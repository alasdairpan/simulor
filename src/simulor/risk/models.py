"""Risk management model implementations.

Reference implementations:
- PositionLimit: Max position size limits
- StopLoss: Automatic stop-loss placement
- LeverageLimit: Maximum leverage constraints
- DrawdownLimit: Reduce exposure on drawdown
"""

from __future__ import annotations

from decimal import Decimal

from simulor.core.protocols import RiskModel
from simulor.logging import get_logger
from simulor.types import Instrument

# Create module logger
logger = get_logger(__name__)


class PositionLimit(RiskModel):
    """Position size limit risk model.

    Enforces maximum position size as a percentage of total portfolio value.
    Scales down positions that exceed the limit while preserving direction
    (long/short) and relative strength.

    Example:
        >>> risk = PositionLimit(max_position=Decimal("0.1"))  # 10% max per position
        >>> targets = {instrument: Decimal("1000")}  # Worth 15% of portfolio
        >>> adjusted = risk.apply_limits(targets)  # Scaled down to 10%
    """

    def __init__(self, max_position: Decimal) -> None:
        """Initialize position limit risk model.

        Args:
            max_position: Maximum position size as fraction of portfolio value
        """
        if max_position <= Decimal("0") or max_position > Decimal("1"):
            raise ValueError("max_position must be between 0 and 1")

        self.max_position = max_position

    def apply_limits(self, targets: dict[Instrument, Decimal]) -> dict[Instrument, Decimal]:
        """Apply position size limits to target positions.

        For each target position, calculates its value as percentage of
        total portfolio value. If it exceeds max_position, scales it down
        while preserving direction (sign).

        Args:
            targets: Dictionary mapping instruments to unconstrained target quantities

        Returns:
            Dictionary mapping instruments to risk-adjusted target quantities.
            Positions exceeding the limit are scaled down.
        """
        if not targets:
            return {}

        # Get total portfolio value for percentage calculations
        total_value = self.portfolio.total_value

        if total_value <= 0:
            # No capital, can't take positions
            return {}

        adjusted: dict[Instrument, Decimal] = {}

        for instrument, target_quantity in targets.items():
            # Get current price to calculate position value
            current_price = self.market_store.get_latest_price(instrument)

            if current_price is None or current_price <= Decimal("0"):
                # Can't get price, skip this instrument
                continue

            # Calculate position value (absolute value for sizing)
            position_value = abs(target_quantity * current_price)

            # Calculate what percentage this is of portfolio
            position_pct = position_value / total_value

            # If exceeds limit, scale down
            if position_pct > self.max_position:
                # Scale factor to bring down to max_position
                scale_factor = self.max_position / position_pct
                adjusted_quantity = target_quantity * scale_factor // Decimal("1")
                adjusted[instrument] = adjusted_quantity
                logger.debug(
                    "PositionLimit: scaled down %s from %.2f to %.2f (%.1f%% -> %.1f%%)",
                    instrument,
                    target_quantity,
                    adjusted_quantity,
                    position_pct * 100,
                    (current_price * adjusted_quantity / total_value) * 100,
                )
            else:
                # Within limits, keep as-is
                adjusted[instrument] = target_quantity

        return adjusted
