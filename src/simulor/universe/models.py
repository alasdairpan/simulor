"""Universe selection models for determining trading universe.

Provides built-in implementations of UniverseSelectionModel:
- Static: Fixed list of instruments
- Top: Top N by metric with rebalancing
- Liquid: Volume/price filters
- Fundamental: Metric-based filters
"""

from __future__ import annotations

import logging

from simulor.core.protocols import UniverseSelectionModel
from simulor.logging import get_logger
from simulor.types import Instrument

# Create module logger
logger = get_logger(__name__)


class Static(UniverseSelectionModel):
    """Static universe: Fixed list of instruments.

    The simplest universe selection model that maintains a constant
    list of instruments throughout the backtest.

    Example:
        >>> universe = Static([
        ...     Instrument.stock("AAPL"),
        ...     Instrument.stock("GOOGL"),
        ...     Instrument.stock("MSFT")
        ... ])
    """

    def __init__(self, instruments: list[Instrument]) -> None:
        """Initialize static universe.

        Args:
            instruments: List of instruments to trade
        """
        if not instruments:
            raise ValueError("Universe must contain at least one instrument")
        self._instruments = list(instruments)
        self._logged = False

    def select_universe(self) -> list[Instrument]:
        """Return the fixed list of instruments.

        Returns:
            List of instruments in universe
        """
        if not self._logged:
            logger.info("Static universe: %d instruments", len(self._instruments))
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Static universe instruments: %s", self._instruments)
            self._logged = True
        return self._instruments
