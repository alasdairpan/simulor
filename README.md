# Simulor

Simulor is a sophisticated backtesting framework designed for quantitative traders and researchers who demand institutional-grade realism and performance. Built on an event-driven architecture with pluggable components, it seamlessly transitions from historical backtesting to paper trading and live execution.

## Key Features

- **Event-Driven Architecture**: True event-driven simulation with point-in-time data delivery, multiple resolutions (tick/minute/hour/daily), and compositional data structures
- **Pluggable Strategy Components**: Modular alpha models, portfolio construction, risk management, execution models, and universe selection. Swap components without rewriting strategy logic
- **Institutional-Grade Execution**: Realistic fill models, transaction costs (commissions, spreads, slippage, market impact), T+0 settlement, and corporate actions handling
- **Comprehensive Analytics**: Performance metrics (Sharpe, Sortino, Calmar), risk analysis (VaR, CVaR, beta), trade statistics, and interactive Plotly visualizations
- **Environment Parity**: Same strategy code runs in backtest, paper trading, and live execution modes. Seamless transition from research to production

## Installation

```bash
pip install simulor
```

## Quick Start

```python
from decimal import Decimal
from pathlib import Path
from simulor import (
    Strategy, Engine, Fund,
    MovingAverageCrossover, EqualWeight, PositionLimit, Immediate, Static,
    CsvFeed, SimulatedBroker, Resolution, Instrument, Tearsheet
)

# Define strategy with pluggable components
# Workflow: Universe Selection -> Alpha Model -> Portfolio Construction -> Risk Management -> Execution
strategy = Strategy(
    name='MA_Crossover',
    universe=Static([
        Instrument.stock('SPY'),
        Instrument.stock('QQQ'),
        Instrument.stock('IWM')
    ]),
    alpha=MovingAverageCrossover(fast_period=10, slow_period=20),
    construction=EqualWeight(),
    risk=PositionLimit(max_position=Decimal('0.1')),
    execution=Immediate()
)

# Run backtest
engine = Engine(
    data=CsvFeed(path=Path('data/bars.csv'), resolution=Resolution.DAILY),
    fund=Fund(
        strategies=[strategy],  # Add more strategies as needed
        capital=Decimal('100000')
    ),
    broker=SimulatedBroker()
)
results = engine.run(
    start='2020-01-01',
    end='2025-12-31',
    mode='backtest'
)

# Analyze results
print(f"Total Return: {results.total_return:.2%}")
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")

# Generate tearsheet
tearsheet = Tearsheet(results)
tearsheet.save('tearsheet.html')
```

## Roadmap

### v0.1.0

- [x] Event-driven engine with CSV data provider
- [x] Pluggable strategy framework
- [x] Basic execution (InstantFill, SpreadFill)
- [x] Core analytics (returns, Sharpe, drawdown)
- [ ] Simple transaction costs

### v0.2.0+ (Planned)

- [ ] Parquet data provider and advanced data layer features
- [ ] History API with type-safe lookback
- [ ] Advanced fill models (L2 matching, probabilistic)
- [ ] T+2 settlement and realistic cash management
- [ ] Overfitting detection (WFA, PBO, CSCV)
- [ ] Advanced analytics (execution quality, attribution)
- [ ] ML integration and model registry
- [ ] Broker integrations for live trading

## Acknowledgments

Simulor implements the industry-standard modular pipeline architecture (Universe Selection → Alpha Generation → Portfolio Construction → Risk Management → Execution). This separation of concerns allows for maximum flexibility, testability, and maintainability, similar to the architecture found in institutional quantitative systems and platforms like Lean.

## Contributing

Contributions are welcome!

## License

This project is licensed under the [MIT License](LICENSE).
