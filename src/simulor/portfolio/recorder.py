"""Time-series recorder for portfolio state snapshots.

The TimeSeriesRecorder class captures portfolio state evolution over time,
storing chronological snapshots of equity, cash, and positions. All timestamps
are converted to UTC for consistency across global markets.

This recorder is owned by the Portfolio class, eliminating parallel hierarchies
and ensuring natural data ownership.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from simulor.portfolio.position import Position
    from simulor.types import Instrument

__all__ = ["TimeSeriesRecorder", "Snapshot"]


class Snapshot:
    """Immutable snapshot of portfolio state at a specific timestamp.

    Attributes:
        timestamp: UTC timestamp of the snapshot
        equity: Total portfolio value (cash + positions)
        cash: Cash balance
        positions: Dictionary of instrument -> position data
    """

    def __init__(
        self,
        timestamp: datetime,
        equity: Decimal,
        cash: Decimal,
        positions: dict[Instrument, Position],
    ) -> None:
        """Create a snapshot.

        Args:
            timestamp: Timestamp (will be converted to UTC)
            equity: Total portfolio value
            cash: Cash balance
            positions: Current positions (will be copied)
        """
        # Convert to UTC if not already
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
        elif timestamp.tzinfo != ZoneInfo("UTC"):
            timestamp = timestamp.astimezone(ZoneInfo("UTC"))

        self.timestamp = timestamp
        self.equity = equity
        self.cash = cash
        # Store copy of positions to prevent mutation
        self.positions = dict(positions)

    def __repr__(self) -> str:
        return (
            f"Snapshot(timestamp={self.timestamp.isoformat()}, "
            f"equity={self.equity}, cash={self.cash}, "
            f"num_positions={len(self.positions)})"
        )


class TimeSeriesRecorder:
    """Records portfolio state evolution as a time series.

    Stores chronological snapshots of portfolio equity, cash, and positions.
    All timestamps are normalized to UTC for global consistency.

    The recorder maintains snapshots in chronological order and provides
    efficient access to equity series and daily returns calculation.

    Example:
        >>> recorder = TimeSeriesRecorder()
        >>> recorder.record_snapshot(timestamp, equity, cash, positions)
        >>> equity_series = recorder.get_equity_series()
        >>> daily_returns = recorder.get_daily_returns()
    """

    def __init__(self) -> None:
        """Initialize an empty time-series recorder."""
        self._snapshots: list[Snapshot] = []

    def record_snapshot(
        self,
        timestamp: datetime,
        equity: Decimal,
        cash: Decimal,
        positions: dict[Instrument, Position],
    ) -> None:
        """Record a new portfolio snapshot.

        Args:
            timestamp: Timestamp of the snapshot (converted to UTC)
            equity: Total portfolio value
            cash: Cash balance
            positions: Current positions dictionary
        """
        snapshot = Snapshot(
            timestamp=timestamp,
            equity=equity,
            cash=cash,
            positions=positions,
        )
        self._snapshots.append(snapshot)

    def get_equity_series(self) -> list[tuple[datetime, Decimal]]:
        """Get time series of (timestamp, equity) pairs.

        Returns:
            List of (timestamp, equity) tuples in chronological order
        """
        return [(snapshot.timestamp, snapshot.equity) for snapshot in self._snapshots]

    def get_daily_returns(self) -> list[Decimal]:
        """Calculate period-over-period returns.

        Returns:
            List of decimal returns (0.01 = 1% return) between consecutive snapshots

        Note:
            Returns empty list if fewer than 2 snapshots.
            Returns are calculated as (equity_t / equity_{t-1}) - 1
        """
        if len(self._snapshots) < 2:
            return []

        returns: list[Decimal] = []
        for i in range(1, len(self._snapshots)):
            prev_equity = self._snapshots[i - 1].equity
            curr_equity = self._snapshots[i].equity

            if prev_equity > 0:
                ret = (curr_equity / prev_equity) - 1
                returns.append(ret)
            else:
                # Handle edge case of zero/negative equity
                returns.append(Decimal("0.0"))

        return returns

    def get_snapshots(self) -> list[Snapshot]:
        """Get all recorded snapshots in chronological order.

        Returns:
            List of Snapshot objects
        """
        return list(self._snapshots)

    def __len__(self) -> int:
        """Return number of recorded snapshots."""
        return len(self._snapshots)

    def __repr__(self) -> str:
        if not self._snapshots:
            return "TimeSeriesRecorder(empty)"

        start = self._snapshots[0].timestamp.isoformat()
        end = self._snapshots[-1].timestamp.isoformat()
        return f"TimeSeriesRecorder(snapshots={len(self._snapshots)}, start={start}, end={end})"
