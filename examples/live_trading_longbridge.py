"""Example: Live trading with Longbridge broker.

This example demonstrates live trading using real-time market data and
real order execution through Longbridge's API.

Requirements:
    - Longbridge OpenAPI account with trading permissions
    - longport package installed: pip install longport
    - Environment variables set:
        * LONGPORT_APP_KEY
        * LONGPORT_APP_SECRET
        * LONGPORT_ACCESS_TOKEN
    - Sufficient account balance for trading

⚠️ WARNING: This executes REAL TRADES with REAL MONEY!
    Test thoroughly with paper trading before running live.

Market data: US, HK, CN, SG stocks
Strategy: Simple moving average crossover
Execution: Real orders through Longbridge broker
"""

import logging
from decimal import Decimal

from longport.openapi import Config

from simulor.alpha import MovingAverageCrossover
from simulor.data.feeds import DataType
from simulor.engine import Engine
from simulor.execution import Immediate
from simulor.execution.live.longbridge import Longbridge
from simulor.portfolio import EqualWeight, Fund
from simulor.risk import PositionLimit
from simulor.strategy import Strategy
from simulor.types import Instrument
from simulor.universe import Static


def main() -> None:
    """Run live trading with Longbridge broker."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger(__name__)

    # ⚠️ Confirm user wants to run live trading
    logger.warning("=" * 60)
    logger.warning("⚠️  WARNING: LIVE TRADING MODE")
    logger.warning("=" * 60)
    logger.warning("This will execute REAL TRADES with REAL MONEY!")
    logger.warning("Make sure you have:")
    logger.warning("  1. Tested your strategy thoroughly in paper trading")
    logger.warning("  2. Set appropriate risk limits")
    logger.warning("  3. Sufficient account balance")
    logger.warning("=" * 60)

    response = input("Type 'YES' to confirm live trading: ")
    if response != "YES":
        logger.info("Live trading cancelled.")
        return

    # Define instruments to trade (conservative universe)
    instruments = [
        Instrument.stock("700", exchange="HK"),  # Tencent
        Instrument.stock("9988", exchange="HK"),  # Alibaba
    ]

    broker = Longbridge(config=Config.from_env())

    feed = broker.live_feed(
        instruments=instruments,
        data_types=[DataType.QUOTE, DataType.TRADE, DataType.DEPTH],
    )

    # Create strategy with conservative risk limits
    strategy = Strategy(
        name="MA_Crossover_Live",
        universe=Static(instruments),
        alpha=MovingAverageCrossover(fast_period=20, slow_period=50),
        construction=EqualWeight(),
        risk=PositionLimit(
            max_position=Decimal("0.1")  # Max 10% per position (conservative)
        ),
        execution=Immediate(),
    )

    # Create fund with strategy
    fund = Fund(
        strategies=[strategy],
        capital=Decimal("10000"),  # Start with small capital
    )

    # Create engine
    engine = Engine(
        data=feed,
        fund=fund,
        broker=broker,
    )

    # Run in LIVE mode
    logger.info("\n" + "=" * 60)
    logger.info("Starting LIVE TRADING...")
    logger.info("=" * 60)
    logger.info(f"Trading {len(instruments)} instruments")
    logger.info(f"Starting capital: ${fund.capital}")
    logger.info("Max position size: 10% per instrument")
    logger.info("=" * 60)
    logger.info("\nPress Ctrl+C to stop trading\n")

    try:
        result = engine.run(mode="live")
        logger.info("\n" + "=" * 60)
        logger.info("Live trading session completed")
        logger.info("=" * 60)
        logger.info(f"Final capital: ${result.final_capital}")
        logger.info(f"Total return: {result.total_return:.2%}")
        logger.info(f"Max drawdown: {result.max_drawdown:.2%}")

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Stopping live trading...")
        logger.info("=" * 60)
        logger.info("Engine will handle cleanup automatically")

    except Exception as e:
        logger.error(f"\n❌ Error during live trading: {e}")
        raise


if __name__ == "__main__":
    main()
