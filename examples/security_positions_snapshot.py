"""Security positions snapshot example.

Runs a small backtest and prints broker-level security positions using the
unified `get_security_positions()` API.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from simulor.alpha.models import MovingAverageCrossover
from simulor.data.csv_feed import CsvFeed
from simulor.engine import Engine
from simulor.execution import Immediate
from simulor.execution.simulation.broker import SimulatedBroker
from simulor.portfolio import EqualWeight, Fund
from simulor.risk import PositionLimit
from simulor.strategy import Strategy
from simulor.types import Instrument, Resolution
from simulor.universe import Static


def main() -> None:
    broker = SimulatedBroker()

    strategy = Strategy(
        name="snapshot_demo",
        universe=Static([Instrument.stock("AAPL"), Instrument.stock("MSFT")]),
        alpha=MovingAverageCrossover(fast_period=5, slow_period=10),
        construction=EqualWeight(),
        risk=PositionLimit(max_position=Decimal("0.6")),
        execution=Immediate(),
    )

    engine = Engine(
        data=CsvFeed(path=Path("examples/data/daily_trade_bars.csv"), resolution=Resolution.DAILY),
        fund=Fund(strategies=[strategy], capital=Decimal("100000")),
        broker=broker,
    )

    engine.run(start="2024-01-01 00:00:00", end="2024-12-31 23:59:59", mode="backtest")

    print("Security positions:")
    for pos in broker.get_security_positions():
        print(
            f"- {pos.instrument.display_name}: qty={pos.quantity}, "
            f"cost={pos.cost_price}, mv={pos.market_value}, upnl={pos.unrealized_pnl}"
        )


if __name__ == "__main__":
    main()
