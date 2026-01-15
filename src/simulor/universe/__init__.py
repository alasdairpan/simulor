"""Universe selection: Determine which instruments to trade.

Provides the protocol and reference implementations for universe selection:
- UniverseSelectionModel: Protocol interface
- Static: Fixed list of instruments
- Top: Top N by metric with rebalancing
- Liquid: Volume/price filters
- Fundamental: Metric-based filters
"""

from __future__ import annotations

from simulor.universe.models import Static

__all__ = [
    "Static",
]
