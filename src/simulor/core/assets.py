"""Broker account and position data models.

Read-only snapshots of broker account state and holdings, designed to work
uniformly across both simulated and live broker implementations.

Inspired by the Longbridge asset APIs but simplified to what both execution
modes need:
    - /v1/asset/account  → AccountBalance + CashInfo
    - /v1/asset/stock    → StockPosition
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulor.types import Instrument


class RiskLevel(IntEnum):
    """Account risk classification.

    Matches the Longbridge risk_level convention:
        0 - safe, no risk action required
        1 - medium risk, monitor closely
        2 - early warning, reduce risk exposure
        3 - danger, margin call imminent or active
    """

    SAFE = 0
    MEDIUM = 1
    WARNING = 2
    DANGER = 3


@dataclass(frozen=True)
class CashInfo:
    """Per-currency cash breakdown within an account.

    Attributes:
        currency: ISO currency code, e.g. "USD", "HKD".
        available_cash: Cash available to place new orders right now.
        frozen_cash: Cash locked by pending orders or settlement holds.
        settling_cash: Cash in T+N settlement pipeline, not yet received.
        withdrawable_cash: Cash that can be withdrawn from the account.
    """

    currency: str
    available_cash: Decimal
    frozen_cash: Decimal
    settling_cash: Decimal
    withdrawable_cash: Decimal


@dataclass(frozen=True)
class AccountBalance:
    """Top-level account snapshot.

    Aggregates overall equity, cash, margin, and risk state for the account.
    Detailed per-currency cash is available in ``cash_infos``.

    Attributes:
        currency: Base settlement currency, e.g. "USD".
        net_assets: Total equity — cash plus all positions at current market value.
        total_cash: Gross cash across all currencies, expressed in base currency.
        buying_power: Effective purchasing power (equals ``total_cash`` in
            simulation; may be higher in a live margin account).
        init_margin: Initial margin currently consumed by open positions.
        maintenance_margin: Maintenance margin required to hold open positions.
        margin_call: Outstanding margin call amount; ``Decimal("0")`` when none.
        risk_level: Current account risk classification.
        cash_infos: Per-currency cash breakdown (``tuple`` to preserve frozen
            semantics; may be empty if the broker does not report it).
    """

    currency: str
    net_assets: Decimal
    total_cash: Decimal
    buying_power: Decimal
    init_margin: Decimal
    maintenance_margin: Decimal
    margin_call: Decimal
    risk_level: RiskLevel
    cash_infos: tuple[CashInfo, ...]


@dataclass(frozen=True)
class StockPosition:
    """Read-only snapshot of a single stock holding.

    Attributes:
        instrument: The held instrument.
        currency: Settlement currency for this position.
        quantity: Total shares currently held (signed; negative = short).
        available_quantity: Shares available to sell immediately. May be less
            than ``quantity`` in live accounts due to T+N settlement restrictions.
            In simulation this always equals ``quantity``.
            Note: Longbridge may return negative values here when shares have
            already been sold but the trade has not yet settled.
        cost_price: Average cost basis per share.
        current_price: Latest market price, or ``None`` if not yet available
            (e.g. before the first market tick, or when the broker asset API
            does not include live pricing).
    """

    instrument: Instrument
    currency: str
    quantity: Decimal
    available_quantity: Decimal
    cost_price: Decimal
    current_price: Decimal | None

    @property
    def market_value(self) -> Decimal | None:
        """Current market value of the position, or ``None`` if price is unknown."""
        if self.current_price is None:
            return None
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal | None:
        """Unrealized profit/loss, or ``None`` if price is unknown."""
        if self.current_price is None:
            return None
        return (self.current_price - self.cost_price) * self.quantity
