"""Calendar-day-aware return calculation functions.

This module provides return calculation utilities that properly handle
mixed-asset portfolios (stocks + crypto) using calendar-day methodology.

Key features:
- Forward-fill missing calendar days for accurate volatility
- Handles stocks (weekends = no change) and crypto (24/7 trading) correctly
- UTC timezone standardization for global consistency
- 365-day annualization factor for calendar-day data

Design rationale:
- Stock prices forward-fill on weekends → 0% return (correct)
- Crypto shows actual returns every calendar day
- Portfolio volatility captures real daily fluctuations including weekends
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

__all__ = [
    "resample_to_calendar_days",
    "calculate_daily_returns",
    "calculate_total_return",
    "calculate_cagr",
]


def resample_to_calendar_days(
    timestamps: list[datetime], equity_values: list[Decimal]
) -> tuple[list[datetime], list[Decimal]]:
    """Resample equity series to calendar days with forward-fill.

    Fills missing calendar days with forward-filled equity values.
    This ensures proper handling of mixed portfolios:
    - Stocks: no change on weekends (forward-filled prices)
    - Crypto: actual returns every calendar day
    - Portfolio volatility captures real daily fluctuations

    Args:
        timestamps: List of UTC timestamps (must be sorted)
        equity_values: Corresponding equity values

    Returns:
        Tuple of (resampled_timestamps, resampled_equity_values)

    Raises:
        ValueError: If timestamps and equity_values have different lengths
                   or if timestamps is empty
    """
    if not timestamps:
        raise ValueError("Cannot resample empty time series")

    if len(timestamps) != len(equity_values):
        raise ValueError(
            f"Timestamps ({len(timestamps)}) and equity values ({len(equity_values)}) must have same length"
        )

    # Start from first timestamp, end at last timestamp
    start_date = timestamps[0].date()
    end_date = timestamps[-1].date()

    # Create date range covering all calendar days
    current_date = start_date
    calendar_days = []
    while current_date <= end_date:
        calendar_days.append(current_date)
        current_date += timedelta(days=1)

    # Build lookup for actual data points (date -> equity)
    data_map: dict[object, Decimal] = {}
    for ts, equity in zip(timestamps, equity_values, strict=True):
        data_map[ts.date()] = equity

    # Forward-fill missing days
    resampled_timestamps: list[datetime] = []
    resampled_equity: list[Decimal] = []
    last_equity = equity_values[0]

    for date in calendar_days:
        if date in data_map:
            last_equity = data_map[date]

        # Create timestamp at midnight UTC for this date
        dt = datetime(date.year, date.month, date.day, 0, 0, 0)
        if timestamps[0].tzinfo is not None:
            dt = dt.replace(tzinfo=timestamps[0].tzinfo)

        resampled_timestamps.append(dt)
        resampled_equity.append(last_equity)

    return resampled_timestamps, resampled_equity


def calculate_daily_returns(equity_series: list[Decimal]) -> list[Decimal]:
    """Calculate period-over-period percentage changes.

    Args:
        equity_series: List of equity values (should be calendar-day resampled)

    Returns:
        List of daily returns as decimals (0.01 = 1% return)

    Note:
        Returns empty list if fewer than 2 data points.
        Handles zero/negative equity by returning 0.0 return.
    """
    if len(equity_series) < 2:
        return []

    returns: list[Decimal] = []
    for i in range(1, len(equity_series)):
        prev_equity = equity_series[i - 1]
        curr_equity = equity_series[i]

        if prev_equity > 0:
            ret = (curr_equity / prev_equity) - 1
            returns.append(ret)
        else:
            # Handle edge case of zero/negative equity
            returns.append(Decimal("0.0"))

    return returns


def calculate_total_return(initial: Decimal, final: Decimal) -> Decimal:
    """Calculate simple total return.

    Args:
        initial: Starting equity
        final: Ending equity

    Returns:
        Total return as decimal (0.10 = 10% return)

    Raises:
        ValueError: If initial equity is zero or negative
    """
    if initial <= 0:
        raise ValueError("Initial equity must be positive")

    return (final / initial) - 1


def calculate_cagr(initial: Decimal, final: Decimal, num_calendar_days: int) -> Decimal:
    """Calculate compound annual growth rate using actual calendar days.

    Uses calendar-day methodology with 365-day years to match institutional
    standards for mixed-asset portfolios.

    Args:
        initial: Starting equity (must be positive)
        final: Ending equity (must be non-negative)
        num_calendar_days: Number of calendar days in period (must be positive)

    Returns:
        CAGR as decimal (0.15 = 15% annualized, -0.50 = -50% annualized)

    Raises:
        ValueError: If initial equity <= 0, final equity < 0, or num_calendar_days <= 0

    Note:
        Final equity of exactly 0 is mathematically valid (represents -100% CAGR
        for any time period). Negative final equity is rejected to prevent invalid
        calculations since equity cannot be negative in real portfolios.

    Examples:
        >>> calculate_cagr(Decimal("100000"), Decimal("150000"), 365)
        0.5  # 50% annual return over 1 year
        >>> calculate_cagr(Decimal("100000"), Decimal("50000"), 365)
        -0.5  # -50% annual return over 1 year
        >>> calculate_cagr(Decimal("100000"), Decimal("0"), 365)
        -1.0  # -100% annual return (total loss) over 1 year
    """
    if initial <= 0:
        raise ValueError("Initial equity must be positive")
    if final < 0:
        raise ValueError("Final equity must be non-negative")
    if num_calendar_days <= 0:
        raise ValueError("Number of calendar days must be positive")

    # CAGR = (final / initial)^(365 / num_days) - 1
    # When final = 0: 0^x = 0, so CAGR = -1.0 (-100% annualized)
    num_years = num_calendar_days / 365.0
    cagr = (final / initial) ** Decimal(str(1.0 / num_years)) - 1

    return cagr
