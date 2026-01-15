"""CSV data provider implementation.

Loads market data from CSV files with automatic symbol parsing and
chronological ordering using heap-based merge-sort algorithm.
"""

from __future__ import annotations

import csv
import heapq
import warnings
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from simulor.core.events import MarketEvent
from simulor.data.providers.base import DataProvider
from simulor.data.providers.columns import (
    QUOTE_BAR_COLUMNS,
    QUOTE_TICK_COLUMNS,
    TRADE_BAR_COLUMNS,
    TRADE_TICK_COLUMNS,
)
from simulor.logging import get_logger
from simulor.types import (
    ColumnName,
    Instrument,
    MarketData,
    QuoteBar,
    QuoteTick,
    Resolution,
    TradeBar,
    TradeTick,
)

# Create module logger
logger = get_logger(__name__)


class CSVDataProvider(DataProvider):
    """Load market data from CSV files.

    Supports both single CSV files and directories containing multiple CSV files.
    Uses merge-sort algorithm to maintain chronological ordering across multiple files.

    CSV Format Requirements:
    - Header row with column names
    - timestamp column (ISO format, Unix epoch seconds/milliseconds, or datetime)
    - symbol column (required - identifies the instrument)
    - Optional: instrument_type column (STOCK, FUTURE, OPTION, CRYPTO, FOREX, etc.)

    Timezone Handling:
    - All timestamps are localized to the specified timezone parameter
    - Naive timestamps (without timezone info) are assumed to be in the specified timezone
    - Timezone-aware timestamps in CSV are converted to the specified timezone
    - Default timezone is UTC

    Supported Data Types:
    - Trade bars: open, high, low, close, volume columns
    - Trade ticks: price, size columns
    - Quote ticks: bid_price, bid_size, ask_price, ask_size columns
    - Quote bars: bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close columns

    Example CSV:
        timestamp,symbol,open,high,low,close,volume
        2024-01-02 09:30:00,AAPL,150.00,150.50,149.80,150.20,1000000
        2024-01-02 09:30:00,MSFT,370.00,371.00,369.50,370.50,800000
        2024-01-02 14:30:00,AAPL,150.20,151.00,150.10,150.90,850000

    Args:
        path: Path to CSV file or directory containing CSV files
        resolution: Resolution for bar data (default: Resolution.DAILY)
        date_column: Name of the timestamp column (default: "timestamp")
        symbol_column: Name of the symbol column (default: "symbol", required in all CSV files)
        instrument_type_column: Name of instrument type column (default: "instrument_type", optional)
        timezone: Timezone for timestamps - all timestamps will be localized to this timezone (default: "UTC")

    Example:
        >>> # Load from directory
        >>> provider = CSVDataProvider(path='data/')
        >>> # Load from single file
        >>> provider = CSVDataProvider(path='data/market_data.csv')
    """

    def __init__(
        self,
        path: Path | str,
        resolution: Resolution,
        date_column: str = "timestamp",
        symbol_column: str = "symbol",
        instrument_type_column: str = "instrument_type",
        timezone: str = "UTC",
    ):
        """Initialize CSV data provider.

        Args:
            path: Path to CSV file or directory
            resolution: Resolution for bar data
            date_column: Name of timestamp column
            symbol_column: Name of symbol column (required in all CSV files)
            instrument_type_column: Name of instrument type column (optional)
            timezone: Timezone for timestamps
        """
        logger.debug("Initializing CSVDataProvider with path=%s, timezone=%s", path, timezone)

        self.data_path = Path(path)
        self.resolution = resolution
        self.date_column = date_column
        self.symbol_column = symbol_column
        self.instrument_type_column = instrument_type_column
        self.timezone_info = ZoneInfo(timezone)

        if not self.data_path.exists():
            logger.error("Path not found: %s", path)
            raise FileNotFoundError(f"Path not found: {path}")

        # Detect if single file or directory
        if self.data_path.is_file():
            self._files = [self.data_path]
            logger.info("Loaded single CSV file: %s", self.data_path)
        elif self.data_path.is_dir():
            self._files = sorted(self.data_path.glob("*.csv"))
            if not self._files:
                logger.error("No CSV files found in directory: %s", path)
                raise ValueError(f"No CSV files found in directory: {path}")
            logger.info("Loaded %d CSV files from directory: %s", len(self._files), self.data_path)
        else:
            logger.error("Invalid path: %s", path)
            raise ValueError(f"Invalid path: {path}")

    def __iter__(self) -> Iterator[MarketEvent]:
        """Return a new iterator for CSV data.

        Returns:
            New CSVDataIterator instance
        """
        return CSVDataIterator(provider=self)

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp from string and localize to configured timezone.

        Supports multiple formats:
        - ISO format: 2024-01-02 09:30:00, 2024-01-02 09:30:00.123456
        - ISO with T: 2024-01-02T09:30:00, 2024-01-02T09:30:00Z
        - Date only: 2024-01-02
        - Unix epoch seconds: 1704189000
        - Unix epoch milliseconds: 1704189000000

        Timezone handling:
        - Naive timestamps (no timezone info) are localized to self.timezone_info
        - Timezone-aware timestamps are converted to self.timezone_info
        - Unix timestamps are assumed to be UTC and converted to self.timezone_info

        Args:
            timestamp_str: Timestamp string

        Returns:
            Timezone-aware datetime object in configured timezone

        Raises:
            ValueError: If timestamp format not recognized
        """
        timestamp_str = timestamp_str.strip()

        # Try Unix epoch (numeric only) - these are always UTC
        if timestamp_str.replace(".", "").isdigit():
            try:
                timestamp_float = float(timestamp_str)
                # If value > 1e10, assume milliseconds
                if timestamp_float > 1e10:
                    timestamp_float /= 1000
                # fromtimestamp with tz parameter creates timezone-aware datetime
                return datetime.fromtimestamp(timestamp_float, tz=self.timezone_info)
            except (ValueError, OSError):
                pass

        # Try ISO format (handles both space and T separator, with/without timezone)
        try:
            dt = datetime.fromisoformat(timestamp_str)
            # If naive, localize to configured timezone
            if dt.tzinfo is None:
                return dt.replace(tzinfo=self.timezone_info)
            # If already timezone-aware, convert to configured timezone
            else:
                return dt.astimezone(self.timezone_info)
        except ValueError:
            pass

        # Try date only
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d")
            # Localize to configured timezone
            return dt.replace(tzinfo=self.timezone_info)
        except ValueError:
            pass

        raise ValueError(f"Could not parse timestamp: {timestamp_str}")


class CSVDataIterator:
    """Iterator for CSV data files.

    Uses heap-based merge-sort to efficiently merge multiple CSV files
    and yield events in chronological order. This ensures proper
    point-in-time simulation without look-ahead bias.

    Algorithm:
    1. Open all CSV files in the specified path
    2. Read first row from each file and add to min-heap
    3. Use min-heap to track earliest timestamp across all files
    4. Yield earliest event, advance that file's reader
    5. Repeat until all files exhausted

    Supports multiple data types (trade bars, trade ticks, quote ticks, quote bars)
    by detecting format from available columns in the CSV file.
    """

    def __init__(self, provider: CSVDataProvider):
        """Initialize CSV data iterator.

        Args:
            provider: CSVDataProvider instance
        """
        self.provider = provider

        # Open readers for each file
        self._file_handles: list[Any] = []
        self._readers: dict[str, csv.DictReader[str]] = {}
        # Min-heap of (timestamp, counter, symbol, row, reader_key)
        # Counter is used to break ties when timestamps are equal
        # reader_key identifies which reader this row came from
        self._heap: list[tuple[datetime, int, str, dict[str, str], str]] = []
        self._counter = 0  # Monotonic counter for heap ordering
        self._warned_missing_type_column = False  # Track if we warned about missing column
        self._has_type_column = False  # Will be set during reader initialization

        self._initialize_readers()

    def _initialize_readers(self) -> None:
        """Open CSV readers for each file and initialize heap.

        All CSV files must have a symbol column to be processed.
        Files without symbol column are rejected.
        """
        for file_path in self.provider._files:
            # Open file (kept open for iteration, closed in __del__)
            f = open(file_path)  # noqa: SIM115
            self._file_handles.append(f)
            reader = csv.DictReader(f)

            # Check if file has required symbol column
            fieldnames = reader.fieldnames or []
            if self.provider.symbol_column not in fieldnames:
                # File doesn't have symbol column - reject it
                f.close()
                self._file_handles.remove(f)
                raise ValueError(f"CSV file {file_path} missing required column '{self.provider.symbol_column}'")

            # Check for instrument_type column (first file sets the flag)
            if not self._warned_missing_type_column:
                self._has_type_column = self.provider.instrument_type_column in fieldnames
                if not self._has_type_column:
                    warnings.warn(
                        f"CSV file '{file_path}' missing '{self.provider.instrument_type_column}' column. "
                        f"Inferring instrument types from symbol format. "
                        f"Add '{self.provider.instrument_type_column}' column for explicit control.",
                        UserWarning,
                        stacklevel=4,
                    )
                    self._warned_missing_type_column = True

            # File is valid - initialize reader
            reader_key = str(file_path)
            self._readers[reader_key] = reader
            self._advance_reader(reader_key)

    def _advance_reader(self, file_key: str) -> None:
        """Read next row from a CSV file and add to heap if valid.

        Args:
            file_key: File path used as reader key
        """
        if file_key not in self._readers:
            return

        reader = self._readers[file_key]

        try:
            row = next(reader)

            # Extract symbol from the row
            symbol = row.get(self.provider.symbol_column, "")
            if not symbol:
                # Skip rows without symbol, try next row
                self._advance_reader(file_key)
                return

            timestamp = self.provider._parse_timestamp(row[self.provider.date_column])

            # Add all rows to heap - no filtering
            heapq.heappush(self._heap, (timestamp, self._counter, symbol, row, file_key))
            self._counter += 1
        except StopIteration:
            # Reader exhausted, remove it
            del self._readers[file_key]

    def __iter__(self) -> Iterator[MarketEvent]:
        """Return iterator."""
        return self

    def __next__(self) -> MarketEvent:
        """Get next chronological event using heap-based merge.

        Accumulates all rows with identical timestamps into a single MarketEvent,
        using pre-sorted buckets for efficient access.

        Returns:
            Next MarketEvent containing bundled same-timestamp data

        Raises:
            StopIteration: When no more data available
        """
        # Create new event for current timestamp
        current_event: MarketEvent | None = None
        current_timestamp: datetime | None = None

        while self._heap:
            # Peek at earliest event
            timestamp, counter, symbol, row, reader_key = heapq.heappop(self._heap)  # noqa: F841

            # Advance the reader that yielded this row
            if reader_key in self._readers:
                self._advance_reader(reader_key)

            # Convert row to MarketData
            try:
                market_data = self._row_to_market_data(symbol, timestamp, row, self.provider.resolution)
            except (KeyError, ValueError):
                # Skip invalid rows and continue
                continue

            # Check if this row has same timestamp as current batch
            if current_timestamp is None:
                current_timestamp = timestamp
                current_event = MarketEvent(time=timestamp)
                current_event.add(market_data)
            elif timestamp == current_timestamp:
                # Same timestamp - add to current event
                current_event.add(market_data)  # type: ignore
            else:
                # Different timestamp - push back to heap and yield current batch
                heapq.heappush(self._heap, (timestamp, counter, symbol, row, reader_key))
                return current_event  # type: ignore

        # Heap exhausted - yield final batch if we have data
        if current_event is not None and current_timestamp is not None:
            return current_event

        # No more data
        raise StopIteration

    def _row_to_market_data(
        self,
        symbol: str,
        timestamp: datetime,
        row: dict[str, str],
        resolution: Resolution,
    ) -> MarketData:
        """Convert CSV row to MarketData instance.

        Detects data type from available columns and creates appropriate
        TradeTick, QuoteTick, TradeBar, or QuoteBar instance.

        Args:
            symbol: Symbol for this row
            timestamp: Parsed timestamp
            row: CSV row as dictionary

        Returns:
            MarketData instance (TradeTick, QuoteTick, TradeBar, or QuoteBar)

        Raises:
            KeyError: If required columns missing
            ValueError: If data validation fails
        """
        # Create instrument with type from CSV or inferred from symbol
        instrument = self._create_instrument(symbol, row)

        # Detect data type from available columns
        columns = set(row.keys())

        # Check for trade bar data (OHLCV)
        if TRADE_BAR_COLUMNS.issubset(columns):
            return TradeBar(
                timestamp=timestamp,
                instrument=instrument,
                resolution=resolution,
                open=Decimal(row[ColumnName.OPEN]),
                high=Decimal(row[ColumnName.HIGH]),
                low=Decimal(row[ColumnName.LOW]),
                close=Decimal(row[ColumnName.CLOSE]),
                volume=Decimal(row[ColumnName.VOLUME]),
            )
        # Check for trade tick data
        elif TRADE_TICK_COLUMNS.issubset(columns):
            return TradeTick(
                timestamp=timestamp,
                instrument=instrument,
                resolution=Resolution.TICK,
                price=Decimal(row[ColumnName.PRICE]),
                size=Decimal(row[ColumnName.SIZE]),
            )
        # Check for quote tick data
        elif QUOTE_TICK_COLUMNS.issubset(columns):
            return QuoteTick(
                timestamp=timestamp,
                instrument=instrument,
                resolution=Resolution.TICK,
                bid_price=Decimal(row[ColumnName.BID_PRICE]),
                bid_size=Decimal(row[ColumnName.BID_SIZE]),
                ask_price=Decimal(row[ColumnName.ASK_PRICE]),
                ask_size=Decimal(row[ColumnName.ASK_SIZE]),
            )
        # Check for quote bar data
        elif QUOTE_BAR_COLUMNS.issubset(columns):
            return QuoteBar(
                timestamp=timestamp,
                instrument=instrument,
                resolution=resolution,
                bid_open=Decimal(row[ColumnName.BID_OPEN]),
                bid_high=Decimal(row[ColumnName.BID_HIGH]),
                bid_low=Decimal(row[ColumnName.BID_LOW]),
                bid_close=Decimal(row[ColumnName.BID_CLOSE]),
                ask_open=Decimal(row[ColumnName.ASK_OPEN]),
                ask_high=Decimal(row[ColumnName.ASK_HIGH]),
                ask_low=Decimal(row[ColumnName.ASK_LOW]),
                ask_close=Decimal(row[ColumnName.ASK_CLOSE]),
            )
        else:
            raise ValueError(f"Cannot determine data type from columns: {columns}")

    def _create_instrument(self, symbol: str, row: dict[str, str]) -> Instrument:
        """Create instrument from symbol and optional type column.

        Uses industry-standard symbol formats to extract metadata:
        - OCC options: AAPL240119C00150000
        - CME futures: ESZ24, CLF25
        - Forex: EUR/USD
        - Crypto: BTC-USD

        Falls back to explicit instrument_type column if parsing fails.

        Args:
            symbol: Instrument symbol
            row: CSV row containing optional instrument_type column

        Returns:
            Instrument instance
        """

        _ = row

        # Create appropriate instrument type using parsed metadata
        # TODO: Support more asset types as needed
        return Instrument.stock(symbol)

    def __del__(self) -> None:
        """Close file handles on cleanup."""
        for f in self._file_handles:
            f.close()
