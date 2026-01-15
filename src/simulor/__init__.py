"""Simulor: Production-ready event-driven backtesting framework.

Simulor is a high-performance backtesting framework designed for institutional-grade
quantitative research and algorithmic trading strategy development.

Key Features:
    - Event-driven architecture for realistic simulation
    - Pluggable strategy components (Alpha, Portfolio, Risk, Execution)
    - Multiple data resolutions (tick, minute, hour, daily)
    - Institutional-grade analytics and performance metrics
    - Rust-accelerated performance (optional)
    - Environment parity (backtest, paper, live)

Quick Start:
    >>> from decimal import Decimal
    >>> from simulor import (
    ...     Strategy, Engine, Fund,
    ...     MovingAverageCrossover, EqualWeight, PositionLimit, Immediate, Static,
    ...     CsvFeed, SimulatedBroker, Resolution, Instrument
    ... )
    >>>
    >>> strategy = Strategy(
    ...     name='MA_Crossover',
    ...     universe=Static([Instrument.stock('SPY'), Instrument.stock('QQQ')]),
    ...     alpha=MovingAverageCrossover(fast_period=10, slow_period=20),
    ...     construction=EqualWeight(),
    ...     risk=PositionLimit(max_position=Decimal('0.1')),
    ...     execution=Immediate()
    ... )
    >>>
    >>> fund = Fund(strategies=[strategy], capital=Decimal('100000'))
    >>> engine = Engine(
    ...     data=CsvFeed('data/bars.csv', resolution=Resolution.DAILY),
    ...     fund=fund,
    ...     broker=SimulatedBroker()
    ... )
    >>> results = engine.run(start='2020-01-01', end='2023-12-31', mode='backtest')
"""

__version__ = "0.1.0b1"
__author__ = "Simulor Contributors"

import simulor.logging

# Capital allocation (multi-strategy)
from simulor.allocation import WeightBasedAllocationModel

# Alpha models and signals
from simulor.alpha import MovingAverageCrossover, Signal, SignalType

# Analytics and results
from simulor.analytics import BacktestResult, StrategyMetrics, Tearsheet

# Events (for custom components)
from simulor.core.events import MarketEvent

# Protocols (for custom implementations)
from simulor.core.protocols import (
    AlphaModel,
    ExecutionModel,
    PortfolioConstructionModel,
    RiskModel,
    UniverseSelectionModel,
)
from simulor.data import MarketStore
from simulor.data.csv_feed import CsvFeed

# Core engine and orchestration
from simulor.engine import Engine

# Execution models and orders
from simulor.execution import Fill, Immediate, OrderSpec, OrderType
from simulor.execution.simulation.broker import SimulatedBroker

# Portfolio management
from simulor.portfolio import EqualWeight, Fund, Portfolio, Position

# Risk management
from simulor.risk import PositionLimit

# Strategy composition
from simulor.strategy import Strategy

# Data structures and providers
from simulor.types import (
    AssetType,
    Instrument,
    MarketData,
    Resolution,
    TradeBar,
    TradeTick,
)

# Universe selection
from simulor.universe import Static

__all__ = [
    "__version__",
    # === Core Engine & Orchestration ===
    "Engine",
    # === Strategy Framework ===
    "Strategy",
    # === Portfolio Management ===
    "Fund",
    "Portfolio",
    "Position",
    "EqualWeight",
    # === Alpha Generation ===
    "AlphaModel",
    "MovingAverageCrossover",
    "Signal",
    "SignalType",
    # === Risk Management ===
    "RiskModel",
    "PositionLimit",
    # === Execution ===
    "ExecutionModel",
    "Immediate",
    "SimulatedBroker",
    "OrderSpec",
    "OrderType",
    "Fill",
    # === Universe Selection ===
    "UniverseSelectionModel",
    "Static",
    # === Capital Allocation ===
    "WeightBasedAllocationModel",
    # === Data Providers & Structures ===
    "CsvFeed",
    "MarketStore",
    "Instrument",
    "MarketData",
    "TradeBar",
    "TradeTick",
    "Resolution",
    "AssetType",
    # === Events (for custom components) ===
    "MarketEvent",
    # === Protocols (for custom implementations) ===
    "PortfolioConstructionModel",
    # === Analytics & Results ===
    "BacktestResult",
    "StrategyMetrics",
    "Tearsheet",
]
