"""Analytics layer: Performance metrics, reporting, and visualization.

This module provides institutional-grade analytics for backtesting:
- TimeSeriesRecorder: Portfolio state recording
- BacktestResult: Comprehensive performance metrics
- Metrics calculation functions
- Visualization utilities (Plotly charts)
- HTML tearsheet generation

Key features:
- Calendar-day methodology for mixed-asset portfolios
- UTC timestamp standardization
- Eager metric computation for consistency
- 365-day annualization for calendar-day data
"""

from __future__ import annotations

from simulor.analytics.result import BacktestResult, StrategyMetrics
from simulor.analytics.tearsheet import Tearsheet
from simulor.portfolio.recorder import Snapshot, TimeSeriesRecorder

__all__ = [
    "TimeSeriesRecorder",
    "Snapshot",
    "BacktestResult",
    "StrategyMetrics",
    "Tearsheet",
]
