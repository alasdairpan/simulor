"""Portfolio construction model implementations.

Reference implementations of PortfolioConstructionModel:
- EqualWeight: Equal allocation across signals
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from simulor.core.protocols import PortfolioConstructionModel
from simulor.logging import get_logger
from simulor.types import Instrument

if TYPE_CHECKING:
    from simulor.alpha.signal import Signal


# Create module logger
logger = get_logger(__name__)


class PositionType(Enum):
    """Type of positions allowed in portfolio construction."""

    LONG_SHORT = "long_short"  # Allow both long and short positions
    LONG_ONLY = "long_only"  # Only long positions
    SHORT_ONLY = "short_only"  # Only short positions


class EqualWeight(PortfolioConstructionModel):
    """Equal weight allocation across signals.

    Allocates available capital equally across all *active* signals.

    Logic for Signal Strength:
    - Strength > 0: Enter Long (or rebalance Long)
    - Strength < 0: Enter Short (or rebalance Short)
    - Strength == 0:
        - If position held: HOLD (Keep in portfolio, rebalance to 1/N weight)
        - If no position: IGNORE (Do not enter)

    A reserve percentage (default 0%) is held back to account for
    transaction costs, rounding, and market impact.
    """

    def __init__(
        self,
        reserve_pct: Decimal = Decimal("0.0"),
        position_type: PositionType = PositionType.LONG_ONLY,
    ) -> None:
        """Initialize equal weight constructor.

        Args:
            reserve_pct: Percentage of portfolio value to reserve for
                transaction costs and rounding (default: 0.0 = no reserve)
            position_type: Type of positions allowed (default: LONG_ONLY)

        Raises:
            ValueError: If reserve_pct not in [0, 1)
        """
        if not 0 <= reserve_pct < 1:
            raise ValueError(f"reserve_pct must be in [0, 1), got {reserve_pct}")

        self.reserve_pct = reserve_pct
        self.position_type = position_type

    def calculate_targets(self, signals: dict[Instrument, Signal]) -> dict[Instrument, Decimal]:
        """Calculate equal-weighted target positions.

        Args:
            signals: Dictionary mapping instruments to signals

        Returns:
            Dictionary mapping instruments to target quantities.
        """
        if not signals:
            return {}

        # Get current positions
        current_positions = self.portfolio.positions

        # 1. Identify "Active" Instruments (The 'N' in 1/N)
        active_instruments: set[Instrument] = set()

        for instrument, signal in signals.items():
            strength = signal.strength
            is_held = instrument in current_positions and current_positions[instrument].quantity != 0

            # Logic: Determine if this instrument should have a slot in the portfolio
            if self.position_type == PositionType.LONG_ONLY:
                # Active if: Strong Buy OR (Neutral and already held)
                if strength > 0 or (strength == 0 and is_held):
                    active_instruments.add(instrument)

            elif self.position_type == PositionType.SHORT_ONLY:
                # Active if: Strong Sell OR (Neutral and already held)
                if strength < 0 or (strength == 0 and is_held):
                    active_instruments.add(instrument)

            elif self.position_type == PositionType.LONG_SHORT:  # noqa: SIM102
                # Active if: Directional Signal OR (Neutral and already held)
                if strength != 0 or (strength == 0 and is_held):
                    active_instruments.add(instrument)

        # 2. Handle Liquidation (If everything is inactive)
        if not active_instruments:
            # Return 0 target for all signaled instruments to ensure we close out positions
            return {inst: Decimal("0") for inst in signals}

        # 3. Calculate Allocation
        available_capital = self.portfolio.total_value
        usable_capital = available_capital * (1 - self.reserve_pct)

        # Divide by active count only, preventing cash drag
        capital_per_position = usable_capital / len(active_instruments)

        logger.debug(
            "EqualWeight: allocating $%.2f per position (%d active, $%.2f usable)",
            capital_per_position,
            len(active_instruments),
            usable_capital,
        )

        # 4. Generate Targets
        targets: dict[Instrument, Decimal] = {}

        for instrument, signal in signals.items():
            # If not active (e.g. Sell signal in LongOnly, or 0 strength and not held), close it.
            if instrument not in active_instruments:
                targets[instrument] = Decimal("0")
                continue

            current_price = self.market_store.get_latest_price(instrument)

            # Sanity check for bad data
            if current_price <= 0:
                logger.warning(f"Price for {instrument} is {current_price}, forcing close.")
                targets[instrument] = Decimal("0")
                continue

            # Calculate Base Shares (Magnitude)
            # TODO: Add logic here for AssetType to switch between // and /
            # Currently using floor division (integer shares) to match stock logic
            base_shares = capital_per_position // current_price

            # Determine Direction (Sign)
            target_sign = Decimal("1")

            if signal.strength == 0:
                # If holding (Strength 0), maintain current direction
                # (We know we hold it because it wouldn't be in active_instruments otherwise)
                current_qty = current_positions[instrument].quantity
                target_sign = Decimal("1") if current_qty > 0 else Decimal("-1")
            else:
                # If entering/flipping, use signal direction
                if self.position_type == PositionType.SHORT_ONLY:
                    target_sign = Decimal("-1")
                elif self.position_type == PositionType.LONG_SHORT:
                    target_sign = Decimal("1") if signal.strength > 0 else Decimal("-1")

                # LONG_ONLY defaults to 1

            targets[instrument] = base_shares * target_sign

        return targets
