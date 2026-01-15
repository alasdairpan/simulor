"""Comprehensive performance metrics calculation.

This module provides institutional-grade metrics organized by category:
- Returns: Total, annualized, cumulative
- Risk-adjusted: Sharpe, Sortino, Calmar ratios
- Drawdowns: Maximum, average, recovery time
- Trade statistics: Win rate, profit factor, expectancy
- Risk measures: Volatility, downside deviation, best/worst day

All calculations use calendar-day methodology with 365-day annualization.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from simulor.types import Fill

__all__ = [
    # Returns
    "calculate_cumulative_returns",
    "calculate_annualized_return",
    # Risk-adjusted
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_calmar_ratio",
    # Drawdowns
    "calculate_drawdown_series",
    "calculate_max_drawdown",
    "calculate_average_drawdown",
    "calculate_recovery_time",
    "calculate_underwater_periods",
    # Trade statistics
    "calculate_win_rate",
    "calculate_profit_factor",
    "calculate_expectancy",
    "calculate_avg_win",
    "calculate_avg_loss",
    "calculate_trade_count",
    # Risk measures
    "calculate_volatility",
    "calculate_downside_deviation",
    "calculate_best_day",
    "calculate_worst_day",
    # Types
    "MaxDrawdownInfo",
]


class MaxDrawdownInfo(TypedDict):
    """Type definition for max drawdown information dict."""

    pct: Decimal
    start_date: datetime | None
    end_date: datetime | None
    recovery_date: datetime | None
    duration_days: int


# ============================================================================
# Returns Metrics
# ============================================================================


def calculate_cumulative_returns(equity_series: list[Decimal]) -> list[Decimal]:
    """Calculate cumulative returns from initial value.

    Args:
        equity_series: List of equity values

    Returns:
        List of cumulative returns as decimals (0.10 = 10% cumulative return)
    """
    if not equity_series:
        return []

    initial = equity_series[0]
    if initial <= 0:
        return [Decimal("0")] * len(equity_series)

    return [(equity / initial) - 1 for equity in equity_series]


def calculate_annualized_return(initial: Decimal, final: Decimal, num_days: int) -> Decimal:
    """Calculate annualized return using CAGR formula.

    Args:
        initial: Starting equity
        final: Ending equity
        num_days: Number of calendar days in period

    Returns:
        Annualized return as decimal (0.15 = 15% annual return)
    """
    if initial <= 0 or final <= 0 or num_days <= 0:
        return Decimal("0.0")

    num_years = Decimal(str(num_days)) / Decimal("365.0")
    exponent = Decimal("1.0") / num_years
    return (final / initial) ** exponent - 1


# ============================================================================
# Risk-Adjusted Performance
# ============================================================================


def calculate_sharpe_ratio(daily_returns: list[Decimal], risk_free_rate: Decimal = Decimal("0.0")) -> Decimal:
    """Calculate Sharpe ratio with 365-day annualization.

    Formula: (Mean Return - Risk Free Rate) / Std Dev * sqrt(365)

    Args:
        daily_returns: List of daily returns (calendar days)
        risk_free_rate: Annual risk-free rate as decimal (default: 0.0)

    Returns:
        Annualized Sharpe ratio
    """
    if not daily_returns:
        return Decimal("0.0")

    n = len(daily_returns)
    if n < 2:
        return Decimal("0.0")

    # Convert annual risk-free rate to daily
    daily_rf = risk_free_rate / Decimal("365.0")

    # Calculate mean and std dev (use Decimal denominators to keep types Decimal)
    mean_return = sum(daily_returns) / Decimal(n)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / Decimal(n - 1)
    std_dev = variance.sqrt()

    if std_dev == 0:
        return Decimal("0.0")

    # Annualize: multiply by sqrt(365)
    sharpe = ((mean_return - daily_rf) / std_dev) * Decimal("365.0").sqrt()

    return sharpe


def calculate_sortino_ratio(
    daily_returns: list[Decimal],
    risk_free_rate: Decimal = Decimal("0.0"),
    target_return: Decimal = Decimal("0.0"),
) -> Decimal:
    """Calculate Sortino ratio (downside deviation only).

    Formula: (Mean Return - Target) / Downside Dev × sqrt(365)

    Args:
        daily_returns: List of daily returns
        risk_free_rate: Annual risk-free rate (default: 0.0)
        target_return: Target daily return threshold (default: 0.0)

    Returns:
        Annualized Sortino ratio
    """
    if not daily_returns:
        return Decimal("0.0")

    n = len(daily_returns)
    if n < 2:
        return Decimal("0.0")

    # Convert annual risk-free rate to daily
    daily_rf = risk_free_rate / Decimal("365.0")

    mean_return = sum(daily_returns) / Decimal(n)

    # Calculate downside deviation (only negative deviations from target)
    downside_returns = [min(r - target_return, Decimal("0")) for r in daily_returns]
    downside_variance = sum(r**2 for r in downside_returns) / Decimal(n - 1)
    downside_dev = downside_variance.sqrt()

    if downside_dev == 0:
        return Decimal("0.0")

    # Annualize
    sortino = ((mean_return - daily_rf) / downside_dev) * Decimal("365.0").sqrt()

    return sortino


def calculate_calmar_ratio(annualized_return: Decimal, max_drawdown_pct: Decimal) -> Decimal:
    """Calculate Calmar ratio.

    Formula: Annualized Return / abs(Maximum Drawdown)

    Args:
        annualized_return: Annual return as decimal
        max_drawdown_pct: Maximum drawdown as decimal (should be negative)

    Returns:
        Calmar ratio
    """
    if max_drawdown_pct >= 0:
        return Decimal("0.0")

    return annualized_return / abs(max_drawdown_pct)


# ============================================================================
# Drawdown Metrics
# ============================================================================


def calculate_drawdown_series(equity_series: list[Decimal]) -> list[Decimal]:
    """Calculate running drawdown from peak.

    Args:
        equity_series: List of equity values

    Returns:
        List of drawdown percentages (negative values, 0.0 at new peaks)
    """
    if not equity_series:
        return []

    drawdowns: list[Decimal] = []
    running_max = Decimal("0")

    for equity in equity_series:
        if equity > running_max:
            running_max = equity

        dd = (equity / running_max) - 1 if running_max > 0 else Decimal("0")
        drawdowns.append(dd)

    return drawdowns


def calculate_max_drawdown(equity_series: list[Decimal], timestamps: list[datetime] | None = None) -> MaxDrawdownInfo:
    """Calculate maximum drawdown with metadata.

    Args:
        equity_series: List of equity values
        timestamps: Optional list of timestamps for date tracking

    Returns:
        MaxDrawdownInfo dict with drawdown details
    """
    if not equity_series:
        return MaxDrawdownInfo(
            pct=Decimal("0"),
            start_date=None,
            end_date=None,
            recovery_date=None,
            duration_days=0,
        )

    max_dd = Decimal("0")
    max_dd_start_idx = 0
    max_dd_end_idx = 0

    running_max = Decimal("0")
    running_max_idx = 0

    for i, equity in enumerate(equity_series):
        if equity > running_max:
            running_max = equity
            running_max_idx = i

        if running_max > 0:
            dd = (equity / running_max) - 1
            if dd < max_dd:
                max_dd = dd
                max_dd_start_idx = running_max_idx
                max_dd_end_idx = i

    # Find recovery date (if any)
    recovery_idx = None
    if max_dd_end_idx < len(equity_series) - 1:
        peak_value = equity_series[max_dd_start_idx]
        for i in range(max_dd_end_idx + 1, len(equity_series)):
            if equity_series[i] >= peak_value:
                recovery_idx = i
                break

    # Calculate duration in days
    duration_days = 0
    if timestamps and max_dd_end_idx > max_dd_start_idx:
        duration = timestamps[max_dd_end_idx] - timestamps[max_dd_start_idx]
        duration_days = duration.days

    return MaxDrawdownInfo(
        pct=max_dd,
        start_date=timestamps[max_dd_start_idx] if timestamps else None,
        end_date=timestamps[max_dd_end_idx] if timestamps else None,
        recovery_date=timestamps[recovery_idx] if timestamps and recovery_idx else None,
        duration_days=duration_days,
    )


def calculate_average_drawdown(drawdown_series: list[Decimal]) -> Decimal:
    """Calculate average drawdown.

    Args:
        drawdown_series: List of drawdown percentages

    Returns:
        Average drawdown (negative value)
    """
    if not drawdown_series:
        return Decimal("0.0")

    return sum(drawdown_series) / Decimal(len(drawdown_series))


def calculate_recovery_time(max_dd_info: MaxDrawdownInfo) -> int | None:
    """Calculate recovery time from maximum drawdown.

    Args:
        max_dd_info: Maximum drawdown info from calculate_max_drawdown

    Returns:
        Number of days to recover, or None if not recovered
    """
    start_date = max_dd_info["start_date"]
    recovery_date = max_dd_info["recovery_date"]

    if start_date and recovery_date:
        return (recovery_date - start_date).days

    return None


def calculate_underwater_periods(
    equity_series: list[Decimal], timestamps: list[datetime] | None = None
) -> list[dict[str, datetime | int]]:
    """Calculate all drawdown (underwater) periods.

    Args:
        equity_series: List of equity values
        timestamps: Optional list of timestamps

    Returns:
        List of dictionaries with keys:
        - start_date: Start of underwater period
        - end_date: End of underwater period (or None if ongoing)
        - duration_days: Length of period in days
    """
    if not equity_series:
        return []

    periods: list[dict[str, Any]] = []
    running_max = Decimal("0")
    underwater_start_idx: int | None = None

    for i, equity in enumerate(equity_series):
        if equity > running_max:
            # New peak - close any open underwater period
            if underwater_start_idx is not None:
                start_idx = underwater_start_idx  # Capture for type narrowing
                duration = (timestamps[i] - timestamps[start_idx]).days if timestamps else i - start_idx

                periods.append(
                    {
                        "start_date": timestamps[start_idx] if timestamps else None,
                        "end_date": timestamps[i] if timestamps else None,
                        "duration_days": duration,
                    }
                )
                underwater_start_idx = None

            running_max = equity
        elif underwater_start_idx is None and running_max > 0:
            # Start new underwater period
            underwater_start_idx = i - 1  # Previous index was the peak

    # Handle ongoing underwater period
    if underwater_start_idx is not None:
        duration = len(equity_series) - 1 - underwater_start_idx if timestamps else 0
        if timestamps:
            duration = (timestamps[-1] - timestamps[underwater_start_idx]).days

        periods.append(
            {
                "start_date": timestamps[underwater_start_idx] if timestamps else None,
                "end_date": None,  # Ongoing
                "duration_days": duration,
            }
        )

    return periods


# ============================================================================
# Trade Statistics
# ============================================================================


def calculate_win_rate(fills: list[Fill]) -> Decimal:
    """Calculate percentage of profitable trades.

    Args:
        fills: List of Fill objects

    Returns:
        Win rate as decimal (0.60 = 60% win rate)

    Note:
        Only considers closed trades (matching buy/sell pairs).
    """
    if not fills:
        return Decimal("0.0")

    winning_trades = sum(1 for fill in fills if fill.quantity * fill.price > 0)
    total_trades = len(fills)

    return Decimal(winning_trades) / Decimal(total_trades) if total_trades > 0 else Decimal("0.0")


def calculate_profit_factor(fills: list[Fill]) -> Decimal:
    """Calculate profit factor (total wins / total losses).

    Args:
        fills: List of Fill objects

    Returns:
        Profit factor (>1.0 is profitable overall)
    """
    if not fills:
        return Decimal("0.0")

    total_wins = Decimal("0")
    total_losses = Decimal("0")

    for fill in fills:
        pnl = fill.quantity * fill.price - fill.commission
        if pnl > 0:
            total_wins += pnl
        elif pnl < 0:
            total_losses += abs(pnl)

    if total_losses == 0:
        return total_wins if total_wins > 0 else Decimal("0.0")

    return total_wins / total_losses


def calculate_expectancy(fills: list[Fill]) -> Decimal:
    """Calculate expected value per trade.

    Args:
        fills: List of Fill objects

    Returns:
        Expected P&L per trade in base currency units
    """
    if not fills:
        return Decimal("0.0")

    total_pnl = sum(fill.quantity * fill.price - fill.commission for fill in fills)
    return total_pnl / Decimal(len(fills))


def calculate_avg_win(fills: list[Fill]) -> Decimal:
    """Calculate average profitable trade size.

    Args:
        fills: List of Fill objects

    Returns:
        Average winning trade P&L
    """
    if not fills:
        return Decimal("0.0")

    winning_trades = [
        fill.quantity * fill.price - fill.commission
        for fill in fills
        if (fill.quantity * fill.price - fill.commission) > 0
    ]

    if not winning_trades:
        return Decimal("0.0")

    return sum(winning_trades) / Decimal(str(len(winning_trades)))


def calculate_avg_loss(fills: list[Fill]) -> Decimal:
    """Calculate average losing trade size.

    Args:
        fills: List of Fill objects

    Returns:
        Average losing trade P&L (negative value)
    """
    if not fills:
        return Decimal("0.0")

    losing_trades = [
        fill.quantity * fill.price - fill.commission
        for fill in fills
        if (fill.quantity * fill.price - fill.commission) < 0
    ]

    if not losing_trades:
        return Decimal("0.0")

    return sum(losing_trades) / Decimal(str(len(losing_trades)))


def calculate_trade_count(fills: list[Fill]) -> int:
    """Count total number of trades.

    Args:
        fills: List of Fill objects

    Returns:
        Number of trades
    """
    return len(fills)


# ============================================================================
# Risk Measures
# ============================================================================


def calculate_volatility(daily_returns: list[Decimal]) -> Decimal:
    """Calculate annualized volatility.

    Formula: Daily Std Dev × sqrt(365)

    Args:
        daily_returns: List of daily returns

    Returns:
        Annualized volatility as decimal
    """
    if len(daily_returns) < 2:
        return Decimal("0.0")

    n = len(daily_returns)
    mean = sum(daily_returns) / Decimal(str(n))
    variance = sum((r - mean) ** 2 for r in daily_returns) / Decimal(str(n - 1))
    std_dev = variance.sqrt()

    # Annualize using sqrt(365)
    return std_dev * Decimal("365.0").sqrt()


def calculate_downside_deviation(daily_returns: list[Decimal], target: Decimal = Decimal("0.0")) -> Decimal:
    """Calculate downside deviation (only negative deviations).

    Args:
        daily_returns: List of daily returns
        target: Target return threshold (default: 0.0)

    Returns:
        Annualized downside deviation
    """
    if len(daily_returns) < 2:
        return Decimal("0.0")

    downside_returns = [min(r - target, Decimal("0")) for r in daily_returns]
    variance = sum(r**2 for r in downside_returns) / Decimal(str(len(daily_returns) - 1))
    downside_dev = variance.sqrt()

    # Annualize using sqrt(365)
    return downside_dev * Decimal("365.0").sqrt()


def calculate_best_day(daily_returns: list[Decimal]) -> Decimal:
    """Find best single-day return.

    Args:
        daily_returns: List of daily returns

    Returns:
        Best daily return as decimal
    """
    if not daily_returns:
        return Decimal("0.0")

    return max(daily_returns)


def calculate_worst_day(daily_returns: list[Decimal]) -> Decimal:
    """Find worst single-day return.

    Args:
        daily_returns: List of daily returns

    Returns:
        Worst daily return as decimal (negative)
    """
    if not daily_returns:
        return Decimal("0.0")

    return min(daily_returns)
