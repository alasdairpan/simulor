# Logging

Simulor uses Python's standard `logging` module, following library best practices. By default, Simulor is completely silent (using `NullHandler`), giving you full control over logging configuration using standard Python logging APIs.

## Philosophy

The logging system is built on several core principles:

1. **Standard Python Logging**: Uses the standard `logging` module - no custom APIs to learn
2. **Library-Friendly Design**: Silent by default with `NullHandler`, respecting the user's logging configuration
3. **Hierarchical Organization**: Logger names mirror the module structure (`simulor.engine`, `simulor.portfolio`, etc.)
4. **Structured Context**: All logs include relevant context (strategy name, timestamp, instrument) for debugging
5. **Performance-Conscious**: Lazy evaluation and guarded expensive operations ensure minimal overhead
6. **Reproducibility**: Critical decisions and state changes are logged to support audit trails

## Quick Start

```python
import logging
import simulor

# Configure Python's logging for Simulor
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

# Now run your backtest - you'll see important events logged
engine = simulor.Engine(...)
result = engine.run(...)
```

## Logger Hierarchy

Simulor uses a hierarchical logger structure that mirrors the module organization:

```text
simulor                          # Root logger
├── simulor.engine               # Event loop orchestration
├── simulor.data                 # Data providers and subscriptions
│   ├── simulor.data.providers   # CSV, Parquet, API providers
│   └── simulor.data.market_store # Historical data management
├── simulor.universe             # Universe selection
├── simulor.alpha                # Signal generation
├── simulor.portfolio            # Portfolio construction & tracking
├── simulor.risk                 # Risk management
├── simulor.allocation           # Capital allocation
├── simulor.execution            # Order execution and fills
│   ├── simulor.execution.broker # Broker-specific events
│   └── simulor.execution.fills  # Order fill details
└── simulor.analytics            # Performance analysis
```

This hierarchy enables targeted debugging using standard Python logging. For example, to debug execution issues:

```python
import logging

# Set global level
logging.basicConfig(level=logging.WARNING)

# Enable DEBUG only for execution module
logging.getLogger('simulor.execution').setLevel(logging.DEBUG)
```

## Usage Examples

### Development: Verbose Logging

During strategy development, enable detailed logging to understand every decision:

```python
import logging
from simulor import Engine, Strategy
from simulor.alpha.models import MovingAverageCrossover
# ... other imports

# Enable comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/ma_crossover_debug.log')
    ]
)

strategy = Strategy(...)
engine = Engine(...)
result = engine.run(start="2020-01-01", end="2024-12-31")

# You'll see detailed logs of:
# - Every signal generated
# - Every target position calculated
# - Every order created and executed
# - Every portfolio update
```

### Production Backtest: Important Events Only

For production backtests, log important events without overwhelming output:

```python
import logging

# Balanced logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/production_backtest.log')
    ]
)

# Run your backtest - logs will show:
# - Initialization details
# - Trades executed
# - Warnings about issues
# - Final results
```

### Targeted Debugging: Specific Module

Debug execution issues without noise from other modules:

```python
import logging

# Global default: WARNING
logging.basicConfig(level=logging.WARNING)

# Only execution layer is verbose
logging.getLogger('simulor.execution').setLevel(logging.DEBUG)
logging.getLogger('simulor.execution.broker').setLevel(logging.DEBUG)

# You'll see detailed execution logs but minimal output from other modules
```

### File-Only Logging: No Console Output

For automated runs where you don't want console spam:

```python
import logging

# Only log to file, not console
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/errors.log')
    ]
)
```

### Structured Logging for Log Aggregation

For production environments with centralized logging (ELK, Splunk, Datadog):

```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'logger': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
        }
        return json.dumps(log_data)

handler = logging.FileHandler('logs/structured.jsonl')
handler.setFormatter(JsonFormatter())

logger = logging.getLogger('simulor')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Logs can be directly ingested by log aggregation systems
```

### Multi-Strategy Portfolio Debugging

When running multiple strategies, isolate logs for specific strategies:

```python
import logging

# Base configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

# Detailed alpha logs
logging.getLogger('simulor.alpha').setLevel(logging.DEBUG)

# Detailed risk management
logging.getLogger('simulor.risk').setLevel(logging.DEBUG)

# Detailed execution for all strategies
logging.getLogger('simulor.execution').setLevel(logging.DEBUG)

# Each strategy's decisions are logged with context
```
