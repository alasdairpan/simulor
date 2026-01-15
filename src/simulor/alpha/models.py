"""Alpha model implementations for signal generation.

Provides built-in implementations of AlphaModel:
- MovingAverageCrossover: Moving average crossover using market_store.trade_bars()

All return Dict[Instrument, Signal] with proper strength/confidence scoring.
"""

from __future__ import annotations

from decimal import Decimal

from simulor.alpha.signal import Signal, SignalType
from simulor.core.events import MarketEvent
from simulor.core.protocols import AlphaModel
from simulor.logging import get_logger
from simulor.types import Instrument, Resolution

# Create module logger
logger = get_logger(__name__)


class MovingAverageCrossover(AlphaModel):
    """Moving average crossover alpha model.

    Generates signals when fast MA crosses slow MA.

    Example:
        >>> alpha = MovingAverageCrossover(fast_period=20, slow_period=50)
        >>> signals = alpha.generate_signals(market_event)
    """

    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        """Initialize moving average crossover model.

        Args:
            fast_period: Fast moving average period
            slow_period: Slow moving average period
        """
        if fast_period < 1:
            raise ValueError("Fast period must be at least 1")
        if slow_period <= fast_period:
            raise ValueError("Slow period must be greater than fast period")

        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, market_event: MarketEvent) -> dict[Instrument, Signal]:
        """Generate signals based on moving average crossover.

        Args:
            data: Current market data event

        Returns:
            Dictionary mapping instruments to signals
        """
        signals: dict[Instrument, Signal] = {}

        for instrument in market_event.quote_bars:
            # Get historical bars for the instrument
            trade_bars = self.market_store.get_trade_bars(instrument, Resolution.DAILY)

            if len(trade_bars) < self.slow_period:
                # Insufficient data for calculation
                logger.debug(
                    "MovingAverageCrossover: insufficient data for %s, need %d bars but have %d",
                    instrument,
                    self.slow_period,
                    len(trade_bars),
                )
                continue

            # Calculate moving averages using last N closes
            recent_closes = [bar.close for bar in trade_bars[-self.slow_period :]]
            fast_ma = Decimal(sum(recent_closes[-self.fast_period :])) / Decimal(self.fast_period)
            slow_ma = Decimal(sum(recent_closes)) / Decimal(self.slow_period)

            # Calculate signal strength based on MA separation
            # Normalize by slow MA to get percentage difference
            separation = (fast_ma - slow_ma) / slow_ma

            # Cap strength at [-1, 1] using linear clipping
            # Scale separation by 10; values beyond [-1, 1] are clipped to limits
            raw_strength = separation * 10
            strength = max(Decimal("-1.0"), min(Decimal("1.0"), raw_strength))

            # Confidence based on how much data we have beyond minimum
            data_ratio = min(1.0, len(trade_bars) / (self.slow_period * 2))
            confidence = Decimal(str(data_ratio * 0.7))  # Max 0.7 for technical signals

            signals[instrument] = Signal(
                instrument=instrument,
                timestamp=market_event.time,
                signal_type=SignalType.TECHNICAL_INDICATOR,
                source_id="MovingAverageCrossover",
                strength=strength,
                confidence=confidence,
                metadata={
                    "fast_period": self.fast_period,
                    "slow_period": self.slow_period,
                    "fast_ma": fast_ma,
                    "slow_ma": slow_ma,
                    "separation": separation,
                },
            )

            logger.debug(
                "MovingAverageCrossover: %s signal strength=%.3f, fast_ma=%.2f, slow_ma=%.2f, sep=%.4f",
                instrument,
                strength,
                fast_ma,
                slow_ma,
                separation,
            )

        return signals
