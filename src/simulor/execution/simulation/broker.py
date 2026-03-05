import heapq
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from simulor.core.assets import AccountBalance, CashInfo, RiskLevel, StockPosition
from simulor.core.connectors import Broker, SubmitOrderResult
from simulor.core.events import EventType, MarketEvent, SystemEvent
from simulor.execution.simulation.cost_models import CostModel
from simulor.execution.simulation.fill_models import FillModel, InstantFillModel
from simulor.execution.simulation.latency_model import ConstantLatencyModel, LatencyModel
from simulor.logging import get_logger
from simulor.types import Fill, Instrument, OrderSide, OrderSpec

logger = get_logger(__name__)

__all__ = ["SimulatedBroker"]


@dataclass
class _AggregatedPosition:
    quantity: Decimal = field(default_factory=lambda: Decimal("0"))
    cost_numerator: Decimal = field(default_factory=lambda: Decimal("0"))
    current_price: Decimal | None = None


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
        base_currency: str = "USD",
    ) -> None:
        super().__init__()
        self._fill_model = fill_model or InstantFillModel()
        self._cost_model = cost_model or CostModel()
        self._latency_model = latency_model or ConstantLatencyModel(latency=0)
        self._base_currency = base_currency

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

    def get_account_balance(self) -> AccountBalance:
        """Get a snapshot of the simulated account's financial state.

        Margin fields are not modelled in simulation and are always zero.
        A single CashInfo entry is returned for the base currency.
        """
        total_cash = self.global_portfolio.cash
        for strategy_portfolio in self.strategy_portfolios.values():
            total_cash += strategy_portfolio.cash

        net_assets = self.global_portfolio.cash
        for strategy_portfolio in self.strategy_portfolios.values():
            net_assets += strategy_portfolio.total_value

        cash_info = CashInfo(
            currency=self._base_currency,
            available_cash=total_cash,
            frozen_cash=Decimal("0"),
            settling_cash=Decimal("0"),
            withdrawable_cash=total_cash,
        )
        return AccountBalance(
            currency=self._base_currency,
            net_assets=net_assets,
            total_cash=total_cash,
            buying_power=total_cash,
            init_margin=Decimal("0"),
            maintenance_margin=Decimal("0"),
            margin_call=Decimal("0"),
            risk_level=RiskLevel.SAFE,
            cash_infos=(cash_info,),
        )

    def get_stock_positions(self, instruments: list[Instrument] | None = None) -> list[StockPosition]:
        """Get current simulated stock holdings, aggregated across all strategies.

        Args:
            instruments: Optional filter; when provided only the specified
                instruments are included in the result.

        Returns:
            List of StockPosition snapshots sorted by instrument symbol.
        """
        aggregated: dict[Instrument, _AggregatedPosition] = {}
        for strategy_portfolio in self.strategy_portfolios.values():
            for instrument, position in strategy_portfolio.positions.items():
                if instruments is not None and instrument not in instruments:
                    continue
                if instrument not in aggregated:
                    aggregated[instrument] = _AggregatedPosition()
                entry = aggregated[instrument]
                entry.cost_numerator += position.quantity * position.average_cost
                entry.quantity += position.quantity
                if position.current_price is not None:
                    entry.current_price = position.current_price

        result = []
        for instrument, entry in aggregated.items():
            qty = entry.quantity
            if qty == 0:
                # Offset long/short positions across strategies should not emit a flat holding.
                continue
            cost_price = entry.cost_numerator / qty
            result.append(
                StockPosition(
                    instrument=instrument,
                    currency=instrument.currency,
                    quantity=qty,
                    available_quantity=qty,  # No T+N settlement delay in simulation
                    cost_price=cost_price,
                    current_price=entry.current_price,
                )
            )
        result.sort(key=lambda p: p.instrument.symbol)
        return result

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
        balance = self.get_account_balance()
        self._global_portfolio.recorder.record_snapshot(
            timestamp=timestamp,
            equity=balance.net_assets,
            cash=balance.total_cash,
            positions=dict(self._global_portfolio._positions),
        )
