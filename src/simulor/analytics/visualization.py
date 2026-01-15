"""Visualization utilities using Plotly.

Generates professional-grade interactive charts:
- Equity curves with benchmark overlay
- Drawdown charts with underwater period shading
- Monthly returns heatmaps (calendar-style)
- Returns distribution histograms with normal curve

All charts use Simulor's professional theme with consistent styling.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import plotly.graph_objects as go

__all__ = [
    "plot_equity_curve",
    "plot_drawdown_chart",
    "plot_monthly_returns_heatmap",
    "plot_returns_distribution",
]


def _apply_simulor_theme(fig: go.Figure) -> go.Figure:
    """Apply consistent professional styling to Plotly figures.

    Args:
        fig: Plotly figure to style

    Returns:
        Styled figure
    """
    fig.update_layout(
        template="plotly_dark",
        font={"family": "Arial, sans-serif", "size": 12, "color": "#E1E1E1"},
        plot_bgcolor="#1E1E1E",
        paper_bgcolor="#2D2D2D",
        hovermode="x unified",
        showlegend=True,
        legend={
            "bgcolor": "rgba(45, 45, 45, 0.8)",
            "bordercolor": "#444",
            "borderwidth": 1,
        },
    )

    fig.update_xaxes(
        gridcolor="#333",
        showgrid=True,
        zeroline=False,
    )

    fig.update_yaxes(
        gridcolor="#333",
        showgrid=True,
        zeroline=False,
    )

    return fig


def plot_equity_curve(
    timestamps: list[datetime],
    equity_values: list[Decimal],
    benchmark_equity: list[Decimal] | None = None,
    benchmark_timestamps: list[datetime] | None = None,
    title: str = "Portfolio Equity Curve",
) -> go.Figure:
    """Plot interactive equity curve with optional benchmark overlay.

    Args:
        timestamps: List of timestamps
        equity_values: Portfolio equity values
        benchmark_equity: Optional benchmark equity values
        benchmark_timestamps: Optional benchmark timestamps (if different from portfolio)
        title: Chart title

    Returns:
        Plotly Figure with equity curve
    """
    fig = go.Figure()

    # Portfolio equity curve
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=equity_values,
            mode="lines",
            name="Portfolio",
            line={"color": "#00D9FF", "width": 2},
            hovertemplate="<b>%{x}</b><br>Equity: $%{y:,.2f}<extra></extra>",
        )
    )

    # Benchmark overlay (if provided)
    if benchmark_equity is not None:
        bench_x = benchmark_timestamps if benchmark_timestamps else timestamps
        fig.add_trace(
            go.Scatter(
                x=bench_x,
                y=benchmark_equity,
                mode="lines",
                name="Benchmark",
                line={"color": "#FF6B9D", "width": 2, "dash": "dash"},
                hovertemplate="<b>%{x}</b><br>Benchmark: $%{y:,.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        height=500,
    )

    return _apply_simulor_theme(fig)


def plot_drawdown_chart(
    timestamps: list[datetime],
    drawdown_pcts: list[Decimal],
    max_dd_info: dict[str, Any] | None = None,
    title: str = "Drawdown Chart",
) -> go.Figure:
    """Plot drawdown chart with underwater period shading.

    Args:
        timestamps: List of timestamps
        drawdown_pcts: Drawdown percentages (negative values)
        max_dd_info: Optional max drawdown info dict with 'pct', 'end_date'
        title: Chart title

    Returns:
        Plotly Figure with drawdown chart
    """
    fig = go.Figure()

    # Drawdown area chart
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=drawdown_pcts,
            mode="lines",
            name="Drawdown",
            fill="tozeroy",
            line={"color": "#FF6B9D", "width": 1},
            fillcolor="rgba(255, 107, 157, 0.3)",
            hovertemplate="<b>%{x}</b><br>Drawdown: %{y:.2%}<extra></extra>",
        )
    )

    # Add annotation for maximum drawdown
    if max_dd_info:
        max_dd_pct = max_dd_info.get("pct", 0)
        max_dd_date = max_dd_info.get("end_date")

        if max_dd_date and max_dd_pct:
            fig.add_annotation(
                x=max_dd_date,
                y=max_dd_pct,
                text=f"Max DD: {max_dd_pct:.2%}",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#FF6B9D",
                bgcolor="rgba(45, 45, 45, 0.9)",
                bordercolor="#FF6B9D",
                borderwidth=2,
            )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        height=400,
    )

    fig.update_yaxes(tickformat=".1%")

    return _apply_simulor_theme(fig)


def plot_monthly_returns_heatmap(
    daily_returns: list[Decimal],
    timestamps: list[datetime],
    title: str = "Monthly Returns Heatmap",
) -> go.Figure:
    """Plot monthly returns heatmap in calendar style.

    Args:
        daily_returns: List of daily returns
        timestamps: List of timestamps (matching daily_returns)
        title: Chart title

    Returns:
        Plotly Figure with monthly returns heatmap
    """
    # Aggregate returns by month/year
    monthly_returns: dict[tuple[int, int], Decimal] = {}

    if not timestamps or len(timestamps) < 2:
        # Return empty figure if insufficient data
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data for monthly returns",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return _apply_simulor_theme(fig)

    # Build cumulative product for each month
    first_ts = timestamps[1]
    current_month_key: tuple[int, int] = (first_ts.year, first_ts.month)
    month_cumulative = Decimal("1.0")

    for i, ts in enumerate(timestamps[1:]):  # Skip first timestamp (no return)
        year = ts.year
        month = ts.month
        month_key = (year, month)

        if month_key != current_month_key:
            # New month - save previous and reset
            monthly_returns[current_month_key] = month_cumulative - 1
            current_month_key = month_key
            month_cumulative = Decimal("1.0")

        # Compound return for this month
        month_cumulative *= 1 + daily_returns[i]

    # Save last month
    monthly_returns[current_month_key] = month_cumulative - 1

    if not monthly_returns:
        # Return empty figure if no data
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data for monthly returns",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return _apply_simulor_theme(fig)

    # Create matrix (years as rows, months as columns)
    years = sorted({year for year, _ in monthly_returns})
    months = list(range(1, 13))
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    z_values = []
    hover_texts = []

    for year in years:
        year_row = []
        hover_row = []
        for month in months:
            ret = monthly_returns.get((year, month))
            year_row.append(ret if ret is not None else None)
            if ret is not None:
                hover_row.append(f"{month_names[month - 1]} {year}<br>{ret:.2%}")
            else:
                hover_row.append("")
        z_values.append(year_row)
        hover_texts.append(hover_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=month_names,
            y=[str(y) for y in years],
            colorscale="RdYlGn",
            zmid=0,
            text=hover_texts,
            hovertemplate="%{text}<extra></extra>",
            colorbar={"title": "Return", "tickformat": ".1%"},
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title="Year",
        height=max(300, len(years) * 40),
    )

    return _apply_simulor_theme(fig)


def plot_returns_distribution(
    returns: list[Decimal],
    title: str = "Returns Distribution",
    bins: int = 50,
) -> go.Figure:
    """Plot returns distribution histogram with normal curve overlay.

    Args:
        returns: List of returns
        title: Chart title
        bins: Number of histogram bins

    Returns:
        Plotly Figure with returns distribution
    """
    import math

    if not returns:
        fig = go.Figure()
        fig.add_annotation(
            text="No returns data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return _apply_simulor_theme(fig)

    # Calculate statistics
    mean = sum(returns) / Decimal(len(returns))
    variance = sum((r - mean) ** 2 for r in returns) / Decimal(len(returns) - 1)
    std_dev = variance.sqrt()

    # Calculate skewness and kurtosis
    n = len(returns)
    m3 = sum((r - mean) ** 3 for r in returns) / Decimal(n)
    m4 = sum((r - mean) ** 4 for r in returns) / Decimal(n)
    skew = m3 / (std_dev**3) if std_dev > 0 else 0
    kurt = (m4 / (std_dev**4)) - 3 if std_dev > 0 else 0

    fig = go.Figure()

    # Histogram of actual returns
    fig.add_trace(
        go.Histogram(
            x=returns,
            nbinsx=bins,
            name="Actual Returns",
            marker={"color": "#00D9FF", "line": {"color": "#007A99", "width": 1}},
            opacity=0.7,
            hovertemplate="Return: %{x:.2%}<br>Count: %{y}<extra></extra>",
        )
    )

    # Add normal distribution overlay
    if std_dev > 0:
        min_ret = min(returns)
        max_ret = max(returns)
        x_range = [min_ret + (max_ret - min_ret) * i / 200 for i in range(201)]

        # Normal PDF scaled to match histogram
        normal_y = [
            (len(returns) * float(max_ret - min_ret) / bins)
            * (1 / (float(std_dev) * math.sqrt(2 * math.pi)))
            * math.exp(-0.5 * (float((x - mean) / std_dev)) ** 2)
            for x in x_range
        ]

        fig.add_trace(
            go.Scatter(
                x=x_range,
                y=normal_y,
                mode="lines",
                name="Normal Distribution",
                line={"color": "#FF6B9D", "width": 2, "dash": "dash"},
                hovertemplate="Return: %{x:.2%}<extra></extra>",
            )
        )

    # Add statistics annotation
    stats_text = f"Mean: {mean:.2%}<br>Std Dev: {std_dev:.2%}<br>Skewness: {skew:.2f}<br>Kurtosis: {kurt:.2f}"

    fig.add_annotation(
        text=stats_text,
        xref="paper",
        yref="paper",
        x=0.98,
        y=0.98,
        xanchor="right",
        yanchor="top",
        showarrow=False,
        bgcolor="rgba(45, 45, 45, 0.8)",
        bordercolor="#444",
        borderwidth=1,
        borderpad=10,
    )

    fig.update_layout(
        title=title,
        xaxis_title="Daily Return",
        yaxis_title="Frequency",
        height=500,
        bargap=0.05,
    )

    fig.update_xaxes(tickformat=".1%")

    return _apply_simulor_theme(fig)
