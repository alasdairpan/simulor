import heapq
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from simulor.core.connectors import Broker, SubmitOrderResult
from simulor.core.events import EventType, MarketEvent, SystemEvent
from simulor.execution.simulation.cost_models import CostModel
from simulor.execution.simulation.fill_models import FillModel, InstantFillModel
from simulor.execution.simulation.latency_model import ConstantLatencyModel, LatencyModel
from simulor.logging import get_logger
from simulor.types import Fill, Instrument, OrderSide, OrderSpec

logger = get_logger(__name__)


@dataclass(order=True)
class _DelayedOrder:
    """Internal wrapper to sort orders by arrival time (simulating latency)."""

    release_time: datetime

    # Fields below are excluded from sorting comparison
    strategy_name: str = field(compare=False)
    order_spec: OrderSpec = field(compare=False)
    order_id: str = field(compare=False)


class SimulatedBroker(Broker):
    """Simulated broker for executing orders and managing portfolio state.

    Responsibilities:
        - Execute orders based on market data
        - Update portfolio holdings and cash balance
        - Generate execution reports and fill events
    """

    def __init__(
        self,
        fill_model: FillModel | None = None,
        cost_model: CostModel | None = None,
        latency_model: LatencyModel | None = None,
    ) -> None:
        super().__init__()
        self._fill_model = fill_model or InstantFillModel()
        self._cost_model = cost_model or CostModel()
        self._latency_model = latency_model or ConstantLatencyModel(latency=0)

        # State: Network Simulation
        # Priority Queue for orders "in flight"
        self._latency_buffer: list[_DelayedOrder] = []

        # State: Exchange Matching Engine (The Order Book)
        # Orders that have arrived but waiting for price (Limit/Stop)
        self._open_orders: dict[str, OrderSpec] = {}

        # Order ID -> StrategyName (Routing Table)
        self._order_owners: dict[str, str] = {}

        # Instrument -> Set[Order ID] (Matching Optimization)
        self._orders_by_instrument: dict[Instrument, set[str]] = defaultdict(set)

        # State: Connection (Trivial in simulation)
        self._is_connected = False

        # Simulation Clock
        self._current_time = datetime.min.replace(tzinfo=ZoneInfo("UTC"))

    def connect(self) -> None:
        self._is_connected = True
        logger.info("SimulatedBroker connected.")

    def disconnect(self) -> None:
        self._is_connected = False
        logger.info("SimulatedBroker disconnected.")

    def is_connected(self) -> bool:
        return self._is_connected

    def register_order_update_callback(self) -> None:
        # In simulation, we don't need an external callback registration
        # because we publish fills directly to the bus ourselves.
        pass

    def submit_order(self, strategy_name: str, order_spec: OrderSpec) -> SubmitOrderResult:
        """Accept order from Strategy and put into Latency Buffer."""

        if not self._is_connected:
            raise RuntimeError("Cannot submit order: SimulatedBroker is not connected.")

        # Validate Strategy
        portfolio = self.strategy_portfolios.get(strategy_name)
        if not portfolio:
            raise ValueError(f"Strategy '{strategy_name}' is not registered with the broker.")

        # Generate ID
        order_id = str(uuid.uuid4())

        # Simulate Network Delay
        # The order effectively "arrives" at the exchange in the future
        release_time = self._current_time + self._latency_model.sample()

        delayed_order = _DelayedOrder(release_time, strategy_name, order_spec, order_id)

        # Push to Priority Queue
        heapq.heappush(self._latency_buffer, delayed_order)

        logger.info(
            f"Order {order_id} submitted by strategy '{strategy_name}' at {self._current_time}, arrives {release_time}"
        )

        return SubmitOrderResult(order_id=order_id)

    def cancel_order(self, strategy_name: str, order_id: str) -> None:
        """
        Attempt to cancel an order.
        """
        # Check Ownership
        owner = self._order_owners.get(order_id)
        if not owner:
            logger.warning(f"Order {order_id} not found for cancellation.")
            return
        if owner != strategy_name:
            logger.warning(f"Strategy '{strategy_name}' cannot cancel order {order_id} owned by '{owner}'.")
            return

        # Remove from Book
        if order_id in self._open_orders:
            order_spec = self._open_orders[order_id]
            self._remove_from_book(order_id, order_spec.instrument)
            logger.info(f"Order {order_id} canceled by strategy '{strategy_name}'")
        else:
            logger.warning(f"Order {order_id} not found in open orders for cancellation.")

    def _remove_from_book(self, order_id: str, instrument: Instrument) -> None:
        del self._open_orders[order_id]
        del self._order_owners[order_id]
        self._orders_by_instrument[instrument].remove(order_id)
        if not self._orders_by_instrument[instrument]:
            del self._orders_by_instrument[instrument]

    def on_market_event(self, event: MarketEvent) -> None:
        """
        Hook called by Engine for every market tick/bar.
        This drives the simulation logic.
        """
        self._current_time = event.time

        # Process Latency Buffer (Network Layer)
        # Move orders from "In Flight" to "At Exchange"
        self._process_latency_buffer()

        # Match Orders (Exchange Layer)
        # Check if any open orders can fill against new data
        self._match_orders(event)

    def _process_latency_buffer(self) -> None:
        """Releases orders that have completed their network travel time."""
        while self._latency_buffer:
            # Peek at the earliest arriving order
            if self._latency_buffer[0].release_time <= self._current_time:
                delayed_order = heapq.heappop(self._latency_buffer)

                # Move to Open Orders (The Exchange has received it)
                self._add_to_book(delayed_order)
                logger.debug(f"Order {delayed_order.order_id} arrived at exchange at {self._current_time}")
            else:
                # Next order arrives in the future
                break

    def _add_to_book(self, delayed_order: _DelayedOrder) -> None:
        """Register order in matching engine."""
        order_id = delayed_order.order_id
        spec = delayed_order.order_spec

        self._open_orders[order_id] = spec
        self._order_owners[order_id] = delayed_order.strategy_name
        self._orders_by_instrument[spec.instrument].add(order_id)

    def _match_orders(self, event: MarketEvent) -> None:
        active_instruments = event.instruments()

        for inst in active_instruments:
            if inst in self._orders_by_instrument:
                # Copy list to allow modification during iteration
                order_ids = list(self._orders_by_instrument[inst])
                for order_id in order_ids:
                    self._check_and_fill(order_id, event)

    def _check_and_fill(self, order_id: str, event: MarketEvent) -> None:
        """Check if an order can be filled and process the fill."""

        # Retrieve order spec and owner
        order_spec = self._open_orders[order_id]
        strategy_name = self._order_owners[order_id]
        strategy_portfolio = self.strategy_portfolios[strategy_name]

        # Determine fill price
        fill_price = self._fill_model.get_fill_price(order_spec, event)
        if fill_price is None:
            logger.warning(
                f"Order {order_id} for {order_spec.instrument.display_name} cannot be filled at {event.time}"
            )
            return

        # Calculate total commission
        commission = self._cost_model.calculate_total_cost(
            quantity=order_spec.quantity,
            price=fill_price,
        )

        # Check if there's enough cash for buy orders (prevent negative cash)
        if order_spec.side == OrderSide.BUY:
            cost = order_spec.quantity * fill_price + commission
            if cost > strategy_portfolio.cash:
                logger.warning(
                    "Insufficient cash for %s: need $%s, have $%s (strategy=%s)",
                    order_spec.instrument.display_name,
                    cost,
                    strategy_portfolio.cash,
                    strategy_name,
                )
                raise ValueError(
                    f"Insufficient cash for {order_spec.instrument.display_name}: "
                    f"need {cost}, have {strategy_portfolio.cash}"
                )
        else:  # SELL order
            # Check if trying to sell more than owned
            current_position = strategy_portfolio.positions.get(order_spec.instrument)
            current_qty = current_position.quantity if current_position else Decimal("0")
            if order_spec.quantity > current_qty:
                logger.warning(
                    "Insufficient shares to sell %s: trying to sell %s, have %s (strategy=%s)",
                    order_spec.instrument.display_name,
                    order_spec.quantity,
                    current_qty,
                    strategy_name,
                )
                raise ValueError(
                    f"Insufficient shares to sell {order_spec.instrument.display_name}: "
                    f"trying to sell {order_spec.quantity}, have {current_qty}"
                )

        # Create signed quantity (positive for buy, negative for sell)
        signed_quantity = order_spec.quantity if order_spec.side == OrderSide.BUY else -order_spec.quantity

        # Create fill
        fill = Fill(
            instrument=order_spec.instrument,
            quantity=signed_quantity,
            price=fill_price,
            commission=commission,
        )

        # Update strategy portfolio and record state
        strategy_portfolio.update_position(fill)
        strategy_portfolio.record_state(timestamp=event.time)

        # Cleanup Book
        self._remove_from_book(order_id, order_spec.instrument)

        # Publish Event
        self.event_bus.publish(
            event=SystemEvent(
                type=EventType.FILL,
                time=event.time,
                payload={
                    "strategy_name": strategy_name,
                    "fill": fill,
                },
            ),
        )

        # Log trade execution
        logger.info(
            "Executed trade: %s %s %s @ $%s, commission=$%s (strategy=%s)",
            order_spec.side.name,
            abs(signed_quantity),
            order_spec.instrument.display_name,
            fill_price,
            commission,
            strategy_name,
        )

    # TODO: Make it ana abstract method for Broker
    def get_cash_balance(self) -> Decimal:
        """Get the total cash balance across all strategies and unallocated cash.

        Returns:
            Total cash balance = unallocated cash + sum of all strategy portfolio cash
        """
        # Start with unallocated cash in global portfolio
        total = self.global_portfolio.cash

        # Add cash from all strategy portfolios
        for strategy_portfolio in self.strategy_portfolios.values():
            total += strategy_portfolio.cash

        return total

    # TODO: Make it an abstract method for Broker
    def get_equity(self) -> Decimal:
        """Get the total equity (net liquidation value) across all strategies.

        Returns:
            Total equity = unallocated cash + sum of all strategy portfolio values
        """
        # Start with unallocated cash in global portfolio
        total = self.global_portfolio.cash

        # Add cash and position values from all strategy portfolios
        for strategy_portfolio in self.strategy_portfolios.values():
            total += strategy_portfolio.total_value

        return total

    def sync_global_portfolio(self, timestamp: datetime) -> None:
        """Synchronize global portfolio with strategy portfolios.

        Aggregates all strategy portfolio states into the global portfolio.
        Global portfolio tracks:
        - Unallocated cash (capital not allocated to strategies)
        - Aggregate positions across all strategies
        - Aggregate trades from all strategies
        - Total portfolio value

        This should be called after processing each market event to ensure
        global portfolio positions have up-to-date current_price values.

        Args:
            timestamp: Timestamp of the sync operation (for snapshot recording)
        """
        # Reset global portfolio positions and trades (will rebuild from strategies)
        self._global_portfolio._positions.clear()
        self._global_portfolio.trades.clear()

        # Aggregate positions and trades from all strategy portfolios
        for strategy_portfolio in self._strategy_portfolios.values():
            # Aggregate trades
            self._global_portfolio.trades.extend(strategy_portfolio.trades)

            # Aggregate positions
            for instrument, position in strategy_portfolio.positions.items():
                if instrument not in self._global_portfolio._positions:
                    # Import Position here to avoid circular import
                    from simulor.portfolio.position import Position

                    self._global_portfolio._positions[instrument] = Position(instrument=instrument)

                global_pos = self._global_portfolio._positions[instrument]

                # Aggregate quantities (average cost basis recalculated)
                if global_pos.quantity == 0:
                    # First position for this instrument
                    global_pos.quantity = position.quantity
                    global_pos.average_cost = position.average_cost
                else:
                    # Combine with existing position
                    total_cost = (
                        global_pos.quantity * global_pos.average_cost + position.quantity * position.average_cost
                    )
                    global_pos.quantity += position.quantity

                    if global_pos.quantity != 0:
                        global_pos.average_cost = total_cost / global_pos.quantity

                # Update current price
                if position.current_price is not None:
                    global_pos.current_price = position.current_price

        # Clean up zero positions
        zero_instruments = [inst for inst, pos in self._global_portfolio._positions.items() if pos.quantity == 0]
        for inst in zero_instruments:
            del self._global_portfolio._positions[inst]

        # Record snapshot after sync
        self._global_portfolio.recorder.record_snapshot(
            timestamp=timestamp,
            equity=self.get_equity(),
            cash=self.get_cash_balance(),
            positions=dict(self._global_portfolio._positions),
        )
