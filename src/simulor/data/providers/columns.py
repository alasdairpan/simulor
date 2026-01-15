"""Column name definitions and data type detection sets.

Shared constants for CSV, Parquet, and other tabular data providers.
"""

from simulor.types import ColumnName

__all__ = [
    "TRADE_BAR_COLUMNS",
    "TRADE_TICK_COLUMNS",
    "QUOTE_TICK_COLUMNS",
    "QUOTE_BAR_COLUMNS",
]

# CSV column name sets for data type detection
TRADE_BAR_COLUMNS = frozenset(
    {
        ColumnName.OPEN,
        ColumnName.HIGH,
        ColumnName.LOW,
        ColumnName.CLOSE,
        ColumnName.VOLUME,
    }
)

TRADE_TICK_COLUMNS = frozenset(
    {
        ColumnName.PRICE,
        ColumnName.SIZE,
    }
)

QUOTE_TICK_COLUMNS = frozenset(
    {
        ColumnName.BID_PRICE,
        ColumnName.BID_SIZE,
        ColumnName.ASK_PRICE,
        ColumnName.ASK_SIZE,
    }
)

QUOTE_BAR_COLUMNS = frozenset(
    {
        ColumnName.BID_OPEN,
        ColumnName.BID_HIGH,
        ColumnName.BID_LOW,
        ColumnName.BID_CLOSE,
        ColumnName.ASK_OPEN,
        ColumnName.ASK_HIGH,
        ColumnName.ASK_LOW,
        ColumnName.ASK_CLOSE,
    }
)
