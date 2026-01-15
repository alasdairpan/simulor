"""Strategy composition and configuration.

Defines the Strategy dataclass that composes all five strategy components:
- UniverseSelectionModel: Symbol selection
- AlphaModel: Signal generation
- PortfolioConstructionModel: Position sizing
- RiskModel: Risk constraint application
- ExecutionModel: Order generation

This module provides the cross-layer composition pattern for assembling
complete trading strategies from pluggable components.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulor.core.protocols import (
    AlphaModel,
    ExecutionModel,
    PortfolioConstructionModel,
    RiskModel,
    UniverseSelectionModel,
)


@dataclass
class Strategy:
    """Strategy composition holding all five components.

    Composes a complete trading strategy from pluggable components:
    - universe: Which instruments to trade
    - alpha: How to generate signals
    - construction: How to size positions
    - risk: How to apply risk constraints
    - execution: How to generate orders

    The Engine uses this composition to orchestrate the strategy pipeline:
    universe → alpha → construction → risk → execution → orders

    Capital Allocation:
    - Strategy does NOT specify its own capital
    - Capital is allocated by Fund's allocation model
    - This enables proper portfolio-level capital management and reserves

    Examples:
        >>> from simulor.strategy import Strategy
        >>> from simulor.universe import Static
        >>> from simulor.alpha.models import MovingAverageCrossover
        >>> from simulor.portfolio import EqualWeight
        >>> from simulor.risk import PositionLimit
        >>> from simulor.execution import Immediate
        >>>
        >>> strategy = Strategy(
        ...     name="MA_Crossover",
        ...     universe=Static([Instrument.stock("AAPL", "NASDAQ")]),
        ...     alpha=MovingAverageCrossover(fast_period=20, slow_period=50),
        ...     construction=EqualWeight(),
        ...     risk=PositionLimit(max_position=Decimal("0.1")),
        ...     execution=Immediate()
        ... )

    """

    name: str
    universe: UniverseSelectionModel
    alpha: AlphaModel
    construction: PortfolioConstructionModel
    risk: RiskModel
    execution: ExecutionModel

    def __post_init__(self) -> None:
        """Validate strategy configuration and create default subscription filter."""
        if not self.name or not self.name.strip():
            raise ValueError("Strategy name cannot be empty")
