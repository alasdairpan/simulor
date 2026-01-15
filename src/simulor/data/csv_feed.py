from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from simulor.core.events import EndOfStreamEvent
from simulor.core.protocols import Feed
from simulor.data.providers.csv import CSVDataProvider
from simulor.logging import get_logger
from simulor.types import Resolution

logger = get_logger(__name__)


class CsvFeed(Feed):
    """Feed that publishes market events from CSV files.

    Uses `CSVDataProvider` to read CSV file(s) and publishes each
    `MarketEvent` to the configured event bus via `publish_event()`.
    """

    def __init__(
        self,
        path: Path | str,
        resolution: Resolution,
        date_column: str = "timestamp",
        symbol_column: str = "symbol",
        instrument_type_column: str = "instrument_type",
        timezone: str = "UTC",
    ) -> None:
        """Initialize the CSV feed.

        Sets up the underlying CSVDataProvider to read appropriate files and columns.

        Args:
            path: Path to the CSV file or directory containing CSV files.
            resolution: The time resolution of the data (e.g., MINUTE, DAILY).
            date_column: Name of the column containing timestamps. Defaults to "timestamp".
            symbol_column: Name of the column containing symbols. Defaults to "symbol".
            instrument_type_column: Name of the column containing instrument types.
                Defaults to "instrument_type".
            timezone: Timezone of the timestamps in the CSV. Defaults to "UTC".
        """
        self._provider = CSVDataProvider(
            path=path,
            resolution=resolution,
            date_column=date_column,
            symbol_column=symbol_column,
            instrument_type_column=instrument_type_column,
            timezone=timezone,
        )
        self._running = False
        self._last_timestamp: datetime | None = None

    def start(self) -> None:
        """Start the feed.

        Initializes the feed and prepares it for event publishing.
        Calls the superclass `start` method to handle any base initialization.
        """
        logger.debug("Starting CsvFeed, publishing market events from CSV files")
        return super().start()

    def run(self) -> None:
        """Run the feed loop.

        Iterates through the `CSVDataProvider` to retrieve `MarketEvent`s and publishes
        them to the event bus. It continues until the provider is exhausted or `stop()`
        is called.

        When the feed finishes (or is stopped), it publishes an `EndOfStreamEvent`.
        """
        self._running = True
        try:
            for market_event in self._provider:
                if not self._running:
                    break
                try:
                    # `market_event` is a MarketEvent (subclass of DataEvent)
                    self.publish_event(market_event)
                    self._last_timestamp = market_event.time
                except Exception:
                    logger.exception(
                        "Failed to publish market event at %s",
                        market_event.time,
                    )
        except Exception:
            logger.exception("CsvFeed run loop terminated with exception")
        finally:
            self._running = False

        self.publish_event(
            EndOfStreamEvent(
                time=self._last_timestamp or datetime.now(tz=ZoneInfo("UTC")),
                reason="End of CSV data stream",
            )
        )

    def stop(self) -> None:
        """Stop the feed run loop.

        Sets the internal running flag to False, which will cause the `run` loop
        to terminate on the next iteration.
        """
        self._running = False
